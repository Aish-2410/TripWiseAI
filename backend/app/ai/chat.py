"""Conversational travel concierge: dialogue manager over the deterministic NLP pipeline.

The bot never answers from canned text alone. Every reply is generated from the engine's
actual output (recommender, knowledge base, planner, budget optimiser, replanner).
"""
from __future__ import annotations

import copy
import logging
import re
from datetime import date

from . import chat_services as cs
from . import llm, nlp
from .intents import INTENT_LABELS, CLARIFY_BELOW, classify
from .budget import suggest_savings
from .data_loader import INTERESTS
from .engine import Engine
from .planner import PlanError
from ..schemas.prefs import Preferences

SCALARS = ["budget", "duration_days", "travellers", "climate", "season", "travel_style", "accommodation", "pace", "start_date", "origin"]
FLAGS = ["elderly", "children", "accessibility_required"]


def new_state() -> dict:
    return dict(prefs=Preferences().model_dump(), last_ranked=[], plan=None, previous_plan=None, pending=None, options=[], turns=0,
                focus=None, shown=None, last_stay=None)


def merge_prefs(prefs: dict, ent: dict) -> dict:
    p = copy.deepcopy(prefs)
    for k in SCALARS:
        if k in ent:
            p[k] = ent[k]
    for k in FLAGS:
        if ent.get(k):
            p[k] = True
    for k in ("interests", "transport"):
        if k in ent:
            p[k] = sorted(set(p.get(k, [])) | set(ent[k]))
    if "exclude_activities" in ent:
        p["excluded_activities"] = sorted(set(p.get("excluded_activities", [])) | set(ent["exclude_activities"]))
    if p.get("elderly") and p.get("pace") == "balanced":
        p["pace"] = "relaxed"
    return p


def inr(x) -> str:
    return f"INR {int(round(x)):,}"


def _chips(*xs: str) -> list[str]:
    return [x for x in xs if x][:5]


log = logging.getLogger("tripwise.chat")
STAR = {1: "One star", 2: "Two stars", 3: "Three stars", 4: "Four stars", 5: "Five stars"}


def build_understood(eng: Engine, intent: str, ent: dict, st: dict) -> dict:
    """Plain-language interpretation of the latest message, shown in the 'What I understood' panel (no internals)."""
    ds, pr = eng.ds, st["prefs"]
    items: list[list[str]] = []

    def add(label, value, always=False):
        if value not in (None, "", []) or always:
            items.append([label, str(value) if value not in (None, "", []) else "Not specified"])
    dname = lambda i: ds.destinations[i]["name"] if i in ds.destinations else None
    dest = dname((ent.get("destinations") or [st.get("focus")])[0] if (ent.get("destinations") or st.get("focus")) else None)
    oname = ds.origins.get(ent.get("origin") or pr.get("origin") or "", {}).get("name")
    if intent in ("stay", "stay_cheaper"):
        add("Destination", dest, True)
        add("Accommodation", (ent.get("stay_type") or "").title() or ent.get("accommodation"), True)
        add("Star rating", STAR.get(ent.get("stars")), True)
        pp = {"low": "Budget-friendly", "high": "Luxury", "mid": "Mid-range"}.get(ent.get("price_pref"))
        cap_ = ent.get("max_price") or ent.get("budget")
        add("Price", f"up to ₹{int(cap_):,} per night" if cap_ else ("Cheaper than the options shown" if intent == "stay_cheaper" else pp), True)
        add("Amenities", ", ".join(ent.get("amenities", [])))
        add("Near", ent.get("near_phrase").title() if ent.get("near_phrase") else ("Your itinerary's attractions" if ent.get("near_plan") else None))
        add("Guests", ent.get("travellers") or (pr.get("travellers") if pr.get("travellers", 1) > 1 else None))
        add("Dates", ent.get("start_date") or (f"{ent['nights']} night(s)" if ent.get("nights") else None), True)
    elif intent in ("transport", "route"):
        add("From", oname, True); add("To", dest, True); add("Travellers", ent.get("travellers") or pr.get("travellers"))
        add("Preferred mode", ", ".join(ent.get("transport", [])))
    elif intent == "activities":
        add("Destination", dest, True); add("Interest", ", ".join(ent.get("interests", []))); add("Near", (ent.get("near_phrase") or "").title() or None)
    elif intent == "weather":
        add("Destination", dest, True); add("Season", ent.get("season"))
    elif intent == "compare":
        add("Destinations", " vs ".join(dname(i) for i in ent.get("destinations", [])))
    elif intent in ("plan", "recommend"):
        add("Destination", dest, intent == "plan"); add("Starting from", oname); add("Budget", f"₹{int(ent['budget']):,}" if ent.get("budget") else (f"₹{int(pr['budget']):,}" if pr.get("budget") else None), True)
        add("Duration", f"{ent.get('duration_days') or pr.get('duration_days')} days" if (ent.get("duration_days") or pr.get("duration_days")) else None, True)
        add("Travellers", ent.get("travellers")); add("Interests", ", ".join(ent.get("interests", []) or pr.get("interests", [])))
        add("Climate", ent.get("climate")); add("Travel style", ent.get("travel_style")); add("Pace", ent.get("pace"))
    elif intent in ("modify", "cheaper", "cost", "details", "explain"):
        add("Destination", dest)
        for k, lab in (("budget", "New budget"), ("duration_days", "Duration"), ("pace", "Pace"), ("accommodation", "Stay"), ("transport", "Transport")):
            if k in ent:
                add(lab, ent[k] if not isinstance(ent[k], list) else ", ".join(ent[k]))
        add("Avoid", ", ".join(ent.get("exclude_activities", []))); add("Add interest", ", ".join(ent.get("interests", [])) if intent == "modify" else None)
        if intent == "cheaper":
            add("Applies to", "Your accommodation options" if st.get("shown") == "stays" and not st.get("plan") else "Your whole trip")
    if ent.get("corrected"):
        items.append(["Spelling fixed", ", ".join(f"{a} → {b}" for a, b in ent["corrected"].items())])
    return dict(intent=INTENT_LABELS.get(intent, intent.title()), items=items)


def respond(eng: Engine, state: dict, message: str, today: date | None = None) -> tuple[dict, dict]:
    """Never raises: a failed specialised operation returns a clear message and leaves the trip state untouched."""
    try:
        return _respond(eng, state, message, today)
    except Exception:  # noqa: BLE001 - the user must never see a stack trace
        log.exception("chat handler failed for %r", message)
        keep = copy.deepcopy(state); keep["turns"] = keep.get("turns", 0) + 1; keep["pending"] = None
        return dict(intent="error", entities={}, actions=[], suggestions=["Try again", "What can you do?"], prefs=keep["prefs"],
                    understood=dict(intent="Something went wrong", items=[]), focus=keep.get("focus"),
                    text="Sorry, I could not complete that request, and nothing about your trip was changed. Please try rephrasing it, or pick one of the suggestions."), keep


def _respond(eng: Engine, state: dict, message: str, today: date | None = None) -> tuple[dict, dict]:
    today = today or date.today()
    st = copy.deepcopy(state); st["turns"] += 1
    for k, v in dict(focus=None, shown=None, last_stay=None).items():
        st.setdefault(k, v)
    ds = eng.ds
    fixed_msg, fixes = nlp.correct_spelling(message, ds)
    message = fixed_msg
    ent = nlp.extract_entities(message, ds, today)
    if fixes:
        ent["corrected"] = fixes
    text_l = message.lower().strip()
    # a bare city name answering "where are you starting from?"
    pend = st.get("pending")
    if pend and pend.get("ask") == "origin" and "origin" not in ent:
        o = ds.resolve_origin(message.strip())
        if o:
            ent["origin"] = o
    if pend and pend.get("ask") == "duration" and "duration_days" not in ent:
        n = nlp._num(text_l.split()[0]) if text_l.split() else None
        if n and 1 <= n <= 14:
            ent["duration_days"] = n
    if pend and pend.get("ask") == "destination" and "destinations" not in ent:
        did_ = ds.resolve_destination(message.strip())
        if did_:
            ent["destinations"] = [did_]
    resumed = bool(pend and (("origin" in ent and pend["ask"] == "origin") or ("duration_days" in ent and pend["ask"] == "duration") or ("destinations" in ent and pend["ask"] == "destination")))
    if resumed and pend.get("ent"):
        ent = {**pend["ent"], **ent}
    intent, conf = (pend["then"], 1.0) if resumed else classify(message, ent, st)
    if text_l.startswith("apply option") or text_l.startswith("apply "):
        intent, conf = "apply", 1.0
    # Gemini (optional): interprets the message; its output is validated, grounded in the message and merged UNDER the rule-based entities
    via, llm_unsupported, llm_question, llm_name, llm_ignored = "rules", None, None, None, None
    if not resumed and intent not in ("greet", "reset", "undo", "help", "apply") and conf < 0.85 and llm.enabled():
        snapshot = (copy.deepcopy(ent), intent, conf)
        try:
            it = llm.interpret_raw(message, llm.context_for(st, ds))
            if it is None:
                via = "rules-fallback"
            else:
                via = "gemini"
                lent = llm.to_entities(it, ds, today, message)
                llm_unsupported, llm_name, llm_ignored = lent.pop("_unsupported", None), lent.pop("_stay_name", None), lent.pop("_ignored", None)
                before = dict(ent)
                for k_, v_ in lent.items():
                    ent.setdefault(k_, v_)                                   # explicit rule-based values are never overwritten
                if ent != before:
                    intent, conf = classify(message, ent, st)
                if conf < 0.85:
                    needs = {"modify": st.get("plan"), "cheaper": st.get("plan"), "cost": st.get("plan"), "stay_cheaper": st.get("last_stay")}
                    if it.intent != "other" and (it.intent not in needs or needs[it.intent]):
                        intent, conf = it.intent, 0.8
                    if it.needs_clarification and not (ent.get("destinations") or ent.get("origin")):
                        llm_question = llm.sanitize_question(it.clarification_question)
                        if llm_question:
                            intent, conf = "clarify", 0.8
        except Exception:  # noqa: BLE001 - whatever goes wrong inside the optional Gemini step, the rule-based result stands
            log.exception("Gemini step failed; continuing with the rule-based interpretation")
            ent, intent, conf = snapshot
            via, llm_unsupported, llm_question, llm_name, llm_ignored = "rules-fallback", None, None, None, None
    if conf < CLARIFY_BELOW:
        intent = "clarify"
    if intent == "plan" and not (ent.get("destinations") or st.get("focus") or st["prefs"].get("destination") or st.get("last_ranked")):
        intent = "recommend"          # "plan a three-day holiday" with no place yet: recommend places first
        if not any(k in ent for k in ("budget", "duration_days", "interests", "climate", "season", "travellers", "origin", "travel_style")):
            intent = "ask_where"
    STAY_INTENTS = ("stay", "stay_cheaper")
    intent_before = intent
    parts = nlp.parse_stay_query(message, ds, ent) if intent in STAY_INTENTS else dict(name=None, location=None)
    if llm_name and intent in STAY_INTENTS and not parts["name"]:
        parts["name"] = llm_name.lower()
    name_hits = nlp.match_stay_name(ds, parts["name"]) if parts["name"] else []
    unknown = None
    if not ent.get("destinations") and not resumed and intent in ("stay", "stay_cheaper", "plan", "activities", "transport", "route", "weather", "details", "recommend", "ask_where", "clarify"):
        unknown = nlp.find_unsupported_place(message, ds, intent, ent, parts, bare_ok=bool(pend and pend.get("ask") == "destination")) or llm_unsupported
        if unknown and not (intent == "stay" and name_hits):      # a property that exists in the dataset identifies its own location
            intent = "unknown_place"
    # the destination changed: anything keyed to the old destination must not leak into the new answer
    newd = (ent.get("destinations") or [None])[0]
    if newd and intent not in ("reset", "greet", "help", "compare") and newd != st.get("focus"):
        st["last_stay"], st["options"] = None, []
    if ent.get("destinations") and intent not in ("reset", "greet", "help"):
        st["focus"] = ent["destinations"][0]
    st["pending"] = None
    prefs_d = st["prefs"]
    reply = dict(intent=intent, entities={k: v for k, v in ent.items()}, actions=[], suggestions=[])

    def finish(text: str, **kw):
        reply["text"] = text; reply.update(kw); reply["prefs"] = st["prefs"]
        reply["understood"] = build_understood(eng, intent, ent, st)
        reply["understanding"] = via
        reply["understood"]["items"].append(["Interpreted by", {"gemini": "Gemini, checked against the dataset", "rules-fallback": "Rule-based parser (Gemini unavailable)"}.get(via, "Rule-based parser")])
        ign = list(llm_ignored or []) + ([ent["ignored_budget"]] if ent.get("ignored_budget") else [])
        if ign:
            reply["understood"]["items"].append(["Ignored", "; ".join(ign)])
        reply["focus"] = st.get("focus")
        return reply, st

    def ask_user(what: str, then: str, text: str, chips: list[str], keep: bool = True):
        st["pending"] = dict(ask=what, then=then, **(dict(ent=ent) if keep else {}))
        return finish(text, suggestions=chips)

    dest_chips = [d["name"] for d in sorted(ds.destinations.values(), key=lambda x: x["name"])][:5]

    origin_names = [o["name"] for o in ds.origins.values()][:5]

    if intent == "greet":
        return finish("Welcome to TripWise AI - the world, thoughtfully yours. Tell me what you have in mind: a budget, number of days, the climate you love, or what you enjoy. For example, \"somewhere cool for 3 days under 8,000 rupees\".",
                      suggestions=_chips("Somewhere cold for 3 days under ₹8,000", "Beaches and food for 4 days", "Heritage trip for 2 days from Delhi"))
    if intent == "help":
        return finish("I can recommend destinations from your budget, days, climate and interests; explain why I chose them; compare places; build a day-by-day itinerary; and re-plan it when things change (cheaper, fewer days, no trekking...). Costs are estimates from sample data, never live prices.",
                      suggestions=_chips("Recommend a hill station", "Compare Ooty and Coorg", "Why did you recommend that?"))
    if intent == "reset":
        st = new_state(); st["turns"] = state["turns"] + 1
        reply["prefs"] = st["prefs"]; reply["text"] = "A fresh start. Where would you like to begin - budget, days, or the kind of place you enjoy?"
        reply["understood"] = dict(intent=INTENT_LABELS["reset"], items=[]); reply["focus"] = None
        reply["suggestions"] = ["Somewhere cool for 3 days under ₹10,000", "Beaches and food for 4 days", "Heritage trip for 2 days"]
        return reply, st
    if intent == "undo":
        if st.get("previous_plan"):
            st["plan"], st["previous_plan"] = st["previous_plan"], st["plan"]
            reply["actions"].append(dict(type="plan", plan=st["plan"]))
            return finish(f"Done - I restored the previous version. Its estimated total is {inr(st['plan']['costs']['total'])}.", suggestions=_chips("Make it cheaper", "Show cost breakdown"))
        return finish("There is no earlier version of this plan yet.")


    if intent == "unknown_place":
        st["prefs"] = merge_prefs(st["prefs"], ent)           # keep what the user told us (days, budget, travellers) for the next step
        names = ", ".join(d["name"] for d in sorted(ds.destinations.values(), key=lambda x: x["name"]))
        what = {"stay": "accommodation records", "stay_cheaper": "accommodation records", "activities": "attractions", "weather": "climate data", "details": "destination data"}.get(intent_before, "attractions, stays or itinerary data")
        if unknown["kind"] == "origin_only":
            lead = f"{unknown['name']} is in my dataset only as a starting city (I can cost journeys from it), so I have no {what} for it" + (" and cannot plan or price a trip there." if intent_before in ("plan", "recommend", "ask_where", "transport", "route", "clarify") else ".")
            near = cs.nearest_destinations_with_stays(ds, unknown["lat"], unknown["lon"])
        else:
            lead = f"I do not have {unknown['name']} in my dataset, so I cannot plan or price a trip there."
            near = []
        if parts.get("name") and intent_before in STAY_INTENTS:
            lead = f"I could not find a property called “{parts['name'].title()}” in the dataset. " + lead
        txt = lead + f" TripWise covers {len(ds.destinations)} destinations in India: {names}."
        if near:
            txt += " Closest to " + unknown["name"] + " with records: " + ", ".join(f"{n['name']} (~{n['km']} km)" for n in near) + "."
        kept = [x for x in (f"{st['prefs']['duration_days']} days" if st["prefs"].get("duration_days") else None, f"₹{int(st['prefs']['budget']):,}" if st["prefs"].get("budget") else None) if x]
        if st.get("plan"):
            txt += f" Your current {st['plan']['destination_name']} plan has not been changed."
        txt += (" I have kept " + " and ".join(kept) + " in mind. " if kept else " ") + "Pick one of these, or ask me to suggest places that fit."
        return finish(txt, suggestions=([(f"Find hotels in {n['name']}" if intent_before in STAY_INTENTS else f"Plan a trip to {n['name']}") for n in near[:2]] + dest_chips[:2] + ["Recommend somewhere for me"])[:5])
    if intent == "ask_where":
        return finish("Happy to build one. Where would you like to go? Name a destination, or tell me your budget, number of days and what you enjoy and I will suggest places.",
                      suggestions=["Plan a 3-day trip to Ooty", "A peaceful weekend from Hyderabad", "Beaches and food for 4 days", "Somewhere cool under ₹10,000"])

    # ---------------------------------------------------------------- accommodation (hotels, resorts, hostels, homestays)
    if intent in ("stay", "stay_cheaper"):
        did, assumed = cs.resolve_focus(st, ent)
        if intent == "stay_cheaper" and st.get("last_stay") and not ent.get("destinations"):
            did = st["last_stay"]["did"]
        name_note, only_ids = "", None
        if parts["name"]:
            in_dest = [h for h in name_hits if h["destination_id"] == did] if ent.get("destinations") else name_hits
            if in_dest:
                homes = {h["destination_id"] for h in in_dest}
                if len(homes) > 1:
                    names_ = [ds.destinations[x]["name"] for x in sorted(homes)]
                    return ask_user("destination", "stay", f"More than one property matches “{parts['name'].title()}” ({', '.join(names_)}). Which destination do you mean?", names_)
                did = in_dest[0]["destination_id"]; assumed = False
                only_ids = {h["id"] for h in in_dest}
                if unknown:
                    name_note = f"{unknown['name']} has no accommodation records here, but “{in_dest[0]['name']}” is in the dataset under {ds.destinations[did]['name']}.\n"
            elif name_hits:
                other = ds.destinations[name_hits[0]["destination_id"]]["name"]
                name_note = f"“{name_hits[0]['name']}” is in the dataset under {other}, not {ds.destinations[did]['name']}, so I am showing {ds.destinations[did]['name']} options instead.\n"
            elif did:
                name_note = f"I could not find a property called “{parts['name'].title()}” in the dataset, so I am not showing it. Here are the {ds.destinations[did]['name']} records I do have:\n"
            else:
                return ask_user("destination", "stay", f"I could not find a property called “{parts['name'].title()}” in the dataset, and I do not know which destination to search. Which destination should I look in?", dest_chips)
        if not did:
            return ask_user("destination", "stay", "Which destination should I look for accommodation in?", dest_chips)
        follow_up = intent == "stay" and bool(st.get("last_stay")) and not ent.get("destinations") and st["last_stay"]["did"] == did and not only_ids
        sf, e2 = None, dict(ent)
        if follow_up:                    # "show luxury options instead": same destination, new preference; amenities / landmark carry over
            sf = {k: v for k, v in (st["last_stay"].get("filters") or {}).items() if k in ("amenities", "near_phrase")}
        if intent == "stay_cheaper":
            last = st["last_stay"] or {}
            lowest = min(last.get("prices") or [0])
            sf = {k: v for k, v in (last.get("filters") or {}).items() if k in ("amenities", "near_phrase")}
            e2 = {k: v for k, v in ent.items() if k in ("destinations", "travellers", "nights")}
            e2["max_price"] = max(lowest - 1, 0)
        show_all = bool(re.search(r"\b(all|every|full list|everything)\b", text_l))
        data = cs.search_stays(eng, st, e2, did, sf, limit=12 if show_all else 3, only_ids=only_ids)
        name = data["destination_name"]
        if not data["results"] or (intent == "stay_cheaper" and data["relaxed"]):
            if intent == "stay_cheaper":
                st["shown"] = "stays"
                return finish(f"Those are already the cheapest accommodation records in the dataset for {name} (from {cs.inr(lowest)} per night). You can lower the cost elsewhere: transport, meals or activities.",
                              suggestions=cs.suggestions_for(st, ds, "stays", did))
            near = cs.nearby_destinations_with_stays(ds, did)
            txt = f"I could not find any accommodation records for {name} in the dataset, so I cannot verify any suitable stay there."
            if near:
                txt += " Nearby destinations that do have records: " + ", ".join(f"{n['name']} (~{n['km']} km)" for n in near) + "."
            reply["actions"].append(dict(type="stays", data=dict(data, alternatives=near)))
            return finish(txt + " A live accommodation source would be needed for more.", suggestions=[f"Find hotels in {n['name']}" for n in near] or cs.suggestions_for(st, ds, None, did))
        st["last_stay"] = dict(did=did, filters=data["filters"], prices=[r["price_inr"] for r in data["results"]], ids=[r["id"] for r in data["results"]])
        st["shown"] = "stays"; st["focus"] = did
        txt = name_note + cs.stays_text(data)
        if intent == "stay_cheaper":
            txt = "More affordable options than the ones I showed:\n" + txt
        if assumed:
            txt = f"(Assuming {name}, your top match.)\n" + txt
        reply["actions"].append(dict(type="stays", data=data))
        return finish(txt, suggestions=cs.suggestions_for(st, ds, "stays", did))

    # ---------------------------------------------------------------- transport / routes / travel time
    if intent in ("transport", "route"):
        did, assumed = cs.resolve_focus(st, ent)
        origin = ent.get("origin") or st["prefs"].get("origin")
        dests = ent.get("destinations", [])
        if intent == "route" and len(dests) >= 2 and not ent.get("origin"):
            r = cs.route_data(eng, dests[0], dests[1])
            if not r:
                return finish(f"I cannot find a modelled route between {ds.destinations[dests[0]]['name']} and {ds.destinations[dests[1]]['name']}.")
            st["shown"] = "route"
            reply["actions"].append(dict(type="route", data=r))
            return finish(f"{' → '.join(r['path'])}: about {r['km']} km and {r['hours']} h. {r['note']}", suggestions=cs.suggestions_for(st, ds, "transport", dests[1]))
        if not did:
            return ask_user("destination", intent, "Which destination are you travelling to?", dest_chips)
        if not origin:
            return ask_user("origin", intent, f"Where will you be travelling from? I need a starting city to estimate the journey to {ds.destinations[did]['name']}.", origin_names)
        st["prefs"]["origin"] = origin
        n = ent.get("travellers") or st["prefs"].get("travellers") or 1
        days = ent.get("duration_days") or st["prefs"].get("duration_days")
        data = cs.transport_data(eng, origin, did, n, days, ent.get("transport"))
        st["shown"] = "transport"; st["focus"] = did
        txt = cs.transport_text(data)
        if intent == "route" or re.search(r"how (far|long)|distance|travel time", text_l):
            r = cs.route_data(eng, origin, did)
            if r:
                txt += f"\nModelled road route: {' → '.join(r['path'])} (about {r['km']} km, {r['hours']} h)."
        if ent.get("transport") and data["options"]:
            missing = [m for m in ent["transport"] if m not in {o["mode"] for o in data["options"]}]
            if missing:
                txt += f"\nNo {'/'.join(missing)} option is modelled for this pair."
        reply["actions"].append(dict(type="transport", data=data))
        if not data["options"]:
            near = [n_ for n_ in cs.nearby_destinations_with_stays(ds, did)]
            return finish(txt, suggestions=cs.suggestions_for(st, ds, "transport", did))
        return finish(txt, suggestions=cs.suggestions_for(st, ds, "transport", did))

    # ---------------------------------------------------------------- activities / attractions
    if intent == "activities":
        did, assumed = cs.resolve_focus(st, ent)
        if not did:
            return ask_user("destination", "activities", "Which destination would you like activity ideas for?", dest_chips)
        data = cs.activities_data(eng, did, ent)
        st["shown"] = "activities"; st["focus"] = did
        reply["actions"].append(dict(type="activities", data=data))
        txt = cs.activities_text(data)
        return finish((f"(Assuming {data['destination_name']}.)\n" if assumed else "") + txt + "\n(Sample dataset: durations and fees are estimates.)", suggestions=cs.suggestions_for(st, ds, "activities", did))

    # ---------------------------------------------------------------- weather / best season
    if intent == "weather":
        did, assumed = cs.resolve_focus(st, ent)
        if not did:
            return ask_user("destination", "weather", "Which destination do you mean?", dest_chips)
        w = cs.weather_data(eng, did, ent)
        st["shown"] = "weather"; st["focus"] = did
        reply["actions"].append(dict(type="weather", data=w))
        return finish(cs.weather_text(w), suggestions=cs.suggestions_for(st, ds, "weather", did))

    # ---------------------------------------------------------------- general travel question / clarification
    if intent == "general":
        did, _ = cs.resolve_focus(st, ent)
        if did:
            d = ds.destinations[did]
            return finish(f"I can only answer from my dataset, and it does not cover that. For {d['name']} I know the climate ({d.get('climate') or 'not recorded'}), best seasons ({', '.join(d['best_seasons']) or 'not recorded'}), attractions, sample stays and estimated transport costs.",
                          suggestions=cs.suggestions_for(st, ds, "recs", did))
        return finish("I can only answer from my travel dataset (destinations, attractions, climate and seasons, stays, transport estimates), so general questions like visas, safety or packing are outside what I can verify. I can help you choose, plan and budget a trip.",
                      suggestions=["Somewhere cool for 3 days under ₹10,000", "Compare Ooty and Coorg", "What can you do?"])
    if intent == "clarify" and llm_question:
        return finish(llm_question, suggestions=["Somewhere cool for 3 days under ₹10,000", "Find hotels in Ooty", "What can you do?"])
    if intent == "clarify":
        fid = st.get("focus")
        if fid:
            n = ds.destinations[fid]["name"]
            return finish(f"I was not sure what you would like to do. Do you want hotels, things to do, transport or a full plan for {n}?",
                          suggestions=[f"Find hotels in {n}", f"What are the best things to do in {n}?", f"Plan a 3-day trip to {n}", "Recommend somewhere else"])
        return finish("I was not sure what you meant. Are you looking for destination ideas, hotels, transport, things to do or a full itinerary?",
                      suggestions=["Somewhere cool for 3 days under ₹10,000", "Find hotels in Ooty", "What can you do?"])

    # ---------------------------------------------------------------- an edit request but no itinerary yet
    if intent == "modify" and not st.get("plan") and st.get("focus"):
        st["prefs"] = merge_prefs(st["prefs"], ent)
        n = ds.destinations[st["focus"]]["name"]
        bits = []
        if ent.get("exclude_activities"):
            bits.append("avoid " + ", ".join(ent["exclude_activities"]))
        if ent.get("interests"):
            bits.append("add " + ", ".join(ent["interests"]))
        return finish(f"There is no itinerary to edit yet. I have noted that you want to {' and '.join(bits) or 'change that'}, and I will apply it when I build your {n} plan.",
                      suggestions=[f"Plan a {st['prefs'].get('duration_days') or 3}-day trip to {n}", f"Find hotels in {n}"])

    # ---------------------------------------------------------------- recommend / set preferences
    if intent in ("recommend",) or (intent == "modify" and not st.get("plan")):
        st["prefs"] = merge_prefs(st["prefs"], ent)
        prefs = Preferences(**st["prefs"])
        if not prefs.origin:
            st["pending"] = dict(ask="origin", then="recommend")
            nice = []
            if ent.get("duration_days"): nice.append(f"{ent['duration_days']} days")
            if ent.get("budget"): nice.append(f"a budget of ₹{int(ent['budget']):,}")
            if ent.get("climate"): nice.append(f"{ent['climate']} weather")
            if ent.get("interests"): nice.append("an interest in " + ", ".join(ent["interests"]))
            known = ", ".join(nice)
            return finish(("Noted: " + known + ". " if known else "") + "Where will you be starting your journey? Travel time and cost depend on it.",
                          suggestions=origin_names)
        out = eng.recommend(prefs, top_n=5)
        if out["needs_info"]:
            st["pending"] = dict(ask="origin", then="recommend")
            return finish(out["message"], suggestions=origin_names)
        st["last_ranked"] = [r["id"] for r in out["ranked"]]
        reply["actions"].append(dict(type="recommendations", data=out))
        if not out["ranked"]:
            tips = " ".join(out.get("relaxation", []))
            return finish(f"I could not find a destination that satisfies all your hard constraints. {tips}", suggestions=_chips("Add more days", "Raise the budget"))
        top = out["ranked"][:3]
        lines = [f"{r['rank']}. {r['name']} ({r['match_score']:.0f}/100) - about {inr(r['cost']['typical'])}, {r['one_way_hours']} h each way by {r['transport_best']}" for r in top]
        txt = "Here is what suits you best:\n" + "\n".join(lines) + f"\n\n{top[0]['explanation']}"
        if out["excluded"]:
            txt += f"\n\n{len(out['excluded'])} destination(s) were ruled out by your constraints (open the reasoning panel to see why)."
        ask = None
        if not prefs.duration_days:
            ask = "How many days do you have? I will tailor the match and the plan."; st["pending"] = dict(ask="duration", then="recommend")
        elif not prefs.budget:
            ask = "What is your total budget for the group? It lets me check affordability."
        if ask:
            txt += "\n\n" + ask
        st["focus"], st["shown"] = top[0]["id"], "recs"
        chips = cs.suggestions_for(st, ds, "recs", top[0]["id"])
        if len(top) > 1:
            chips = chips[:4] + [f"Compare {top[0]['name']} and {top[1]['name']}"]
        return finish(txt, suggestions=chips[:5])

    # ---------------------------------------------------------------- explain
    if intent == "explain":
        did = (ent.get("destinations") or [None])[0] or (st["last_ranked"][0] if st["last_ranked"] else (st["plan"] or {}).get("destination_id"))
        if not did:
            return finish("Ask me for a recommendation first, then I can explain exactly why each place was chosen.", suggestions=_chips("Recommend a hill station"))
        prefs = Preferences(**st["prefs"])
        if not prefs.origin:
            st["pending"] = dict(ask="origin", then="explain")
            return finish("Where are you starting from? The explanation includes travel time and cost.", suggestions=origin_names)
        ex = eng.explain(did, prefs)
        ev = ex["evaluation"]
        name = ex["destination"]
        if ev and ev.get("excluded_reasons"):
            return finish(f"{name} was ruled out because: " + "; ".join(ev["excluded_reasons"]) + ".", suggestions=_chips("Recommend again"))
        comp = ", ".join(f"{k} {v['score']:.2f} (weight {v['weight']:.2f})" for k, v in ev["components"].items() if v["status"] != "not_specified")
        fired = "; ".join(f"{a['rule_id']} {a['points']:+g}: {a['reason']}" for a in ev["adjustments"] if a["fired"]) or "no ranking rules fired"
        facts = ex["facts"]
        key = [f"{f['p']} {f['o']}" for f in facts if f["p"] in ("HAS_CLIMATE", "HAS_TYPE", "HAS_MIN_DAYS", "HAS_MAX_DAYS", "HAS_ACCESSIBILITY")]
        txt = (f"{ev['explanation']}\n\nScore components: {comp}.\nRules: {fired}.\nKnowledge-base facts: " + "; ".join(key) + ".")
        reply["actions"].append(dict(type="explanation", data=ex))
        return finish(txt, suggestions=_chips(f"Plan a trip to {name}", "Compare the top two"))

    # ---------------------------------------------------------------- compare
    if intent == "compare":
        cids = list(ent.get("destinations", []))
        if len(cids) == 1 and st.get("focus") and st["focus"] != cids[0]:
            cids = [st["focus"], cids[0]]
        if len(cids) < 2:
            top2 = (st.get("last_ranked") or [])[:2]
            if len(top2) == 2:
                cids = top2
            else:
                return ask_user("destination", "compare", "Which two destinations would you like me to compare?", [f"Compare {dest_chips[0]} and {dest_chips[1]}", f"Compare {dest_chips[2]} and {dest_chips[3]}"], keep=False)
        ent["destinations"] = cids
        prefs = Preferences(**merge_prefs(st["prefs"], {k: v for k, v in ent.items() if k != "destinations"}))
        ids = ent.get("destinations")
        cmp_ = eng.compare(ids, prefs)
        reply["actions"].append(dict(type="comparison", data=cmp_))
        lines = []
        for c in cmp_["destinations"]:
            cost = f"about {inr(c['estimated_cost'])}" if c["estimated_cost"] else "cost not available"
            lines.append(f"{c['name']}: {c['climate']} climate, best in {', '.join(c['best_seasons'])}, {c['recommended_days']} days, {cost}; {c['pace_note']}" + (f" - excluded: {c['excluded'][0]}" if c["excluded"] else ""))
        st["shown"], st["focus"] = "compare", cids[0]
        no_origin = "" if prefs.origin else "\n\nTell me where you are starting from and I will add costs and travel times."
        return finish("Side by side:\n" + "\n".join(lines) + "\n\nThe full table is below. Costs are estimates." + no_origin,
                      suggestions=[f"Plan a trip to {c['name']}" for c in cmp_["destinations"][:2]] + [f"Find hotels in {cmp_['destinations'][0]['name']}", f"What is the weather like in {cmp_['destinations'][1]['name']}?"])

    # ---------------------------------------------------------------- details
    if intent == "details":
        did = ent["destinations"][0]
        d = ds.destinations[did]
        attrs = sorted(ds.dest_attractions(did), key=lambda a: (-a["significance"], a["name"]))[:4]
        txt = (f"{d['name']}, {d['state']} - {d['description']} Climate: {d.get('climate')}; best in {', '.join(d['best_seasons'])}; ideal for {d['min_days']}-{d['max_days']} days. "
               f"Highlights: {', '.join(a['name'] for a in attrs)}. (Sample dataset; verify details before travelling.)")
        st["shown"], st["focus"] = "details", did
        return finish(txt, suggestions=cs.suggestions_for(st, ds, "details", did))

    # ---------------------------------------------------------------- plan
    if intent == "plan":
        st["prefs"] = merge_prefs(st["prefs"], ent)
        did = (ent.get("destinations") or [None])[0] or st.get("focus") or (st["prefs"].get("destination")) or (st["last_ranked"][0] if st["last_ranked"] else None)
        if not did:
            return finish("Which destination should I plan? Ask for recommendations first or name a place.", suggestions=_chips("Recommend a hill station"))
        st["prefs"]["destination"] = did
        prefs = Preferences(**st["prefs"])
        if not prefs.origin:
            st["pending"] = dict(ask="origin", then="plan")
            return finish(f"Lovely choice. Where will you be starting from, so I can cost the journey to {ds.destinations[did]['name']}?", suggestions=origin_names)
        if not prefs.duration_days:
            st["pending"] = dict(ask="duration", then="plan")
            return finish(f"How many days would you like in {ds.destinations[did]['name']}?", suggestions=["2", "3", "4", "5"])
        try:
            plan = eng.plan(prefs, did)
        except PlanError as e:
            return finish(f"I could not build that plan: {e}")
        st["previous_plan"], st["plan"], st["options"] = st.get("plan"), plan, []
        st["focus"], st["shown"] = did, "plan"
        reply["actions"].append(dict(type="plan", plan=plan))
        c = plan["costs"]
        days = " | ".join(f"Day {d['day']}: " + ", ".join(ds.attractions[a]["name"] for a in d["activity_ids"]) for d in plan["days"] if d["activity_ids"])
        txt = f"Your {len(plan['days'])}-day {plan['destination_name']} plan: {days}.\nEstimated total {inr(c['total'])} ({inr(c['per_person'])} per person) via {plan['transport']['mode']}, {plan['accommodation_tier']} stay."
        if c["over_budget"]:
            txt += f" That is {inr(c['overrun'])} over your budget - say \"make it cheaper\" and I will show ranked options."
        elif c["budget"]:
            txt += f" That leaves {inr(c['remaining'])} of your budget."
        if plan["notes"]:
            txt += " Note: " + " ".join(plan["notes"][:2])
        return finish(txt, suggestions=cs.suggestions_for(st, ds, "plan", did))

    # ---------------------------------------------------------------- cost
    if intent == "cost":
        if not st.get("plan"):
            return finish("Build a plan first and I will break down the estimate for you.", suggestions=_chips("Recommend a hill station"))
        c = st["plan"]["costs"]; b = c["breakdown"]
        txt = "Estimated breakdown: " + ", ".join(f"{k.replace('_', ' ')} {inr(v)}" for k, v in b.items()) + f". Total {inr(c['total'])} ({inr(c['per_person'])} per person). These are estimates from sample data."
        return finish(txt, suggestions=_chips("Make it cheaper"))

    # ---------------------------------------------------------------- cheaper
    if intent == "cheaper":
        if not st.get("plan"):
            fid = st.get("focus")
            if fid:
                n = ds.destinations[fid]["name"]
                return finish(f"There is no itinerary to make cheaper yet. I can build a plan for {n} within a budget, or look for lower-priced stays.",
                              suggestions=[f"Plan a {st['prefs'].get('duration_days') or 3}-day trip to {n} under ₹10,000", f"Show budget accommodation in {n}"])
            return finish("Once we have a plan I can show ways to lower its cost. Tell me where you are travelling from and what you enjoy to begin.", suggestions=_chips("Recommend a hill station"))
        prefs = Preferences(**st["plan"]["prefs"])
        opts = suggest_savings(ds, eng.cfg, prefs, copy.deepcopy(st["plan"]), limit=5)
        if not opts:
            return finish("This plan is already close to the cheapest the data allows; no further savings found.")
        st["options"] = [dict(description=o["description"], saving=o["saving"], new_total=o["new_total"], violates_preference=o["violates_preference"], plan=o["plan"]) for o in opts]
        if re.search(r"\b(entire|whole|everything|overall|all of it)\b", text_l):     # "make the entire trip cheaper": apply the best option that respects stated preferences
            pick = next((o for o in st["options"] if not o["violates_preference"]), st["options"][0])
            st["previous_plan"], st["plan"] = st["plan"], pick["plan"]
            st["plan"]["version"] = (st["previous_plan"].get("version", 1)) + 1
            st["options"], st["shown"] = [], "plan"
            reply["actions"].append(dict(type="plan", plan=st["plan"]))
            c = st["plan"]["costs"]
            return finish(f"Done. {pick['description']}, which saves about {inr(pick['saving'])}. New estimated total {inr(c['total'])}" + (f" ({inr(c['overrun'])} over budget)." if c["over_budget"] else "."),
                          suggestions=["Make it cheaper", "Undo", "Show my budget breakdown"])
        lines = [f"{i}. {o['description']} - saves about {inr(o['saving'])} (new total {inr(o['new_total'])})" + (" [changes a stated preference]" if o["violates_preference"] else "") for i, o in enumerate(st["options"], 1)]
        reply["actions"].append(dict(type="savings", data=[{k: v for k, v in o.items() if k != "plan"} for o in st["options"]]))
        return finish("Ranked ways to lower the cost:\n" + "\n".join(lines), suggestions=_chips("Apply option 1", "Apply option 2", "Apply option 3"))

    if intent == "apply":
        import re as _re
        m = _re.search(r"(\d+)", text_l)
        i = int(m.group(1)) - 1 if m else 0
        if not st.get("options") or not 0 <= i < len(st["options"]):
            return finish("Ask me to make the trip cheaper first, then choose one of the numbered options.")
        o = st["options"][i]
        st["previous_plan"], st["plan"], st["options"] = st["plan"], o["plan"], []
        st["plan"]["version"] = (st["previous_plan"].get("version", 1)) + 1
        reply["actions"].append(dict(type="plan", plan=st["plan"]))
        return finish(f"Applied: {o['description']}. New estimated total {inr(o['new_total'])}. Say \"undo\" to compare with the previous version.", suggestions=_chips("Undo", "Show cost breakdown"))

    # ---------------------------------------------------------------- modify (re-plan)
    if intent == "modify":
        plan = st["plan"]
        changes: dict = {}
        for k in ("budget", "duration_days", "pace", "accommodation", "transport", "travellers", "start_date"):
            if k in ent:
                changes[k] = ent[k]
        for k in ("elderly", "accessibility_required", "children"):
            if ent.get(k):
                changes[k] = True
        if ent.get("elderly"):
            changes["pace"] = "relaxed"
        if "exclude_activities" in ent:
            changes["exclude_activities"] = ent["exclude_activities"]
        add = [i for i in ent.get("interests", []) if i not in st["prefs"].get("interests", [])]
        if add:
            changes["add_interests"] = add
        if not changes:
            return finish("What would you like to change - the budget, number of days, an activity to remove, or the pace?", suggestions=_chips("My budget dropped to ₹6,000", "I have only two days now", "Remove trekking"))
        res = eng.replan(plan, changes)
        if not res["ok"]:
            return finish(f"I could not apply that: {res['error']}")
        st["previous_plan"], st["plan"], st["options"] = plan, res["plan"], []
        st["prefs"] = res["plan"]["prefs"]
        reply["actions"].append(dict(type="plan", plan=st["plan"], summary=res["summary"]))
        sm = res["summary"]
        txt = "Updated your plan:\n" + "\n".join(sm["lines"])
        if not sm["added"] and not sm["removed"]:
            if add:
                n = sum(1 for a in ds.dest_attractions(plan["destination_id"]) if set(add) & set(a["tags"]))
                txt += f"\nNo activities changed: the data lists only {n} {'/'.join(add)} attraction(s) for {plan['destination_name']}, and {'it is' if n == 1 else 'they are'} already in your plan or cannot fit."
            elif changes.get("exclude_activities"):
                txt += f"\nNothing in the plan matched {', '.join(changes['exclude_activities'])}, so no activity was removed."
        if "optimiser" in sm:
            txt += "\n" + sm["optimiser"]["message"]
            if not sm["optimiser"]["resolved"] and st["plan"]["prefs"].get("budget"):   # Plan B: cheaper destinations that do fit
                alt_prefs = Preferences(**{**st["plan"]["prefs"], "destination": None})
                alts = [r for r in eng.recommend(alt_prefs, top_n=8)["ranked"] if r["id"] != plan["destination_id"] and r["cost"]["typical"] and r["cost"]["typical"] <= alt_prefs.budget][:2]
                if alts:
                    txt += "\nPlan B within your budget: " + "; ".join(f"{r['name']} (about {inr(r['cost']['typical'])})" for r in alts) + "."
                    reply["suggestions"] = [f"Plan a trip to {r['name']}" for r in alts]
        if st["plan"]["notes"]:
            txt += "\nNote: " + " ".join(st["plan"]["notes"][:2])
        if ent.get("elderly") and Preferences(**st["prefs"]).travellers == 1 and "travellers" not in ent:
            txt += "\nHow many of you are travelling? I have assumed 1, and costs scale with the group size."
        return finish(txt + "\nSay \"undo\" to go back.", suggestions=reply["suggestions"] or _chips("Undo", "Show cost breakdown", "Make it cheaper"))

    return finish("I am not sure I caught that. I can recommend places, compare them, explain a pick, build an itinerary or re-plan it. Try one of these:",
                  suggestions=_chips("Somewhere cool for 3 days under ₹10,000", "Compare Ooty and Coorg", "Beaches and food", "What can you do?"))
