"""Regression: place resolution, accommodation name/location handling and follow-ups.

Runs on the synthetic fixture KB (Hill A, Beach B ... / Origin City, Second City) plus synthetic property records added here,
so every assertion exercises the general pipeline rather than a particular real city or hotel. A few tests also replay the exact
wording from the bug reports against the shipped sample dataset.
"""
from __future__ import annotations

from datetime import date

import pytest

from app.ai import chat as chat_mod
from app.ai import nlp
from app.ai.data_loader import load_dataset
from app.ai.engine import Engine
from app.config import load_config

TODAY = date(2026, 10, 15)


def stay_rec(rid, name, dest, tier="premium", price=5200):
    return dict(id=rid, destination_id=dest, name=name, tier=tier, price_inr=price, price_unit="per_room", capacity=2, amenities=["wifi", "spa"], comfort=5,
                accessible=True, lat=11.42, lon=76.70, is_sample=True, note="synthetic test record")


@pytest.fixture()
def eng(fixture_dir):
    ds = load_dataset(fixture_dir)
    for r in (stay_rec("t-zephyr", "Zephyr Lodge (sample)", "hilla"), stay_rec("t-blue", "Blue Heron Resort (sample)", "beachb"),
              stay_rec("t-mango", "Mango Tree Inn (sample)", "coldc", "budget", 1300)):
        ds.accommodation[r["id"]] = r
    return Engine(ds=ds, cfg=load_config())


@pytest.fixture(scope="module")
def real():
    return Engine()


def say(e, st, msg):
    return chat_mod.respond(e, st, msg, TODAY)


def convo(e, *msgs):
    st, out = chat_mod.new_state(), []
    for m in msgs:
        r, st = say(e, st, m)
        out.append(r)
    return out, st


def stays_of(r):
    a = next((a for a in r["actions"] if a["type"] == "stays"), None)
    return a["data"] if a else None


# ------------------------------------------------------------------ accommodation: name + location
def test_name_and_known_location_use_both_and_do_not_ask(eng):
    (r,), st = convo(eng, "Zephyr Lodge Hill A")
    d = stays_of(r)
    assert r["intent"] == "stay" and st["pending"] is None
    assert d["destination_id"] == "hilla" and [s["id"] for s in d["results"]] == ["t-zephyr"]


@pytest.mark.parametrize("msg,rid,dest", [("Blue Heron resorts beach b", "t-blue", "beachb"), ("find mango tree inn in cold c", "t-mango", "coldc"), ("zephyr lodge hill a please", "t-zephyr", "hilla")])
def test_same_pipeline_for_arbitrary_names(eng, msg, rid, dest):
    (r,), _ = convo(eng, msg)
    d = stays_of(r)
    assert d and d["destination_id"] == dest and [s["id"] for s in d["results"]] == [rid]


def test_name_without_location_is_located_from_its_record(eng):
    (r,), st = convo(eng, "Blue Heron Resort")
    d = stays_of(r)
    assert st["pending"] is None and d["destination_id"] == "beachb" and d["results"][0]["id"] == "t-blue"


def test_name_with_a_small_typo_still_resolves(eng):
    (r,), _ = convo(eng, "zepher lodge")
    assert stays_of(r) and stays_of(r)["results"][0]["id"] == "t-zephyr"


def test_name_stated_with_the_wrong_location_is_called_out(eng):
    (r,), _ = convo(eng, "Zephyr Lodge in Beach B")
    d = stays_of(r)
    assert "Hill A" in r["text"] and "Beach B" in r["text"]
    assert d["destination_id"] == "beachb" and "t-zephyr" not in {s["id"] for s in d["results"]}


# ------------------------------------------------------------------ accommodation: location only
def test_location_only_searches_that_location_with_preferences(eng):
    (r,), _ = convo(eng, "cheap hostels in Beach B")
    d = stays_of(r)
    assert d["destination_id"] == "beachb" and {s["tier"] for s in d["results"]} <= {"hostel", "budget", "homestay"} and d["results"][0]["tier"] == "hostel"


# ------------------------------------------------------------------ accommodation: name only, unknown to the dataset
def test_unknown_name_with_known_location_says_so_and_never_invents_it(eng):
    (r,), _ = convo(eng, "Quasar Palace resorts in Hill A")
    d = stays_of(r)
    assert "could not find a property called" in r["text"] and "Quasar Palace" in r["text"]
    assert d and all("quasar" not in s["name"].lower() for s in d["results"]) and d["destination_id"] == "hilla"


def test_unknown_name_without_any_location_asks_where_once(eng):
    (r, r2), st = convo(eng, "Quasar Palace resorts", "Hill A")
    assert r["intent"] == "stay" and "could not find a property" in r["text"] and "which destination" in r["text"].lower()
    assert stays_of(r) is None
    assert stays_of(r2) and stays_of(r2)["destination_id"] == "hilla"


def test_no_name_no_location_is_the_only_case_that_asks_for_a_destination(eng):
    (r,), st = convo(eng, "find me a hotel")
    assert st["pending"]["ask"] == "destination"


# ------------------------------------------------------------------ unsupported locations
def test_starting_city_is_not_treated_as_a_destination_with_stays(eng):
    (r,), st = convo(eng, "Quasar resorts Origin City")
    assert r["intent"] == "unknown_place" and stays_of(r) is None
    assert "starting city" in r["text"] and "Quasar" in r["text"]
    assert st["pending"] is None                                  # it does not re-ask for a destination it already has


def test_place_the_dataset_never_heard_of(eng):
    (r,), _ = convo(eng, "hotels in atlantis")
    assert r["intent"] == "unknown_place" and stays_of(r) is None and "Atlantis" in r["text"]
    (r2,), _ = convo(eng, "Find hotels in Atlantis")
    assert r2["intent"] == "unknown_place"


def test_unsupported_place_offers_relevant_next_steps_only_from_real_records(eng):
    (r,), _ = convo(eng, "hotels near Origin City")      # "near" a starting city is an anchor, not a target
    assert r["intent"] == "stay" or r["intent"] == "unknown_place"
    (r2,), _ = convo(eng, "hotels in Second City")
    assert r2["intent"] == "unknown_place"
    names = {d["name"] for d in eng.ds.destinations.values()}
    for chip in r2["suggestions"]:
        assert any(n in chip for n in names) or chip.startswith("Recommend")


# ------------------------------------------------------------------ follow-ups keep accommodation context
def test_follow_up_changes_preference_and_keeps_destination(eng):
    (a, b, c), st = convo(eng, "hotels in Hill A", "show luxury options instead", "what about hostels instead")
    assert stays_of(a)["destination_id"] == stays_of(b)["destination_id"] == stays_of(c)["destination_id"] == "hilla"
    assert b["intent"] == "stay" and stays_of(b)["results"][0]["tier"] == "premium"
    assert stays_of(c)["results"][0]["tier"] == "hostel"
    assert st["focus"] == "hilla"


def test_follow_up_can_switch_destination_and_keep_the_stay_context(eng):
    (a, b), st = convo(eng, "luxury hotels in Hill A", "what about Beach B instead")
    assert b["intent"] == "stay" and stays_of(b)["destination_id"] == "beachb" and st["focus"] == "beachb"


def test_follow_up_amenity_carries_into_next_search(eng):
    (a, b), _ = convo(eng, "hotels in Hill A with wifi", "luxury options instead")
    assert "wifi" in stays_of(b)["filters"].get("amenities", [])


def test_cheaper_follow_up_still_works(eng):
    (a, b), _ = convo(eng, "luxury hotels in Hill A", "those are too expensive")
    assert b["intent"] == "stay_cheaper"


# ------------------------------------------------------------------ place extraction is general
def test_parse_stay_query_separates_name_from_location(eng):
    ds = eng.ds
    ent = nlp.extract_entities("zephyr lodge hill a", ds, TODAY)
    assert nlp.parse_stay_query("zephyr lodge hill a", ds, ent)["name"] == "zephyr"
    p = nlp.parse_stay_query("cheap hotels in gotham", ds, nlp.extract_entities("cheap hotels in gotham", ds, TODAY))
    assert p["location"] == "gotham" and p["name"] is None


def test_match_stay_name_never_returns_something_that_is_not_in_the_dataset(eng):
    assert nlp.match_stay_name(eng.ds, "quasar") == [] and nlp.match_stay_name(eng.ds, None) == []


# ------------------------------------------------------------------ explicit destinations, itineraries and conversation state
FIRST = "I would like to plan a 3-day trip from Origin City to {d}. I have a budget of 10K rupees, travelling alone. Make an itinerary."


def plan_dest(st):
    return (st.get("plan") or {}).get("destination_id")


def test_explicit_destination_goes_to_the_planner_not_to_recommendations(eng):
    (r,), st = convo(eng, FIRST.format(d="Hill A"))
    assert r["intent"] == "plan" and plan_dest(st) == "hilla" and len(st["plan"]["days"]) == 3
    assert not any(a["type"] == "recommendations" for a in r["actions"])
    assert st["prefs"]["origin"] == "orig" and st["prefs"]["budget"] == 10000 and st["prefs"]["travellers"] == 1


def test_plan_records_all_belong_to_the_resolved_destination(eng):
    for dest, did in (("Hill A", "hilla"), ("Beach B", "beachb"), ("Heritage D", "heritd")):
        _, st = convo(eng, FIRST.format(d=dest))
        ids = [a for d in st["plan"]["days"] for a in d["activity_ids"]]
        assert ids and all(eng.ds.attractions[a]["destination_id"] == did for a in ids)


def test_changing_destination_updates_trip_and_keeps_the_other_constraints(eng):
    (a, b), st = convo(eng, FIRST.format(d="Hill A"), "Hmm, I have changed my mind. Can you draft one for Beach B? Same trip, same budget.")
    assert plan_dest(st) == "beachb" and b["intent"] == "plan"
    p = st["prefs"]
    assert (p["origin"], p["budget"], p["duration_days"], p["travellers"], p["destination"]) == ("orig", 10000, 3, 1, "beachb")
    assert len(st["plan"]["days"]) == 3 and st["focus"] == "beachb"
    assert all(eng.ds.attractions[x]["destination_id"] == "beachb" for d in st["plan"]["days"] for x in d["activity_ids"])


def test_short_follow_up_changes_destination(eng):
    (a, b), st = convo(eng, FIRST.format(d="Hill A"), "Actually, make it Heritage D")
    assert b["intent"] == "plan" and plan_dest(st) == "heritd" and st["prefs"]["budget"] == 10000 and st["prefs"]["origin"] == "orig"


def test_changing_duration_keeps_destination_and_other_constraints(eng):
    (a, b, c), st = convo(eng, FIRST.format(d="Hill A"), "Actually, make it Beach B", "Make it four days instead")
    assert c["intent"] == "modify" and plan_dest(st) == "beachb" and len(st["plan"]["days"]) == 4
    assert st["prefs"]["budget"] == 10000 and st["prefs"]["origin"] == "orig" and st["prefs"]["travellers"] == 1


def test_destination_change_discards_cached_destination_data(eng):
    (a, b, c), st = convo(eng, FIRST.format(d="Hill A"), "luxury hotels in Hill A", "Actually, make it Beach B")
    assert st["last_stay"] is None and st["options"] == []
    assert plan_dest(st) == "beachb"


def test_a_fresh_conversation_does_not_inherit_the_old_destination(eng):
    _, old = convo(eng, FIRST.format(d="Hill A"))
    fresh = chat_mod.new_state()
    assert fresh["focus"] is None and fresh["plan"] is None and fresh["prefs"]["destination"] is None and fresh["prefs"]["origin"] is None
    r, st = say(eng, fresh, "Hotels there")                  # "there" has nothing to refer to in a new conversation
    assert stays_of(r) is None and st["focus"] is None


def test_unsupported_destination_never_produces_another_destinations_itinerary(eng):
    (r,), st = convo(eng, FIRST.format(d="Second City"))
    assert r["intent"] == "unknown_place" and st["plan"] is None and not r["actions"]
    assert "Second City" in r["text"] and "starting city" in r["text"]
    assert st["prefs"]["budget"] == 10000 and st["prefs"]["duration_days"] == 3        # kept for the next step


def test_unsupported_destination_does_not_disturb_an_existing_plan(eng):
    (a, b), st = convo(eng, FIRST.format(d="Hill A"), "Can you draft one for Second City? Same trip, same budget.")
    assert b["intent"] == "unknown_place" and plan_dest(st) == "hilla" and "has not been changed" in b["text"]


def test_after_an_unsupported_destination_alternatives_use_the_kept_constraints(eng):
    (a, b), st = convo(eng, FIRST.format(d="Second City"), "Recommend somewhere for me")
    assert b["intent"] == "recommend" and any(x["type"] == "recommendations" for x in b["actions"])
    assert st["prefs"]["budget"] == 10000


def test_genuine_discovery_request_still_ranks_destinations(eng):
    (r,), st = convo(eng, "Recommend destinations for a three day trip under 10000 from Origin City")
    rec = next(a for a in r["actions"] if a["type"] == "recommendations")
    assert r["intent"] == "recommend" and len(rec["data"]["ranked"]) >= 1 and st["plan"] is None


def test_starting_city_mentions_are_still_origins(eng):
    (r,), st = convo(eng, "Plan a 3 day trip to Hill A from Second City under 9000")
    assert r["intent"] == "plan" and st["prefs"]["origin"] == "o2" and plan_dest(st) == "hilla"


def test_existing_flows_unchanged(eng):
    (a, b, c), _ = convo(eng, "How can I get to Hill A from Origin City", "weather in Hill A", "things to do in Hill A")
    assert [a["intent"], b["intent"], c["intent"]] == ["transport", "weather", "activities"]
    (d,), _ = convo(eng, "Compare Hill A and Beach B")
    assert d["intent"] == "compare"


# ------------------------------------------------------------------ the exact reports, on the shipped sample dataset
def test_reported_accommodation_message_no_longer_asks_for_a_destination(real):
    (r,), st = convo(real, "Arth resorts hyderabad")
    assert "Which destination should I look" not in r["text"] and st["pending"] is None
    assert r["intent"] == "unknown_place" and "Arth" in r["text"] and "Hyderabad" in r["text"] and stays_of(r) is None
    assert "starting city" in r["text"]


def test_reported_itinerary_messages_do_not_substitute_other_destinations(real):
    (a, b), st = convo(real, "I would like to plan a 3-day trip from Hyderabad to Chennai. I have a budget of 10K rupees, travelling alone. Make an itinerary.",
                       "Hmm, I have changed my mind. Can you draft one for Chennai? Same trip, same budget.")
    for r in (a, b):
        assert r["intent"] == "unknown_place" and not any(x["type"] in ("recommendations", "plan") for x in r["actions"]) and "Chennai" in r["text"]
    assert st["plan"] is None and st["prefs"]["budget"] == 10000 and st["prefs"]["origin"] == "hyderabad"


def test_reported_flow_on_a_supported_destination_end_to_end(real):
    (a, b, c), st = convo(real, "Plan a 3 day solo trip from Hyderabad to Ooty under ₹10,000", "Actually, make it Munnar", "Make it five days instead")
    assert plan_dest(st) == "munnar" and len(st["plan"]["days"]) == 5 and st["prefs"]["origin"] == "hyderabad" and st["prefs"]["travellers"] == 1
    assert all(real.ds.attractions[x]["destination_id"] == "munnar" for d in st["plan"]["days"] for x in d["activity_ids"])
