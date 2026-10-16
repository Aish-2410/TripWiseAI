import copy
import math

import pytest

from app.ai import accommodation as acc
from app.ai import transport as trn
from app.ai.budget import optimize, price_plan, suggest_savings
from app.ai.itinerary import _day_limit, generate_itinerary, matches_exclusion, schedule_day
from app.schemas.prefs import Preferences


def base_prefs(**kw):
    d = dict(origin="orig", budget=30000, duration_days=3, travellers=2, interests=["nature", "photography"], pace="balanced")
    d.update(kw)
    return Preferences(**d)


def hotel(ds, did="hilla", tier="budget"):
    s = acc.stay_for_tier(ds, did, tier)
    return (s["lat"], s["lon"])


def gen(engine, prefs, did="hilla", **kw):
    return generate_itinerary(engine.ds, engine.cfg, prefs, did, hotel(engine.ds, did), prefs.duration_days, **kw)


# ------------------------------------------------------------------ itinerary
@pytest.mark.parametrize("pace", ["relaxed", "balanced", "packed"])
def test_itinerary_respects_time_and_activity_limits(engine, pace):
    """#7 Daily time limits, per-day activity caps, no repeats, only real attractions."""
    prefs = base_prefs(pace=pace)
    r = gen(engine, prefs)
    seen = []
    for i, day in enumerate(r["days"]):
        lim, cap = _day_limit(prefs, engine.cfg, i, 3)
        sch = schedule_day(engine.ds, engine.cfg, hotel(engine.ds), day["activity_ids"], prefs.travellers)
        assert len(day["activity_ids"]) <= cap
        assert sch["activity_minutes"] + sch["travel_minutes"] <= lim + 1
        seen += day["activity_ids"]
    assert len(seen) == len(set(seen)) and set(seen) <= set(engine.ds.attractions)
    assert r["search"]["optimal"] is False and r["search"]["algorithm"] == "beam search"


def test_itinerary_honours_exclusions_accessibility_and_elderly(engine):
    ds = engine.ds
    ids = lambda r: {a for d in r["days"] for a in d["activity_ids"]}
    r = gen(engine, base_prefs(excluded_activities=["trekking"]))
    names = {ds.attractions[a]["name"] for a in ids(r)}
    assert "Summit Trek" not in names and "Waterfall Hike" not in names
    r = gen(engine, base_prefs(accessibility_required=True))
    assert all(ds.attractions[a]["accessible"] is not False for a in ids(r))
    r = gen(engine, base_prefs(elderly=True, pace="relaxed"))
    assert all(ds.attractions[a]["intensity"] < 3 for a in ids(r)) and all(len(d["activity_ids"]) <= 3 for d in r["days"])


def test_itinerary_prefers_user_interests(engine):
    ds = engine.ds
    r = gen(engine, base_prefs(interests=["photography"], duration_days=2))
    chosen = {ds.attractions[a]["name"] for d in r["days"] for a in d["activity_ids"]}
    assert {"Botanic Garden", "Viewpoint"} <= chosen            # both photography attractions are scheduled
    r2 = gen(engine, base_prefs(interests=["culture"], duration_days=2, pace="relaxed"))
    assert "Tea Museum" in {ds.attractions[a]["name"] for d in r2["days"] for a in d["activity_ids"]}


def test_nearby_attractions_share_a_day(engine):
    """Rule R7: the cluster of close attractions (Botanic Garden / Tea Museum / Rose Park) is not scattered across days."""
    ds = engine.ds
    r = gen(engine, base_prefs(interests=["nature", "culture"], duration_days=3, pace="relaxed"))
    day_of = {ds.attractions[a]["name"]: d["day"] for d in r["days"] for a in d["activity_ids"]}
    cluster = [n for n in ("Botanic Garden", "Tea Museum", "Rose Park") if n in day_of]
    assert len(cluster) >= 2 and len({day_of[n] for n in cluster}) <= 2


def test_itinerary_fallback_when_data_is_insufficient(engine):
    r = gen(engine, base_prefs(duration_days=7), did="coldc")
    assert sum(len(d["activity_ids"]) for d in r["days"]) <= 3 and r["notes"]       # 3 attractions only: no invention
    r = gen(engine, base_prefs(excluded_activities=["adventure", "culture", "food", "mountains"]), did="coldc")
    assert sum(len(d["activity_ids"]) for d in r["days"]) == 0 and any("No attraction" in n for n in r["notes"])


def test_schedule_orders_clock_times_and_inserts_meals(engine):
    ids = [a["id"] for a in engine.ds.dest_attractions("hilla")][:4]
    sch = schedule_day(engine.ds, engine.cfg, hotel(engine.ds), ids, 2)
    acts = [i for i in sch["items"] if i["kind"] == "activity"]
    assert [a["title"] for a in acts] == [engine.ds.attractions[i]["name"] for i in ids]
    starts = [i["start"] for i in sch["items"]]
    assert starts == sorted(starts)
    assert any(i["kind"] == "meal" for i in sch["items"])


# ------------------------------------------------------------------ budget maths
def test_group_costs_multiply_correctly(engine):
    """#8 Per-person fares x travellers; per-vehicle x vehicles; hostel per bed; rooms from occupancy."""
    link_pp = {"price_inr": 1000, "price_basis": "per_person"}
    link_car = {"price_inr": 6000, "price_basis": "per_vehicle"}
    assert trn.round_trip_total(link_pp, 3) == 1000 * 3 * 2
    assert trn.round_trip_total(link_car, 5) == 6000 * math.ceil(5 / 4) * 2 and trn.round_trip_total(link_car, 4) == 6000 * 2
    hostel = acc.stay_for_tier(engine.ds, "hilla", "hostel"); room = acc.stay_for_tier(engine.ds, "hilla", "budget")
    assert acc.stay_cost(hostel, 3, 2) == hostel["price_inr"] * 3 * 2
    assert acc.stay_cost(room, 3, 2) == room["price_inr"] * 2 * 2           # 3 people -> 2 rooms
    assert acc.stay_cost(room, 4, 2) == room["price_inr"] * 2 * 2 and acc.stay_cost(room, 5, 1) == room["price_inr"] * 3
    assert acc.stay_cost(room, 3, 0) == 0


def test_plan_costs_scale_with_travellers_and_add_up(engine):
    p1 = engine.plan(base_prefs(travellers=1, budget=100000), "hilla", tier="budget", food_tier="mid")
    p3 = engine.plan(base_prefs(travellers=3, budget=100000), "hilla", tier="budget", food_tier="mid")
    b1, b3 = p1["costs"]["breakdown"], p3["costs"]["breakdown"]
    assert b3["transport"] == 3 * b1["transport"] and b3["food"] == 3 * b1["food"]
    assert b3["attractions"] == 3 * b1["attractions"]
    room = acc.stay_for_tier(engine.ds, "hilla", "budget")["price_inr"]
    assert b1["accommodation"] == room * 1 * 2 and b3["accommodation"] == room * 2 * 2
    for c in (p1["costs"], p3["costs"]):
        parts = sum(c["breakdown"][k] for k in ("transport", "accommodation", "food", "attractions", "local_transport"))
        assert c["subtotal"] == parts and abs(c["total"] - (parts + c["breakdown"]["other"])) <= 1
        assert c["per_person"] == round(c["total"] / c["travellers"]) and c["remaining"] == c["budget"] - c["total"]
        assert "Estimates" in c["label"] and c["daily"] and len(c["daily"]) == 3


def test_over_budget_is_flagged(engine):
    p = engine.plan(base_prefs(budget=2000), "hilla")
    assert p["costs"]["over_budget"] and p["costs"]["overrun"] == p["costs"]["total"] - 2000 and p["costs"]["remaining"] < 0
    assert any("exceeds the budget" in n for n in p["notes"])


# ------------------------------------------------------------------ optimiser
def test_budget_optimiser_ranks_explains_and_reduces(engine):
    """#9 Ranked, explained alternatives; every applied step saves money; mandatory constraints survive."""
    prefs = base_prefs(budget=6500, accommodation="midrange", excluded_activities=["trekking"], accessibility_required=False)
    plan = engine.plan(prefs, "hilla", tier="midrange", food_tier="premium")
    start = plan["costs"]["total"]; assert plan["costs"]["over_budget"]
    out = engine.optimize(plan, relax=True)
    assert out["original_total"] == start and out["final_total"] < start
    totals = [start] + [s["running_total"] for s in out["steps"]]
    assert totals == sorted(totals, reverse=True) and all(s["saving"] > 0 and s["description"] for s in out["steps"])
    assert out["ranked_options"] and out["ranked_options"][0]["saving"] > 0
    final = out["plan"]
    names = {engine.ds.attractions[a]["name"] for d in final["days"] for a in d["activity_ids"]}
    assert not {"Summit Trek", "Waterfall Hike"} & names                     # exclusion never silently undone
    assert final["activity_total"] >= math.ceil(0.6 * plan["activity_total"])  # never gutted
    assert out["resolved"] == (not final["costs"]["over_budget"])


def test_optimiser_does_not_break_stated_preferences_unless_allowed(engine):
    prefs = base_prefs(budget=9000, accommodation="midrange", transport=["train"])
    plan = engine.plan(prefs, "hilla")
    assert plan["costs"]["over_budget"] and plan["accommodation_tier"] == "midrange"        # the scenario is genuinely over budget
    strict = engine.optimize(copy.deepcopy(plan), relax=False)
    assert strict["steps"] and all(not s["violates_preference"] for s in strict["steps"])
    assert strict["plan"]["accommodation_tier"] == "midrange" and strict["plan"]["transport"]["mode"] == "train"   # stated preferences untouched
    flagged = [m["description"] for m in strict["ranked_options"] if m["violates_preference"]]
    assert any("hostel" in f for f in flagged)                 # relaxing options are listed, clearly flagged, but not applied
    relaxed = engine.optimize(copy.deepcopy(plan), relax=True)
    assert relaxed["final_total"] < strict["final_total"] and any(s["violates_preference"] for s in relaxed["steps"])


def test_optimiser_message_when_budget_impossible(engine):
    plan = engine.plan(base_prefs(budget=1000), "hilla")
    out = engine.optimize(plan)
    assert out["resolved"] is False and "cheapest version" in out["message"]


def test_optimiser_noop_when_within_budget_or_no_budget(engine):
    plan = engine.plan(base_prefs(budget=500000), "hilla")
    assert engine.optimize(plan)["message"] == "The plan is already within budget." and engine.optimize(plan)["steps"] == []
    p2 = engine.plan(base_prefs(budget=None), "hilla")
    assert engine.optimize(p2)["resolved"] is None
    assert suggest_savings(engine.ds, engine.cfg, Preferences(**p2["prefs"]), copy.deepcopy(p2))   # savings still listed without a budget


def test_matches_exclusion_keywords(engine):
    at = {a["name"]: a for a in engine.ds.attractions.values()}
    assert matches_exclusion(at["Summit Trek"], "trekking") and matches_exclusion(at["Waterfall Hike"], "trekking")
    assert not matches_exclusion(at["Lake Walk"], "trekking") and matches_exclusion(at["Spice Market"], "shopping")
