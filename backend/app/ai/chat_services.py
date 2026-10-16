"""Chat feature services: each function calls the real engine modules and returns structured data (never prose invented from nothing).

Accommodation records in the shipped dataset are FICTIONAL SAMPLES with no star rating, so star requests are answered with the closest
tier and an explicit statement that star ratings cannot be verified.
"""
from __future__ import annotations

import re

from . import accommodation as acc
from . import transport as trn
from . import nlp
from .data_loader import TIERS
from .geo import haversine_km

SAMPLE_NOTE = "Sample data: these are fictional placeholder properties. Prices are estimates; star ratings, reviews, availability and booking links are not in the dataset."
STAR_TIERS = {5: ["premium"], 4: ["premium", "midrange"], 3: ["midrange"], 2: ["budget"], 1: ["hostel", "budget"]}
STAR_WORD = {1: "one-star", 2: "two-star", 3: "three-star", 4: "four-star", 5: "five-star"}


def inr(x) -> str:
    return f"₹{int(round(x)):,}"


def resolve_focus(st: dict, ent: dict) -> tuple[str | None, bool]:
    """Destination the user is talking about. Returns (id, assumed). 'there' / 'it' resolve to the remembered focus."""
    if ent.get("destinations"):
        return ent["destinations"][0], False
    for cand in (st.get("focus"), (st.get("plan") or {}).get("destination_id"), st["prefs"].get("destination")):
        if cand:
            return cand, False
    if st.get("last_ranked"):
        return st["last_ranked"][0], True
    return None, False


def nearby_destinations_with_stays(ds, did: str, limit: int = 3, max_km: float = 400) -> list[dict]:
    d = ds.destinations[did]
    out = []
    for o in ds.destinations.values():
        if o["id"] == did or not ds.dest_stays(o["id"]):
            continue
        km = haversine_km(d["lat"], d["lon"], o["lat"], o["lon"])
        if km <= max_km:
            out.append(dict(id=o["id"], name=o["name"], km=round(km)))
    return sorted(out, key=lambda x: x["km"])[:limit]


def nearest_destinations_with_stays(ds, lat: float, lon: float, limit: int = 3, max_km: float = 700) -> list[dict]:
    """Destinations that have stay records, nearest first to an arbitrary point (e.g. a starting city). Offered as options, never substituted."""
    out = []
    for o in ds.destinations.values():
        if ds.dest_stays(o["id"]):
            km = haversine_km(lat, lon, o["lat"], o["lon"])
            if km <= max_km:
                out.append(dict(id=o["id"], name=o["name"], km=round(km)))
    return sorted(out, key=lambda x: x["km"])[:limit]


def _tiers_for(ent: dict) -> list[str] | None:
    if ent.get("stars"):
        return STAR_TIERS[ent["stars"]]
    pp = ent.get("price_pref")
    if pp == "high":
        return ["premium"]
    if pp == "mid":
        return ["midrange"]
    if pp == "low":
        return ["hostel", "budget", "homestay"]
    st = ent.get("stay_type")
    if st == "hostel":
        return ["hostel"]
    if st == "homestay":
        return ["homestay"]
    if st == "resort":
        return ["premium"]
    if ent.get("accommodation") in TIERS:
        return [ent["accommodation"]]
    return None


def search_stays(eng, st: dict, ent: dict, did: str, stay_filter: dict | None = None, limit: int = 3, only_ids: set | None = None) -> dict:
    """Retrieve + filter + rank real accommodation records. Relaxes constraints one at a time and says exactly what was relaxed."""
    ds = eng.ds
    prefs = st["prefs"]
    f = {} if only_ids else dict(stay_filter or {})       # a named property overrides tier/price filters: the user asked for that record
    for k in ("stars", "price_pref", "stay_type", "amenities", "accommodation"):
        if k in ent and not only_ids:
            f[k] = ent[k]
    cap_ = None if only_ids else (ent.get("max_price") if "max_price" in ent else f.get("max_price"))
    if cap_ is None and ent.get("budget") and not only_ids:
        cap_ = ent["budget"]                 # in a stay search a stated amount is a per-night cap, not the trip budget (shown in "What I understood")
    f["max_price"] = cap_
    travellers = ent.get("travellers") or prefs.get("travellers") or 1
    plan = st.get("plan") if (st.get("plan") or {}).get("destination_id") == did else None
    nights = ent.get("nights") or (plan["costs"]["nights"] if plan else None) or (ent["duration_days"] - 1 if (ent.get("duration_days") or 0) > 1 else None) or 2
    nights_assumed = not (ent.get("nights") or plan or ent.get("duration_days"))
    notes: list[str] = []
    planned = None
    near = None
    if ent.get("near_plan") and plan:
        planned = [a for d in plan["days"] for a in d["activity_ids"]]
        notes.append("Ranked by distance to the attractions in your current itinerary.")
    elif ent.get("near_plan"):
        notes.append("You have no itinerary yet, so I could not rank by proximity to planned attractions.")
    phrase = ent.get("near_phrase") or f.get("near_phrase")
    if phrase:
        near = nlp.resolve_landmark(ds, phrase, did)
        if near and near["destination_id"] != did:
            notes.append(f"{near['name']} is in {ds.destinations[near['destination_id']]['name']}, not {ds.destinations[did]['name']}; ignoring that location.")
            near = None
        elif not near:
            notes.append(f"I could not find “{phrase}” among the attractions in the dataset, so I could not rank by distance to it.")
        f["near_phrase"] = phrase
    base = acc.options(ds, did, travellers, nights, f.get("accommodation") if f.get("accommodation") in TIERS else None, bool(prefs.get("accessibility_required")), planned)
    total_records = len(base)
    if only_ids:
        base = [s for s in base if s["id"] in only_ids]
    if near:
        for s in base:
            s["distance_to_target_km"] = round(haversine_km(s["lat"], s["lon"], near["lat"], near["lon"]), 1)
            s["target_name"] = near["name"]
    tiers = _tiers_for(f)
    pool = list(base)
    exact = list(pool)
    if tiers:
        exact = [s for s in exact if s["tier"] in tiers]
    if f.get("max_price"):
        exact = [s for s in exact if s["price_inr"] <= f["max_price"]]
    if f.get("amenities"):
        am = [s for s in exact if all(a in s["amenities"] for a in f["amenities"])]
        if am:
            exact = am
        else:
            notes.append(f"No matching property lists {', '.join(f['amenities'])}; amenity filter dropped.")
    relaxed = False
    if not exact:
        relaxed = True
        under = [s for s in pool if not f.get("max_price") or s["price_inr"] <= f["max_price"]]
        if tiers and under:
            notes.append(f"No {'/'.join(tiers)}-tier record fits your filters; showing the closest options instead.")
            exact = under
        elif f.get("max_price"):
            notes.append(f"Nothing in the dataset is priced at or below {inr(f['max_price'])} per night here; showing the cheapest available.")
            exact = sorted(pool, key=lambda s: s["price_inr"])
        else:
            exact = pool
    # ranking
    if near or planned:
        exact.sort(key=lambda s: (s.get("distance_to_target_km", s.get("avg_distance_to_planned_km") or 99), s["price_inr"]))
    elif f.get("price_pref") == "low" or f.get("max_price"):
        exact.sort(key=lambda s: (s["price_inr"], -(s.get("comfort") or 0)))
    elif tiers and "premium" in tiers or f.get("stars", 0) >= 4:
        exact.sort(key=lambda s: (-(s.get("comfort") or 0), s["price_inr"]))
    shown = exact[:limit]
    for s in shown:
        s["match"] = "exact" if (not tiers or s["tier"] in tiers) and not relaxed else "closest"
    n_exact = len(shown)
    # fill "a few" with the next-closest tier so the user sees a useful set, clearly labelled
    if tiers and len(shown) < min(limit, 3) and not relaxed and not f.get("max_price"):
        order = {t: i for i, t in enumerate(TIERS)}
        anchor = max(order[t] for t in tiers)
        alts = sorted([s for s in pool if s["tier"] not in tiers and s["id"] not in {x["id"] for x in shown}], key=lambda s: (abs(order[s["tier"]] - anchor), -order[s["tier"]]))
        for s in alts[: min(limit, 3) - len(shown)]:
            s["match"] = "alternative"
            shown.append(s)
        if any(s["match"] == "alternative" for s in shown):
            notes.append(f"The dataset has {n_exact} {'/'.join(tiers)}-tier record(s) for {ds.destinations[did]['name']}; the rest are the nearest alternative tiers.")
    if f.get("stars"):
        notes.insert(0, f"The dataset does not record star ratings, so I cannot verify any property as {STAR_WORD[f['stars']]}. "
                        f"Closest by tier: {'/'.join(STAR_TIERS[f['stars']])}.")
    data = dict(destination_id=did, destination_name=ds.destinations[did]["name"], filters={k: v for k, v in f.items() if v not in (None, [], "")},
                tiers=tiers, nights=nights, nights_assumed=nights_assumed, travellers=travellers, results=shown, notes=notes, relaxed=relaxed,
                total_records=total_records, sample=True, disclaimer=SAMPLE_NOTE, stars_verified=False, target=(near or {}).get("name"))
    return data


def stays_text(d: dict) -> str:
    name = d["destination_name"]
    if not d["results"]:
        return f"The dataset has no accommodation records for {name}."
    f = d["filters"]
    kind = "budget-friendly " if f.get("price_pref") == "low" else "luxury " if f.get("price_pref") == "high" and not f.get("stars") else ""
    head = f"Here {'is' if len(d['results']) == 1 else 'are'} {len(d['results'])} {kind}option{'' if len(d['results']) == 1 else 's'} in {name}" + (f" for a {STAR_WORD[f['stars']]} request" if f.get("stars") else "")
    if d.get("target"):
        head += f", nearest to {d['target']} first"
    lines = [head + " (sample records, prices are estimates):"]
    for i, s in enumerate(d["results"], 1):
        unit = "bed" if s["price_unit"] == "per_bed" else "room"
        extra = f", {s['distance_to_target_km']} km from {s['target_name']}" if s.get("distance_to_target_km") is not None else (f", ~{s['avg_distance_to_planned_km']} km from the main sights" if s.get("avg_distance_to_planned_km") is not None else "")
        tag = " [closest tier]" if s.get("match") == "alternative" else ""
        lines.append(f"{i}. {s['name']} - {s['tier']} tier{tag}, {inr(s['price_inr'])} per {unit} per night (about {inr(s['total_inr'])} for {d['nights']} night(s), {d['travellers']} guest(s)){extra}.")
    for n in d["notes"]:
        lines.append(n)
    lines.append(SAMPLE_NOTE)
    return "\n".join(lines)


# ---------------------------------------------------------------- transport / route
def transport_data(eng, origin: str, did: str, travellers: int, days: int | None, modes: list[str] | None = None) -> dict:
    ds = eng.ds
    opts = trn.options(ds, origin, did, None, travellers, trip_days=days)
    out = dict(origin=origin, origin_name=ds.origins[origin]["name"], destination_id=did, destination_name=ds.destinations[did]["name"], travellers=travellers, options=opts,
               preferred_modes=modes or [])
    if opts:
        out["cheapest"] = min(opts, key=lambda o: o["round_trip_group_inr"])["mode"]
        out["fastest"] = min(opts, key=lambda o: o["one_way_hours"])["mode"]
        out["most_comfortable"] = max(opts, key=lambda o: (o["comfort"] or 0, -o["round_trip_group_inr"]))["mode"]
        out["best_overall"] = opts[0]["mode"]
    return out


def transport_text(d: dict) -> str:
    if not d["options"]:
        return f"The dataset has no transport link from {d['origin_name']} to {d['destination_name']}."
    o = {x["mode"]: x for x in d["options"]}
    lines = [f"From {d['origin_name']} to {d['destination_name']} the dataset models {len(o)} option(s) (estimates from a distance model, not live fares or timetables):"]
    for x in d["options"]:
        tags = [t for t, k in (("cheapest", "cheapest"), ("fastest", "fastest"), ("most comfortable", "most_comfortable"), ("best overall", "best_overall")) if d.get(k) == x["mode"]]
        lines.append(f"- {x['mode'].title()}: about {x['one_way_hours']} h each way, {inr(x['per_person_round_trip_inr'])} per person return ({inr(x['round_trip_group_inr'])} for {d['travellers']}), comfort {x['comfort']}/5" + (f" - {', '.join(tags)}" if tags else ""))
    return "\n".join(lines)


def route_data(eng, a: str, b: str) -> dict | None:
    g = eng.graph
    if a not in g.coords or b not in g.coords:
        return None
    r = eng.route_demo(a, b, "time")
    x = r["astar"]
    if not x["found"]:
        return None
    return dict(path=x["labels"], km=x["total_km"], hours=x["total_hours"], note="Modelled road network (straight-line x 1.3), not live routing.")


# ---------------------------------------------------------------- activities
def activities_data(eng, did: str, ent: dict, limit: int = 5) -> dict:
    ds = eng.ds
    attrs = ds.dest_attractions(did)
    want = ent.get("interests") or []
    near = None
    notes = []
    if ent.get("near_phrase"):
        near = nlp.resolve_landmark(ds, ent["near_phrase"], did)
        if near and near["destination_id"] != did:
            near = None
        if not near:
            notes.append(f"I could not find “{ent['near_phrase']}” in the dataset, so results are not ranked by proximity.")
    pool = attrs
    if want:
        m = [a for a in attrs if set(a["tags"]) & set(want)]
        if m:
            pool = m
        else:
            notes.append(f"No {'/'.join(want)} attractions are recorded for {ds.destinations[did]['name']}; showing the most significant ones instead.")
    if near:
        pool = sorted([a for a in pool if a["id"] != near["id"]], key=lambda a: haversine_km(near["lat"], near["lon"], a["lat"], a["lon"]))
    else:
        pool = sorted(pool, key=lambda a: (-a["significance"], a["name"]))
    items = []
    for a in pool[:limit]:
        it = dict(id=a["id"], name=a["name"], tags=a["tags"], duration_min=a["duration_min"], fee_inr=a["fee_inr"], intensity=a["intensity"], accessible=a["accessible"],
                  best_slot=a["best_slot"], description=a["description"])
        if near:
            it["distance_km"] = round(haversine_km(near["lat"], near["lon"], a["lat"], a["lon"]), 1)
        items.append(it)
    return dict(destination_id=did, destination_name=ds.destinations[did]["name"], items=items, total=len(attrs), near=(near or {}).get("name"), filter=want, notes=notes)


def activities_text(d: dict) -> str:
    if not d["items"]:
        return f"The dataset lists no attractions for {d['destination_name']}."
    head = f"Top things to do in {d['destination_name']}" + (f" near {d['near']}" if d["near"] else "") + (f" ({'/'.join(d['filter'])})" if d["filter"] else "") + ":"
    lines = [head]
    for i, a in enumerate(d["items"], 1):
        fee = f"entry about {inr(a['fee_inr'])}" if a["fee_inr"] else "no entry fee recorded"
        lines.append(f"{i}. {a['name']} - {a['description']} (about {int(a['duration_min'])} min, {fee}" + (f", {a['distance_km']} km away" if a.get("distance_km") is not None else "") + ")")
    return "\n".join(lines + d["notes"])


# ---------------------------------------------------------------- weather / season
def weather_data(eng, did: str, ent: dict) -> dict:
    d = eng.ds.destinations[did]
    season = ent.get("season")
    return dict(destination_id=did, destination_name=d["name"], climate=d.get("climate"), best_seasons=d.get("best_seasons") or [], season_asked=season,
                season_ok=(season in (d.get("best_seasons") or [])) if season else None, live_weather=False,
                limitation="No live weather or forecast integration: this is the typical climate and best seasons recorded in the dataset, not current conditions.")


def weather_text(w: dict) -> str:
    if not w["climate"] and not w["best_seasons"]:
        base = f"The dataset has no climate or season information for {w['destination_name']}."
    else:
        base = f"{w['destination_name']}: recorded climate is {w['climate'] or 'unknown'}; best seasons in the dataset are {', '.join(w['best_seasons']) or 'not recorded'}."
        if w["season_asked"]:
            base += f" {w['season_asked'].title()} is {'' if w['season_ok'] else 'not '}listed among the best seasons."
    return base + " " + w["limitation"]


# ---------------------------------------------------------------- suggestions
def suggestions_for(st: dict, ds, shown: str | None, did: str | None = None) -> list[str]:
    name = ds.destinations[did]["name"] if did in ds.destinations else None
    prefs = st["prefs"]
    plan = st.get("plan")
    origin = ds.origins.get(prefs.get("origin") or "", {}).get("name")
    days = prefs.get("duration_days") or 3
    attrs = sorted(ds.dest_attractions(did), key=lambda a: (-a["significance"], a["name"])) if name else []
    lake = next((a["name"] for a in attrs if re.search(r"\b(lake|beach|fort|temple|palace)\b", a["name"].lower())), attrs[0]["name"] if attrs else None)
    out: list[str] = []
    if shown == "plan" and plan:
        trek = any("adventure" in ds.attractions[a]["tags"] for d in plan["days"] for a in d["activity_ids"] if a in ds.attractions)
        out = ["Replace trekking with sightseeing" if trek else "Add more food experiences", "Show my budget breakdown", "Find accommodation near these attractions", "Make the schedule more relaxed", "Reduce the total cost"]
    elif shown == "stays" and name:
        out = ["Those are too expensive", f"Show budget accommodation in {name}", f"Plan a {days}-day itinerary for {name}", f"What are the best things to do in {name}?"]
        if origin:
            out.append(f"How do I get to {name} from {origin}?")
    elif shown == "transport" and name:
        out = [f"Find hotels in {name}", f"Plan a {days}-day trip to {name}", f"What is the best time to visit {name}?", f"What are the best things to do in {name}?"]
    elif shown == "activities" and name:
        out = [f"Find hotels near {lake}" if lake else f"Find hotels in {name}", f"Plan a {days}-day itinerary for {name}", f"What is the weather like in {name}?"]
        if origin:
            out.append(f"Compare transport options from {origin}")
    elif shown == "weather" and name:
        out = [f"Find hotels in {name}", f"What are the best things to do in {name}?", f"Plan a {days}-day trip to {name}"]
    elif shown in ("recs", "details", "compare") and name:
        out = [f"Find luxury hotels in {name}", f"Show me budget accommodation in {name}", f"Plan a {days}-day itinerary for {name}"]
        out.append(f"Compare transport options from {origin}" if origin else f"What are the best things to do in {name}?")
        if lake:
            out.append(f"Find attractions near {lake}")
        out.append("Make this trip cheaper") if plan else None
    elif plan:
        out = ["Show my budget breakdown", "Make it cheaper", "Find accommodation near these attractions"]
    return [x for x in out if x][:5]
