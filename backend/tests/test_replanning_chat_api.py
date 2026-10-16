import copy
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.ai import chat as chat_mod
from app.ai import nlp
from app.schemas.prefs import Preferences


def prefs(**kw):
    d = dict(origin="orig", budget=30000, duration_days=3, travellers=2, interests=["nature", "adventure"], pace="balanced")
    d.update(kw)
    return Preferences(**d)


def ids(plan):
    return {a for d in plan["days"] for a in d["activity_ids"]}


# ------------------------------------------------------------------ replanning
def test_replan_after_exclusion_preserves_unaffected_activities(engine):
    """#10 Excluding trekking removes only matching items, keeps the rest, bumps the version, and explains the diff."""
    plan = engine.plan(prefs(), "hilla"); plan["version"] = 1
    before = ids(plan)
    trek = {a for a in before if engine.ds.attractions[a]["name"] in ("Summit Trek", "Waterfall Hike")}
    assert trek, "fixture plan should include trekking-type items"
    res = engine.replan(plan, dict(exclude_activities=["trekking"]))
    assert res["ok"]; new = res["plan"]
    assert not (ids(new) & trek)
    kept = before - trek
    assert kept <= ids(new)                                  # unaffected activities preserved
    s = res["summary"]
    assert s["removed"] and s["unchanged"] == len(kept) and new["version"] == 2
    assert res["previous"]["costs"]["total"] == plan["costs"]["total"]       # previous version retained for undo/compare
    assert any(l.startswith("Removed:") for l in s["lines"]) and any("Estimated total" in l for l in s["lines"])
    assert "trekking" in new["prefs"]["excluded_activities"]


def test_replan_budget_drop_runs_optimiser_and_reports(engine):
    plan = engine.plan(prefs(budget=50000, accommodation="midrange"), "hilla")
    res = engine.replan(plan, dict(budget=6500))
    assert res["ok"] and res["plan"]["prefs"]["budget"] == 6500
    assert res["summary"]["cost_after"] < res["summary"]["cost_before"] and "optimiser" in res["summary"]


def test_replan_shorter_trip_and_pace_and_new_interest(engine):
    plan = engine.plan(prefs(duration_days=4, budget=80000), "hilla")
    short = engine.replan(plan, dict(duration_days=2))["plan"]
    assert len(short["days"]) == 2 and ids(short) <= set(engine.ds.attractions)
    relaxed = engine.replan(plan, dict(pace="relaxed"))["plan"]
    assert all(len(d["activity_ids"]) <= 3 for d in relaxed["days"]) and relaxed["prefs"]["pace"] == "relaxed"
    more = engine.replan(plan, dict(add_interests=["culture"]))
    assert more["ok"] and "culture" in more["plan"]["prefs"]["interests"]
    stay = engine.replan(plan, dict(accommodation="hostel"))["plan"]
    assert stay["accommodation_tier"] == "hostel" and stay["costs"]["breakdown"]["accommodation"] < plan["costs"]["breakdown"]["accommodation"]
    assert ids(stay) == ids(plan)                            # an accommodation change must not reshuffle activities


def test_manual_edit_add_remove_move_with_warnings(engine):
    plan = engine.plan(prefs(accessibility_required=True, budget=80000), "hilla")
    victim = plan["days"][0]["activity_ids"][0]
    r = engine.edit(plan, dict(type="remove", activity_id=victim))
    assert r["ok"] and victim not in ids(r["plan"]) and r["plan"]["version"] == 2
    trek = next(a["id"] for a in engine.ds.dest_attractions("hilla") if a["name"] == "Summit Trek")
    r2 = engine.edit(r["plan"], dict(type="add", activity_id=trek, day=1))
    assert r2["ok"] and any("not step-free" in w for w in r2["warnings"]) and trek in r2["plan"]["pinned"]
    assert not engine.edit(plan, dict(type="add", activity_id="nonsense", day=1))["ok"]
    assert not engine.edit(plan, dict(type="move", activity_id=trek, day=9))["ok"]


# ------------------------------------------------------------------ NLP / chat
def test_entity_extraction(ds):
    t = date(2026, 10, 15)
    e = nlp.extract_entities("I want somewhere cold for three days under ₹8,000", ds, t)
    assert e["climate"] == "cold" and e["duration_days"] == 3 and e["budget"] == 8000
    e = nlp.extract_entities("Weekend trip for 2 people from Second City, beaches and food, budget 12k, by train, on 20 Dec", ds, t)
    assert e["duration_days"] == 2 and e["travellers"] == 2 and e["origin"] == "o2" and set(e["interests"]) >= {"beaches", "food"}
    assert e["budget"] == 12000 and e["transport"] == ["train"] and e["start_date"] == "2026-12-20"
    e = nlp.extract_entities("replace trekking with sightseeing", ds, t)
    assert e["exclude_activities"] == ["trekking"] and e["interests"] == ["photography"]
    e = nlp.extract_entities("I'm travelling with my parents, so avoid exhausting activities", ds, t)
    assert e["elderly"] and e["pace"] == "relaxed" and "travellers" not in e      # never invents a head-count
    assert nlp.extract_entities("compare Hill A and Beach B", ds, t)["destinations"] == ["hilla", "beachb"]


def test_chat_flow_recommend_ask_explain_plan_replan_undo(engine):
    st = chat_mod.new_state(); today = date(2026, 10, 15)
    r, st = chat_mod.respond(engine, st, "I want somewhere cool for 3 days under 30000 for 2 people", today)
    assert r["intent"] == "recommend" and "starting" in r["text"].lower() and st["pending"]["ask"] == "origin"     # asks, never guesses
    r, st = chat_mod.respond(engine, st, "Origin City", today)
    assert r["intent"] == "recommend" and r["actions"][0]["type"] == "recommendations" and st["last_ranked"]
    top = st["last_ranked"][0]
    r, st = chat_mod.respond(engine, st, "why did you recommend Hill A?", today)
    assert r["intent"] == "explain" and "Score components" in r["text"] and "Knowledge-base facts" in r["text"]
    r, st = chat_mod.respond(engine, st, "compare Hill A and Beach B", today)
    assert r["intent"] == "compare" and len(r["actions"][0]["data"]["destinations"]) == 2
    r, st = chat_mod.respond(engine, st, "plan a trip to Hill A", today)
    assert r["intent"] == "plan" and st["plan"]["destination_id"] == "hilla"
    base_total = st["plan"]["costs"]["total"]
    r, st = chat_mod.respond(engine, st, "can you make this trip cheaper?", today)
    assert r["intent"] == "cheaper" and st["options"] and "saves" in r["text"]
    r, st = chat_mod.respond(engine, st, "apply option 1", today)
    assert r["intent"] == "apply" and st["plan"]["costs"]["total"] < base_total
    r, st = chat_mod.respond(engine, st, "remove trekking", today)
    assert r["intent"] == "modify" and "trekking" in st["plan"]["prefs"]["excluded_activities"]
    cur, prev = st["plan"]["costs"]["total"], st["previous_plan"]["costs"]["total"]
    assert cur != prev
    r, st = chat_mod.respond(engine, st, "undo", today)
    assert r["intent"] == "undo" and st["plan"]["costs"]["total"] == prev and st["previous_plan"]["costs"]["total"] == cur
    r, st = chat_mod.respond(engine, st, "start over", today)
    assert st["plan"] is None and st["prefs"]["origin"] is None


def test_chat_replies_differ_and_unknown_input_is_handled(engine):
    st = chat_mod.new_state(); texts = set()
    for m in ["hello", "what can you do?", "qwerty asdf", "tell me about Beach B"]:
        r, st = chat_mod.respond(engine, st, m)
        texts.add(r["text"]); assert r["text"]
    assert len(texts) == 4


# ------------------------------------------------------------------ API
@pytest.fixture()
def client(fixture_dir, tmp_path, monkeypatch):
    from app import config
    from app.ai import engine as eng_mod
    from app.api import routes
    from app.ai.data_loader import load_dataset
    monkeypatch.setattr(routes, "_store", None)
    monkeypatch.setattr(routes, "DB_PATH", tmp_path / "t.db")
    eng_mod.get_engine.cache_clear()
    monkeypatch.setattr(eng_mod, "load_dataset", lambda *_a, **_k: load_dataset(fixture_dir))
    from app.main import app
    with TestClient(app) as c:
        yield c
    eng_mod.get_engine.cache_clear()


def test_api_validation_errors(client):
    assert client.post("/api/recommend", json=dict(prefs=dict(origin="orig", budget=-1))).status_code == 422
    assert client.post("/api/recommend", json=dict(prefs=dict(origin="orig", duration_days=99))).status_code == 422
    assert client.post("/api/plan", json=dict(prefs=dict(origin="orig", duration_days=3), destination_id="atlantis")).status_code == 400
    assert client.post("/api/plan", json=dict(prefs=dict(duration_days=3), destination_id="hilla")).status_code == 400
    assert client.get("/api/destinations/atlantis").status_code == 404
    assert client.post("/api/chat", json=dict(message="")).status_code == 422
    assert client.put("/api/config/weights", json=dict(weights=dict(interest=1))).status_code == 400


def test_api_discover_plan_save_reload_flow(client):
    meta = client.get("/api/meta").json()
    assert meta["counts"]["destinations"] == 4 and meta["dataset"]["disclaimer"]
    rec = client.post("/api/recommend", json=dict(prefs=dict(origin="orig", budget=30000, duration_days=3, travellers=2, interests=["nature"], climate="cool"))).json()
    assert rec["ranked"][0]["id"] == "hilla" and rec["trace"]["weights"]
    plan = client.post("/api/plan", json=dict(prefs=rec["trace"]["prefs"], destination_id="hilla")).json()
    assert plan["costs"]["total"] > 0 and plan["days"][0]["schedule"]["items"]
    saved = client.post("/api/trips", json=dict(name="Hill escape", plan=plan)).json()
    listing = client.get("/api/trips").json()
    assert listing[0]["id"] == saved["id"] and listing[0]["total"] == plan["costs"]["total"]
    again = client.get(f"/api/trips/{saved['id']}").json()
    assert again["plan"]["costs"]["total"] == plan["costs"]["total"]
    upd = client.post("/api/trips", json=dict(name="Renamed", plan=plan, trip_id=saved["id"])).json()
    assert upd["id"] == saved["id"] and client.get("/api/trips").json()[0]["name"] == "Renamed"
    assert client.delete(f"/api/trips/{saved['id']}").status_code == 200 and client.get(f"/api/trips/{saved['id']}").status_code == 404


def test_api_chat_session_persists_and_prefs_editable(client):
    r = client.post("/api/chat", json=dict(message="somewhere cool for 3 days from Origin City")).json()
    sid = r["session_id"]
    assert r["prefs"]["climate"] == "cool" and r["prefs"]["origin"] == "orig"
    hist = client.get(f"/api/chat/{sid}").json()
    assert [m["role"] for m in hist["messages"]] == ["user", "assistant"]
    edited = client.put(f"/api/chat/{sid}/prefs", json=dict(prefs=dict(budget=20000, travellers=3))).json()
    assert edited["prefs"]["budget"] == 20000 and edited["prefs"]["travellers"] == 3 and edited["prefs"]["climate"] == "cool"
    assert client.put(f"/api/chat/{sid}/prefs", json=dict(prefs=dict(budget=-5))).status_code == 400
    r2 = client.post("/api/chat", json=dict(session_id=sid, message="recommend something")).json()
    assert r2["prefs"]["budget"] == 20000          # context persists across turns
    assert client.delete(f"/api/chat/{sid}").status_code == 200 and client.get(f"/api/chat/{sid}").status_code == 404


def test_api_kb_search_and_weights(client):
    assert client.get("/api/kb/facts", params=dict(s="hilla", p="HAS_CLIMATE")).json()["facts"][0]["o"] == "cool"
    assert any(r["id"] == "R7_PROXIMITY" for r in client.get("/api/kb/rules").json())
    route = client.get("/api/search/route", params=dict(start="orig", goal="hilla")).json()
    assert route["astar"]["found"] and route["bfs"]["found"] and route["heuristic_check"]["consistent"]
    assert client.get("/api/search/route", params=dict(start="nowhere", goal="hilla")).status_code == 404
    w = client.put("/api/config/weights", json=dict(weights=dict(interest=2, budget=1, climate=1, duration=1, convenience=1, style=0))).json()["weights"]
    try:
        assert abs(sum(w.values()) - 1) < 1e-3 and w["interest"] > w["budget"]
    finally:
        client.delete("/api/config/weights")
    assert abs(sum(client.get("/api/config").json()["weights"].values()) - 1) < 1e-9


def test_replan_preserves_user_edited_arrangement(engine):
    """Locked activities keep their day. A fresh search would put 'Tea Museum' on day 2, so only real preservation passes this."""
    plan = engine.plan(prefs(budget=80000), "hilla")
    byname = {a["name"]: a["id"] for a in engine.ds.dest_attractions("hilla")}
    day_of = lambda p: {engine.ds.attractions[a]["name"]: d["day"] for d in p["days"] for a in d["activity_ids"]}
    assert day_of(plan)["Tea Museum"] == 2
    edited = engine.edit(plan, dict(type="move", activity_id=byname["Tea Museum"], day=1))["plan"]
    assert day_of(edited)["Tea Museum"] == 1
    for change in (dict(accommodation="hostel"), dict(budget=70000)):
        assert day_of(engine.replan(edited, change)["plan"]) == day_of(edited)            # unrelated change: nothing moves
    after = day_of(engine.replan(edited, dict(exclude_activities=["trekking"]))["plan"])
    assert "Summit Trek" not in after and "Waterfall Hike" not in after
    assert {k: v for k, v in after.items()} == {k: v for k, v in day_of(edited).items() if k not in ("Summit Trek", "Waterfall Hike")}
