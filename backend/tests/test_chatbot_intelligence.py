"""Chatbot intelligence: intent recognition, entity extraction, routing to real modules, context retention, graceful failure.

Uses the shipped (sample) dataset so the scenarios match what a user actually types (Ooty, Coorg, Hyderabad...).
A second, tiny fixture dataset covers "no matching records".
"""
from __future__ import annotations

import copy
from datetime import date

import pytest

from app.ai import chat as chat_mod
from app.ai import chat_services as cs
from app.ai import nlp
from app.ai import transport as trn
from app.ai.engine import Engine
from app.config import load_config

TODAY = date(2026, 10, 15)


@pytest.fixture(scope="module")
def real():
    return Engine()


def say(eng, st, msg):
    return chat_mod.respond(eng, st, msg, TODAY)


def spy(monkeypatch, obj, name):
    calls = []
    orig = getattr(obj, name)

    def wrapper(*a, **k):
        calls.append((a, k))
        return orig(*a, **k)
    monkeypatch.setattr(obj, name, wrapper)
    return calls


def planned(eng, msgs=("Plan a three-day trip to Ooty under ₹10,000.", "Hyderabad")):
    st = chat_mod.new_state()
    for m in msgs:
        r, st = say(eng, st, m)
    assert st["plan"], "fixture plan should exist"
    return r, st


# ---------------------------------------------------------------- 1. five-star hotels (the original bug)
def test_five_star_hotels_in_ooty_routes_to_accommodation_not_destination_description(real, monkeypatch):
    calls = spy(monkeypatch, cs, "search_stays")
    r, st = say(real, chat_mod.new_state(), "Give me a few five-star hotels to stay in Ooty.")
    assert r["intent"] == "stay"
    e = r["entities"]
    assert e["stars"] == 5 and e["stay_type"] == "hotel" and e["destinations"] == ["ooty"]
    assert "budget" not in e and "start_date" not in e                    # unspecified stays unspecified
    assert calls, "accommodation retrieval must actually run"
    assert r["actions"][0]["type"] == "stays"
    data = r["actions"][0]["data"]
    assert data["results"] and data["sample"] and data["stars_verified"] is False
    real_ids = {s["id"] for s in real.ds.dest_stays("ooty")}
    assert {s["id"] for s in data["results"]} <= real_ids                  # only real dataset records, nothing invented
    assert all("star" not in str(k).lower() for s in data["results"] for k in s)   # no fabricated star field
    assert "cannot verify" in r["text"] and "Sample data" in r["text"]
    assert r["text"].count("Ooty Premium Stay") == 1
    assert "colonial-era" not in r["text"]                                 # NOT the generic destination blurb
    assert r["understood"]["intent"] == "Find accommodation"
    items = dict(r["understood"]["items"])
    assert items["Destination"] == "Ooty" and items["Star rating"] == "Five stars" and items["Price"] == "Luxury" and items["Dates"] == "Not specified"
    assert st["focus"] == "ooty" and st["shown"] == "stays"
    assert r["suggestions"] and any("Ooty" in s for s in r["suggestions"])


# ---------------------------------------------------------------- 2. cheap hotels near a landmark
def test_cheap_hotels_near_ooty_lake_filters_and_ranks_by_distance(real):
    r, st = say(real, chat_mod.new_state(), "Find cheap hotels near Ooty Lake")
    assert r["intent"] == "stay"
    assert r["entities"]["price_pref"] == "low" and r["entities"]["near_phrase"] == "ooty lake"
    d = r["actions"][0]["data"]
    assert d["target"] == "Ooty Lake" and d["results"]
    assert all(s["tier"] in ("hostel", "budget", "homestay") for s in d["results"])
    dist = [s["distance_to_target_km"] for s in d["results"]]
    assert dist == sorted(dist) and all(x < 15 for x in dist)
    lake = next(a for a in real.ds.dest_attractions("ooty") if a["name"] == "Ooty Lake")
    s0 = d["results"][0]
    from app.ai.geo import haversine_km
    assert abs(haversine_km(s0["lat"], s0["lon"], lake["lat"], lake["lon"]) - s0["distance_to_target_km"]) < 0.06


def test_unknown_landmark_is_reported_not_guessed(real):
    r, _ = say(real, chat_mod.new_state(), "Find hotels near the Eiffel Tower in Ooty")
    assert r["intent"] == "stay" and r["actions"][0]["data"]["results"]
    assert any("could not find" in n for n in r["actions"][0]["data"]["notes"])


# ---------------------------------------------------------------- 3. transport
def test_how_can_i_get_to_ooty_from_hyderabad(real, monkeypatch):
    calls = spy(monkeypatch, cs, "transport_data")
    r, st = say(real, chat_mod.new_state(), "How can I get to Ooty from Hyderabad?")
    assert r["intent"] == "transport" and r["entities"]["origin"] == "hyderabad" and r["entities"]["destinations"] == ["ooty"]
    assert calls
    d = r["actions"][0]["data"]
    expect = {o["mode"] for o in trn.options(real.ds, "hyderabad", "ooty", None, 1)}
    assert {o["mode"] for o in d["options"]} == expect and {"cheapest", "fastest", "most_comfortable", "best_overall"} <= set(d)
    assert "estimates" in r["text"] and "not live fares" in r["text"]
    assert st["prefs"]["origin"] == "hyderabad"


def test_transport_without_origin_asks_once_then_answers(real):
    r, st = say(real, chat_mod.new_state(), "How do I get to Ooty?")
    assert r["intent"] == "transport" and st["pending"]["ask"] == "origin" and not r["actions"]
    r, st = say(real, st, "Hyderabad")
    assert r["intent"] == "transport" and r["actions"][0]["type"] == "transport"


# ---------------------------------------------------------------- 4. activities
def test_best_activities_in_ooty(real, monkeypatch):
    calls = spy(monkeypatch, cs, "activities_data")
    r, st = say(real, chat_mod.new_state(), "What are the best activities in Ooty?")
    assert r["intent"] == "activities" and calls
    d = r["actions"][0]["data"]
    names = {a["name"] for a in real.ds.dest_attractions("ooty")}
    assert d["items"] and {i["name"] for i in d["items"]} <= names
    sig = [next(a["significance"] for a in real.ds.dest_attractions("ooty") if a["id"] == i["id"]) for i in d["items"]]
    assert sig == sorted(sig, reverse=True)
    assert "hotel" not in r["text"].lower()


def test_attractions_near_landmark(real):
    r, _ = say(real, chat_mod.new_state(), "Find attractions near Ooty Lake")
    d = r["actions"][0]["data"]
    assert r["intent"] == "activities" and d["near"] == "Ooty Lake" and all(i["name"] != "Ooty Lake" for i in d["items"])
    km = [i["distance_km"] for i in d["items"]]
    assert km == sorted(km)


# ---------------------------------------------------------------- 5. plan
def test_plan_three_day_trip_under_10000_asks_origin_once_then_builds(real, monkeypatch):
    r, st = say(real, chat_mod.new_state(), "Plan a three-day trip to Ooty under ₹10,000.")
    assert r["intent"] == "plan" and r["entities"]["budget"] == 10000 and r["entities"]["duration_days"] == 3 and r["entities"]["destinations"] == ["ooty"]
    assert st["pending"]["ask"] == "origin" and "Where will you be starting" in r["text"]
    calls = spy(monkeypatch, real, "plan")
    r, st = say(real, st, "Hyderabad")
    assert r["intent"] == "plan" and calls
    p = st["plan"]
    assert p["destination_id"] == "ooty" and len(p["days"]) == 3 and p["prefs"]["budget"] == 10000 and st["focus"] == "ooty" and st["shown"] == "plan"
    assert r["actions"][0]["type"] == "plan" and "Estimated total" in r["text"]


def test_plan_without_destination_recommends_first(real):
    r, st = say(real, chat_mod.new_state(), "Plan a three-day holiday.")
    assert r["intent"] == "recommend" and r["entities"]["duration_days"] == 3 and st["pending"]["ask"] == "origin"


# ---------------------------------------------------------------- 6. cheaper (actually changes the plan)
def test_make_it_cheaper_uses_budget_optimiser_and_entire_trip_applies_it(real, monkeypatch):
    _, st = planned(real)
    calls = spy(monkeypatch, chat_mod, "suggest_savings")
    r, st2 = say(real, st, "Make it cheaper.")
    assert r["intent"] == "cheaper" and calls and r["actions"][0]["type"] == "savings" and st2["options"]
    assert st2["plan"]["costs"]["total"] == st["plan"]["costs"]["total"]            # options only, nothing silently applied
    r, st3 = say(real, st2, "Okay, make the entire trip cheaper too.")
    assert r["intent"] == "cheaper" and st3["plan"]["costs"]["total"] < st["plan"]["costs"]["total"] and st3["previous_plan"]["costs"]["total"] == st["plan"]["costs"]["total"]
    assert r["actions"][0]["type"] == "plan" and "New estimated total" in r["text"]


def test_cheaper_with_no_plan_does_not_pretend(real):
    r, st = say(real, chat_mod.new_state(), "Make it cheaper")
    assert r["intent"] == "cheaper" and st["plan"] is None and "no itinerary" in r["text"].lower() or "once we have a plan" in r["text"].lower()


# ---------------------------------------------------------------- 7. replace trekking with sightseeing
def test_replace_trekking_modifies_existing_itinerary_preserving_the_rest(real, monkeypatch):
    _, st = planned(real, ("Plan a four-day trip to Coorg under ₹40,000 for 2 people", "Hyderabad"))
    before = {a for d in st["plan"]["days"] for a in d["activity_ids"]}
    calls = spy(monkeypatch, real, "replan")
    r, st2 = say(real, st, "Replace trekking with sightseeing.")
    assert r["intent"] == "modify" and calls
    assert r["entities"]["exclude_activities"] == ["trekking"] and r["entities"]["interests"] == ["photography"]
    assert "trekking" in st2["plan"]["prefs"]["excluded_activities"] and st2["previous_plan"]["destination_id"] == st["plan"]["destination_id"]
    after = {a for d in st2["plan"]["days"] for a in d["activity_ids"]}
    assert len(before & after) >= len(before) // 2                                 # unaffected activities preserved
    trek = {a["id"] for a in real.ds.dest_attractions("coorg") if "adventure" in a["tags"] and "trek" in a["name"].lower()}
    assert not (trek & after)


def test_edit_request_without_itinerary_is_noted_not_faked(real):
    r, st = say(real, chat_mod.new_state(), "Tell me about Ooty")
    r, st = say(real, st, "Replace trekking with sightseeing")
    assert r["intent"] == "modify" and st["plan"] is None and "no itinerary" in r["text"].lower() and "trekking" in st["prefs"]["excluded_activities"]


# ---------------------------------------------------------------- 8. context: "there", "those", "it"
def test_find_hotels_there_uses_established_destination(real):
    r, st = say(real, chat_mod.new_state(), "Tell me about Coorg")
    assert r["intent"] == "details" and st["focus"] == "coorg"
    r, st = say(real, st, "Find hotels there.")
    assert r["intent"] == "stay" and r["actions"][0]["data"]["destination_id"] == "coorg"
    r, st = say(real, st, "What are the best things to do there?")
    assert r["intent"] == "activities" and r["actions"][0]["data"]["destination_id"] == "coorg"
    r, st = say(real, st, "What is the weather like there?")
    assert r["intent"] == "weather" and r["actions"][0]["data"]["destination_id"] == "coorg"


def test_full_conversation_context_hotels_too_expensive_then_whole_trip(real):
    _, st = planned(real)
    r, st = say(real, st, "Find five-star hotels there.")
    assert r["intent"] == "stay" and r["actions"][0]["data"]["destination_id"] == "ooty"
    shown = min(s["price_inr"] for s in r["actions"][0]["data"]["results"])
    r, st = say(real, st, "Those are too expensive.")
    assert r["intent"] == "stay_cheaper"
    cheaper = r["actions"][0]["data"]["results"]
    assert cheaper and all(s["price_inr"] < shown for s in cheaper) and st["plan"]["destination_id"] == "ooty"
    before = st["plan"]["costs"]["total"]
    r, st = say(real, st, "Okay, make the entire trip cheaper too.")
    assert r["intent"] == "cheaper" and st["plan"]["costs"]["total"] < before


def test_destination_change_updates_focus_and_new_trip_resets(real):
    r, st = say(real, chat_mod.new_state(), "hotels in Ooty")
    r, st = say(real, st, "what about hotels in Munnar?")
    assert r["actions"][0]["data"]["destination_id"] == "munnar" and st["focus"] == "munnar"
    r, st = say(real, st, "start over")
    assert st["focus"] is None and st["plan"] is None
    r, st = say(real, st, "Find hotels there")
    assert st["pending"]["ask"] == "destination" and "Which destination" in r["text"]
    r, st = say(real, st, "Goa")
    assert r["intent"] == "stay" and r["actions"][0]["data"]["destination_id"] == "goa"


# ---------------------------------------------------------------- 9. compare
def test_compare_ooty_and_coorg_without_needing_an_origin(real, monkeypatch):
    calls = spy(monkeypatch, real, "compare")
    r, st = say(real, chat_mod.new_state(), "Compare Ooty and Coorg.")
    assert r["intent"] == "compare" and calls and st["pending"] is None
    cols = r["actions"][0]["data"]["destinations"]
    assert [c["id"] for c in cols] == ["ooty", "coorg"] and all(c["climate"] and c["best_seasons"] and c["activities"] for c in cols)
    assert "starting from" in r["text"]                                             # offers cost comparison once an origin is known


# ---------------------------------------------------------------- 10. weather without live data
def test_weather_is_grounded_and_admits_no_live_data(real):
    r, st = say(real, chat_mod.new_state(), "What is the weather like in Ooty?")
    assert r["intent"] == "weather"
    d = r["actions"][0]["data"]
    assert d["live_weather"] is False and d["climate"] == real.ds.destinations["ooty"]["climate"]
    assert "No live weather" in r["text"] and "°" not in r["text"] and "forecast" in r["text"]
    r2, _ = say(real, chat_mod.new_state(), "What is the weather like there?")
    assert r2["intent"] == "weather" and "Which destination" in r2["text"]          # no destination known: asks, never invents


def test_best_time_to_visit_uses_recorded_seasons(real):
    r, _ = say(real, chat_mod.new_state(), "When is the best time to visit Coorg?")
    assert r["intent"] == "weather" and set(r["actions"][0]["data"]["best_seasons"]) == set(real.ds.destinations["coorg"]["best_seasons"])


# ---------------------------------------------------------------- 11. ambiguity
@pytest.mark.parametrize("msg", ["hmm okay", "maybe", "asdf lkj", "the thing"])
def test_ambiguous_message_asks_short_clarification_without_changing_state(real, msg):
    st0 = chat_mod.new_state()
    r, st = say(real, st0, msg)
    assert r["intent"] == "clarify" and not r["actions"] and r["suggestions"] and len(r["text"]) < 260
    assert st["plan"] is None and st["prefs"] == st0["prefs"]


# ---------------------------------------------------------------- 12. no matching records
def test_hotel_request_with_no_records_says_so_and_offers_alternatives(ds):
    eng = Engine(ds=ds, cfg=load_config())
    for sid in [k for k, v in eng.ds.accommodation.items() if v["destination_id"] == "hilla"]:
        del eng.ds.accommodation[sid]
    r, st = say(eng, chat_mod.new_state(), "Find hotels in Hill A")
    assert r["intent"] == "stay" and r["actions"][0]["data"]["results"] == []
    assert "could not find any accommodation records" in r["text"] and "cannot verify" in r["text"]
    assert "Hill A" in r["text"] and st["focus"] == "hilla"
    assert not any(w in r["text"].lower() for w in ("star", "₹")), "must not invent properties"


def test_stars_with_missing_tier_falls_back_and_labels_it(ds):
    eng = Engine(ds=ds, cfg=load_config())
    del eng.ds.accommodation["hilla-premium"]
    r, _ = say(eng, chat_mod.new_state(), "five star hotel in Hill A")
    d = r["actions"][0]["data"]
    assert d["relaxed"] and d["results"] and all(s["match"] == "closest" for s in d["results"]) and "cannot verify" in r["text"]


# ---------------------------------------------------------------- intent coverage (section 2 examples)
@pytest.mark.parametrize("msg,intent", [
    ("Suggest some five-star hotels in Ooty.", "stay"), ("Where should I stay in Ooty?", "stay"), ("Find me luxury accommodation in Ooty.", "stay"),
    ("I need a hotel near Ooty Lake.", "stay"), ("Show me affordable places to stay in Ooty.", "stay"), ("How can I get from Hyderabad to Ooty?", "transport"),
    ("What are the best things to do in Ooty?", "activities"), ("Plan a three-day holiday.", "plan"), ("Plan a three day holiday in Coorg", "plan"),
    ("Which is better, Ooty or Munnar?", "compare"), ("How far is Ooty from Hyderabad?", "route"), ("Is it going to rain in Munnar?", "weather"),
    ("best time to visit Goa", "weather"), ("Somewhere cool for 3 days", "recommend"), ("hello", "greet"), ("what can you do", "help"),
    ("Do I need a visa to travel there?", "general"), ("homestays in Coorg with breakfast", "stay"), ("3 star hotel in Goa under 3000 per night", "stay"),
    ("Compare transport options from Hyderabad to Ooty", "transport"), ("Show me budget accommodation in Ooty", "stay"),
])
def test_intent_classification(real, msg, intent):
    st = chat_mod.new_state(); st["focus"] = "ooty"
    ent = nlp.extract_entities(msg, real.ds, TODAY)
    from app.ai.intents import classify
    got, conf = classify(msg, ent, st)
    assert got == intent and conf >= 0.5, (msg, got, conf)


def test_spelling_errors_are_repaired_conservatively(real):
    r, _ = say(real, chat_mod.new_state(), "hotles in Ootty")
    assert r["intent"] == "stay" and r["actions"][0]["data"]["destination_id"] == "ooty" and r["entities"]["corrected"]
    fixed, fixes = nlp.correct_spelling("good food near the water with kids, cheap tickets and trains", real.ds)
    assert not fixes                                                                  # ordinary words are left alone


def test_stay_entities(real):
    e = nlp.extract_entities("I need a 4 star resort with a spa and breakfast in Goa for 3 nights under ₹9,000 near the beach", real.ds, TODAY)
    assert e["stars"] == 4 and e["stay_type"] == "resort" and set(e["amenities"]) == {"spa", "breakfast"} and e["nights"] == 3 and e["budget"] == 9000 and e["destinations"] == ["goa"]
    assert e["near_phrase"] == "the beach" or e["near_phrase"] == "beach"


def test_amenity_filter_and_unmatched_amenity_is_disclosed(real):
    r, _ = say(real, chat_mod.new_state(), "hotels in Ooty with a spa")
    res = r["actions"][0]["data"]["results"]
    assert res and all("spa" in s["amenities"] for s in res)
    r, _ = say(real, chat_mod.new_state(), "hostels in Ooty with a spa")
    assert any("No matching property lists spa" in n for n in r["actions"][0]["data"]["notes"])


def test_price_cap_per_night_and_unreachable_cap_is_disclosed(real):
    r, _ = say(real, chat_mod.new_state(), "hotels in Ooty under ₹2000")
    assert all(s["price_inr"] <= 2000 for s in r["actions"][0]["data"]["results"])
    r, _ = say(real, chat_mod.new_state(), "hotels in Ooty under ₹300 per night")
    d = r["actions"][0]["data"]
    assert d["results"] and any("Nothing in the dataset is priced" in n for n in d["notes"])


def test_those_are_too_expensive_when_already_cheapest(real):
    r, st = say(real, chat_mod.new_state(), "cheapest hostels in Ooty")
    r, st = say(real, st, "Those are too expensive")
    assert r["intent"] == "stay_cheaper" and "already the cheapest" in r["text"]


# ---------------------------------------------------------------- suggestions are contextual and functional
def test_suggestion_chips_are_contextual_and_each_one_works(real):
    first, st = say(real, chat_mod.new_state(), "Give me a few five-star hotels in Ooty")
    after_plan, st_p = planned(real)
    assert set(first["suggestions"]) != set(after_plan["suggestions"])
    assert any("trekking" in s or "food" in s for s in after_plan["suggestions"]) and "Show my budget breakdown" in after_plan["suggestions"]
    for base_msg, base_st in [("Give me a few five-star hotels in Ooty", chat_mod.new_state()), ("What are the best things to do in Ooty?", chat_mod.new_state()),
                              ("How can I get to Ooty from Hyderabad?", chat_mod.new_state()), ("Tell me about Coorg", chat_mod.new_state()),
                              ("What is the weather like in Ooty?", chat_mod.new_state())]:
        r, s0 = say(real, base_st, base_msg)
        assert r["suggestions"], base_msg
        for chip in r["suggestions"]:
            r2, _ = say(real, copy.deepcopy(s0), chip)
            assert r2["intent"] not in ("clarify", "general", "error"), (base_msg, chip, r2["intent"])
    for chip in after_plan["suggestions"]:
        r2, _ = say(real, copy.deepcopy(st_p), chip)
        assert r2["intent"] not in ("clarify", "general", "error"), (chip, r2["intent"])


def test_hotels_near_itinerary_attractions(real):
    _, st = planned(real)
    r, _ = say(real, st, "Find accommodation near these attractions")
    d = r["actions"][0]["data"]
    assert r["intent"] == "stay" and d["results"] and any("itinerary" in n for n in d["notes"])


# ---------------------------------------------------------------- failure handling
def test_backend_failure_gives_friendly_message_and_preserves_trip(real, monkeypatch):
    _, st = planned(real)
    snapshot = copy.deepcopy(st["plan"])
    monkeypatch.setattr(cs, "search_stays", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    r, st2 = say(real, st, "Find hotels in Ooty")
    assert r["intent"] == "error" and "could not complete" in r["text"] and "boom" not in r["text"] and "Traceback" not in r["text"]
    assert st2["plan"] == snapshot and r["suggestions"]


# ---------------------------------------------------------------- understood panel
def test_understood_for_plan_and_transport(real):
    r, _ = say(real, chat_mod.new_state(), "Plan a 4 day trip to Munnar for 2 people from Chennai under 30000 with nature and food")
    items = dict(r["understood"]["items"])
    assert r["understood"]["intent"] == "Build an itinerary" and items["Destination"] == "Munnar" and items["Duration"] == "4 days" and items["Budget"] == "₹30,000"
    assert "nature" in items["Interests"] and "internal" not in str(r["understood"]).lower() and "0.9" not in str(r["understood"])
    r, _ = say(real, chat_mod.new_state(), "How can I get to Goa from Delhi by train?")
    items = dict(r["understood"]["items"])
    assert items["To"] == "Goa" and items["Preferred mode"] == "train"


# ---------------------------------------------------------------- regressions on the engine itself
def test_regression_recommend_plan_optimise_replan_still_work(real):
    from app.schemas.prefs import Preferences
    p = Preferences(origin="hyderabad", budget=40000, duration_days=4, travellers=2, interests=["nature", "mountains"], climate="cool")
    rec = real.recommend(p, top_n=5)
    assert rec["ranked"] and rec["ranked"][0]["match_score"] >= rec["ranked"][-1]["match_score"]
    plan = real.plan(p, rec["ranked"][0]["id"])
    assert plan["days"] and plan["costs"]["total"] > 0
    tight = dict(plan, prefs=dict(plan["prefs"], budget=int(plan["costs"]["total"] * 0.6)))
    opt = real.optimize(tight, relax=True)
    assert opt["steps"] and opt["final_total"] < opt["original_total"]
    rp = real.replan(plan, dict(exclude_activities=["trekking"], pace="relaxed"))
    assert rp["ok"] and rp["summary"]["unchanged"] >= 1


# ---------------------------------------------------------------- API surface
def test_api_chat_returns_understood_and_focus_and_destination_is_correctable(real):
    from fastapi.testclient import TestClient
    from app.main import app
    c = TestClient(app)
    j = c.post("/api/chat", json=dict(message="Give me a few five-star hotels to stay in Ooty")).json()
    assert j["reply"]["intent"] == "stay" and j["reply"]["understood"]["intent"] == "Find accommodation" and j["focus"]["name"] == "Ooty"
    sid = j["session_id"]
    j2 = c.put(f"/api/chat/{sid}/prefs", json=dict(prefs=dict(destination="Coorg"))).json()
    assert j2["focus"]["id"] == "coorg"
    j3 = c.post("/api/chat", json=dict(session_id=sid, message="Find hotels there")).json()
    assert j3["reply"]["actions"][0]["data"]["destination_id"] == "coorg"
    assert c.put(f"/api/chat/{sid}/prefs", json=dict(prefs=dict(destination="Atlantis"))).status_code == 400
    c.delete(f"/api/chat/{sid}")
