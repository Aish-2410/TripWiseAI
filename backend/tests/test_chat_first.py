"""Backend behaviour behind the chat-first UI."""
from fastapi.testclient import TestClient
from app.main import app

c = TestClient(app)


def chat(msg, sid=None):
    r = c.post("/api/chat", json={"message": msg, "session_id": sid})
    assert r.status_code == 200, r.text
    return r.json()


def test_cheapest_hotels_coorg_returns_stay_cards():
    r = chat("Find me the cheapest hotels in Coorg")
    assert r["reply"]["intent"] in ("stay", "stay_cheaper")
    assert any(a["type"] == "stays" for a in r["reply"]["actions"])
    assert r["focus"]["id"] == "coorg"


def test_show_all_stays_returns_more_than_default():
    r = chat("Find hotels in Coorg")
    r2 = chat("Show all hotels in Coorg", r["session_id"])
    st = next(a for a in r2["reply"]["actions"] if a["type"] == "stays")
    assert len(st["data"]["results"]) > 3


def test_unknown_place_japan_is_honest():
    r = chat("Plan a 5-day trip to Japan under ₹80,000")
    assert r["reply"]["intent"] == "unknown_place"
    assert not any(a["type"] == "plan" for a in r["reply"]["actions"])
    assert "Japan" in r["reply"]["text"]


def test_build_my_itinerary_without_context_asks_where():
    r = chat("Build my itinerary")
    assert r["reply"]["intent"] == "ask_where"


def test_weekend_getaway_from_hyderabad_recommends():
    r = chat("I want a peaceful weekend getaway from Hyderabad")
    assert r["reply"]["intent"] in ("recommend", "plan")
    assert r["prefs"]["origin"] == "hyderabad" or "Hyderabad" in str(r["prefs"].get("origin", ""))


def test_transport_compare_chennai_ooty():
    r = chat("Compare the cheapest ways to travel from Chennai to Ooty")
    assert any(a["type"] == "transport" for a in r["reply"]["actions"])


def test_summaries_endpoint_only_returns_requested_ids():
    a = chat("Find hotels in Ooty")
    chat("Weather in Munnar")
    r = c.get("/api/chat/summaries", params={"ids": a["session_id"]}).json()
    assert [x["id"] for x in r] == [a["session_id"]]
    assert r[0]["title"].startswith("Find hotels")
    assert c.get("/api/chat/summaries", params={"ids": "nope"}).json() == []


def test_meta_reports_no_llm():
    m = c.get("/api/meta").json()
    assert m["chat"]["llm_enabled"] is False
