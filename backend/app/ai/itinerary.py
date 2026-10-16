"""Search-based itinerary generation (beam search) and day scheduling.

Problem formulation
-------------------
State   : (completed days, activities in the current day, minutes used today, current
          location, visited set, accumulated value, accumulated cost, whether lunch has
          been taken). Each trip day starts and ends at the accommodation.
Actions : VISIT(a) for an unvisited attraction `a`, or END_DAY.
Feasible: used + travel(loc->a) + duration(a) + travel(a->hotel) <= day limit (pace-based);
          activities per day <= pace cap; accessibility / intensity / exclusions respected;
          no attraction is visited twice.
Cost    : value(a) (interest match, significance, slot fit, intensity fit)
          - lambda_travel x travel hours - lambda_cost x spend (fees + local transport).
Goal    : all trip days closed.
Search  : beam search (width from config). f(n) = g(n) + h(n), where h(n) is an optimistic
          bound: the sum of the best remaining attraction values that could still fit.
          Beam search is a HEURISTIC method: the result is good, not proven globally optimal.
Complexity: O(D x K x B x N) expansions, D days, K steps/day, B beam width, N attractions.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

from .data_loader import Dataset
from .geo import haversine_km, local_leg

DAY_START_MIN = 9 * 60            # 09:00
LUNCH_FROM, LUNCH_MIN = 12 * 60 + 45, 60
SLOT_BOUNDS = (12 * 60 + 30, 17 * 60 + 30)   # morning < 12:30 <= afternoon < 17:30 <= evening
VEHICLE_SEATS = 4
EDGE_TRAVEL_MIN_WALK_KM = 1.2


def slot_of(clock_min: float) -> str:
    return "morning" if clock_min < SLOT_BOUNDS[0] else "afternoon" if clock_min < SLOT_BOUNDS[1] else "evening"


def fmt_clock(m: float) -> str:
    m = int(round(m)); return f"{(m // 60) % 24:02d}:{m % 60:02d}"


# ------------------------------------------------------------ exclusions / eligibility
def matches_exclusion(a: dict, kw: str) -> bool:
    k = kw.lower().strip()
    if not k:
        return False
    name = a["name"].lower()
    if k in name or k in a["tags"]:
        return True
    if k in ("trekking", "trek", "hiking", "hike"):
        return ("adventure" in a["tags"] and a["intensity"] >= 2) or any(w in name for w in ("trek", "climb", "hike", "falls trek"))
    if k in ("shopping", "shop"):
        return "shopping" in a["tags"]
    return False


def eligible(ds: Dataset, dest_id: str, prefs, cfg: dict) -> list[dict]:
    out = []
    strict = prefs.elderly or prefs.pace == "relaxed" and prefs.elderly
    for a in ds.dest_attractions(dest_id):
        if any(matches_exclusion(a, kw) for kw in prefs.excluded_activities):
            continue
        if prefs.accessibility_required and a.get("accessible") is False:
            continue
        if prefs.elderly and a["intensity"] >= 3:
            continue
        if prefs.elderly and a.get("accessible") is False and a["intensity"] >= 2:
            continue
        out.append(a)
    return out


def attraction_value(a: dict, prefs, limited_budget: bool) -> float:
    interests = set(prefs.interests)
    match = len(interests & set(a["tags"])) / len(interests) if interests else 0.5
    v = 2.2 * match + 0.8 * a["significance"]
    if prefs.elderly or prefs.pace == "relaxed":
        v -= 0.5 * (a["intensity"] - 1)
    if prefs.accessibility_required and a.get("accessible") is None:
        v -= 0.4  # unknown accessibility is not treated as a match
    if limited_budget and a["fee_inr"] > 0:
        v -= min(a["fee_inr"] / 800.0, 0.8)
    return v


# ------------------------------------------------------------ day scheduling (deterministic)
def _hop(ds_attr_from: tuple[float, float], to: tuple[float, float], cfg: dict) -> tuple[float, float, str]:
    straight = haversine_km(*ds_attr_from, *to)
    km, minutes = local_leg(straight, cfg["local_road_factor"])
    if km < EDGE_TRAVEL_MIN_WALK_KM:
        return km, max(km / 4.5 * 60, 3.0), "walk"
    return km, minutes, "auto / taxi"


def schedule_day(ds: Dataset, cfg: dict, hotel: tuple[float, float], activity_ids: list[str], travellers: int,
                 day_start: float = DAY_START_MIN, rest_breaks: bool = False) -> dict:
    """Turn an ordered list of attraction ids into a timed schedule with legs, meals and costs."""
    items, clock, loc = [], float(day_start), hotel
    km_total = travel_min = fee_total = act_min = 0.0
    paid_km = 0.0
    lunch_done = False
    vehicles = math.ceil(travellers / VEHICLE_SEATS)
    for n, aid in enumerate(activity_ids):
        a = ds.attractions[aid]
        km, mins, how = _hop(loc, (a["lat"], a["lon"]), cfg)
        if clock + mins >= LUNCH_FROM and not lunch_done:
            items.append(dict(kind="meal", title="Lunch break", start=fmt_clock(clock), end=fmt_clock(clock + LUNCH_MIN), minutes=LUNCH_MIN))
            clock += LUNCH_MIN; lunch_done = True
        if mins > 0 and loc is not None and (km > 0.05):
            items.append(dict(kind="travel", title=f"{how} to {a['name']}", start=fmt_clock(clock), end=fmt_clock(clock + mins),
                              minutes=round(mins), km=round(km, 1), mode=how))
        km_total += km; travel_min += mins
        if how != "walk":
            paid_km += km
        clock += mins
        fee = a["fee_inr"] * travellers
        items.append(dict(kind="activity", attraction_id=aid, title=a["name"], start=fmt_clock(clock), end=fmt_clock(clock + a["duration_min"]),
                          minutes=int(a["duration_min"]), slot=slot_of(clock), lat=a["lat"], lon=a["lon"], tags=a["tags"], fee_per_person=a["fee_inr"],
                          fee_group=round(fee), fee_known=a.get("fee_known", True), intensity=a["intensity"], accessible=a.get("accessible"),
                          description=a.get("description", "")))
        fee_total += fee; act_min += a["duration_min"]; clock += a["duration_min"]; loc = (a["lat"], a["lon"])
        if rest_breaks and n == 1 and len(activity_ids) > 2:
            items.append(dict(kind="rest", title="Rest break", start=fmt_clock(clock), end=fmt_clock(clock + 30), minutes=30)); clock += 30
    if activity_ids:  # return leg
        km, mins, how = _hop(loc, hotel, cfg)
        if km > 0.05:
            items.append(dict(kind="travel", title=f"{how} back to your stay", start=fmt_clock(clock), end=fmt_clock(clock + mins), minutes=round(mins), km=round(km, 1), mode=how))
        km_total += km; travel_min += mins; clock += mins
        if how != "walk":
            paid_km += km
        if clock < 19 * 60:
            clock = max(clock, 19 * 60)
        items.append(dict(kind="meal", title="Dinner and rest", start=fmt_clock(clock), end=fmt_clock(clock + 60), minutes=60))
    local_cost = paid_km * cfg["local_km_rate"] * vehicles
    return dict(items=items, activity_minutes=int(act_min), travel_minutes=int(round(travel_min)), local_km=round(km_total, 1),
                local_cost=round(local_cost), fee_total=round(fee_total), end_time=fmt_clock(clock))


# ------------------------------------------------------------ beam search
@dataclass(frozen=True)
class _S:
    day: int
    today: tuple
    done: tuple
    used: float
    loc: tuple
    visited: frozenset
    value: float
    spend: float
    travel: float
    lunch: bool


def _day_limit(prefs, cfg: dict, day_idx: int, n_days: int) -> tuple[float, int]:
    p = cfg["pace"][prefs.pace]
    lim, cap = p["limit_min"], p["max_activities"]
    if prefs.elderly:
        lim, cap = min(lim, 360), min(cap, 3)
    if n_days >= 2 and day_idx in (0, n_days - 1):
        lim *= 0.75  # arrival and departure days carry travel overhead (documented assumption)
    return lim, cap


def generate_itinerary(ds: Dataset, cfg: dict, prefs, dest_id: str, hotel: tuple[float, float], n_days: int,
                       limited_budget: bool = False, locked: dict[int, list[str]] | None = None, travel_weight: float = 0.35,
                       cost_weight: float | None = None, beam_width: int | None = None, trace_steps: int = 10,
                       banned_ids: set[str] | None = None) -> dict:
    banned_ids = banned_ids or set()
    pool = [a for a in eligible(ds, dest_id, prefs, cfg) if a["id"] not in banned_ids]
    by_id = {a["id"]: a for a in pool}
    vals = {a["id"]: attraction_value(a, prefs, limited_budget) for a in pool}
    B = beam_width or cfg["beam_width"]
    vehicles = math.ceil(prefs.travellers / VEHICLE_SEATS)
    lam_cost = cost_weight if cost_weight is not None else (0.0012 if limited_budget else 0.0004)
    locked = {d: [i for i in ids if i in by_id] for d, ids in (locked or {}).items()}
    locked_all = {i for ids in locked.values() for i in ids}
    notes: list[str] = []
    expanded = generated = 0
    trace: list[dict] = []

    def leg(loc, a):
        return _hop(loc, (a["lat"], a["lon"]), cfg)

    def add(s: _S, aid: str, day_limit: float, cap: int, enforce: bool = True) -> _S | None:
        a = by_id[aid]
        km, mins, how = leg(s.loc, a)
        back_km, back_min, _ = _hop((a["lat"], a["lon"]), hotel, cfg)
        clock = DAY_START_MIN + s.used + (LUNCH_MIN if s.lunch else 0)
        lunch = s.lunch
        if not lunch and clock + mins >= LUNCH_FROM:
            lunch = True
        used = s.used + mins + a["duration_min"]
        if enforce and (len(s.today) + 1 > cap or used + back_min > day_limit):
            return None
        start_clock = DAY_START_MIN + s.used + mins + (LUNCH_MIN if lunch else 0)
        bonus = 0.0
        if a["best_slot"] != "any":
            bonus = 0.5 if a["best_slot"] == slot_of(start_clock) else -0.4
        spend = a["fee_inr"] * prefs.travellers + (km * cfg["local_km_rate"] * vehicles if how != "walk" else 0.0)
        val = vals[aid] + bonus - travel_weight * mins / 60.0 - lam_cost * spend
        return _S(s.day, s.today + (aid,), s.done, used, (a["lat"], a["lon"]), s.visited | {aid}, s.value + val, s.spend + spend, s.travel + mins, lunch)

    def seed_day(s: _S, d: int) -> _S:
        """Start day d, placing its locked activities first (kept even if slightly over the limit)."""
        lim, cap = _day_limit(prefs, cfg, d, n_days)
        s = _S(d, (), s.done, 0.0, hotel, s.visited | frozenset(locked.get(d, [])), s.value, s.spend, s.travel, False)
        placed = _S(d, (), s.done, 0.0, hotel, s.visited, s.value, s.spend, s.travel, False)
        for aid in locked.get(d, []):
            nxt = add(placed, aid, lim, cap, enforce=True)
            if nxt is None:
                notes.append(f"'{by_id[aid].get('name', aid)}' no longer fits day {d + 1} under the current pace and was released.")
                placed = _S(d, placed.today, placed.done, placed.used, placed.loc, placed.visited - {aid}, placed.value, placed.spend, placed.travel, placed.lunch)
            else:
                placed = nxt
        return placed

    def h(s: _S) -> float:
        remaining = sorted((v for i, v in vals.items() if i not in s.visited and v > 0), reverse=True)
        slots = 0
        for d in range(s.day, n_days):
            lim, cap = _day_limit(prefs, cfg, d, n_days)
            slots += cap - (len(s.today) if d == s.day else 0)
        return sum(remaining[: max(slots, 0)])

    start = _S(0, (), (), 0.0, hotel, frozenset(locked_all), 0.0, 0.0, 0.0, False)
    start = seed_day(start, 0)
    beam, finished, step = [start], [], 0
    while beam and step < n_days * (max(p["max_activities"] for p in cfg["pace"].values()) + 2) + 4:
        step += 1; nxt_states: dict[tuple, _S] = {}
        for s in beam:
            expanded += 1
            lim, cap = _day_limit(prefs, cfg, s.day, n_days)
            cands = []
            for aid in sorted(by_id):
                if aid in s.visited:
                    continue
                n = add(s, aid, lim, cap)
                if n is not None:
                    cands.append(n)
            moves = list(cands)
            if s.today or not cands:  # END_DAY allowed when the day has content or nothing else fits
                done = s.done + (s.today,)
                if s.day + 1 >= n_days:
                    finished.append(_S(s.day + 1, (), done, s.used, hotel, s.visited, s.value, s.spend, s.travel, s.lunch))
                else:
                    e = _S(s.day + 1, (), done, 0.0, hotel, s.visited, s.value, s.spend, s.travel, False)
                    moves.append(seed_day(e, s.day + 1))
            for m in moves:
                generated += 1
                k = (m.day, m.done, m.today)
                if k not in nxt_states or nxt_states[k].value < m.value:
                    nxt_states[k] = m
        ranked = sorted(nxt_states.values(), key=lambda t: (-(t.value + h(t)), t.done, t.today))
        beam = ranked[:B]
        if step <= trace_steps and beam:
            trace.append(dict(step=step, beam_size=len(beam), candidates=len(nxt_states), top=[
                dict(day=t.day + 1, plan=[by_id[i]["name"] for i in t.today] if t.today else [by_id[i]["name"] for i in (t.done[-1] if t.done else ())],
                     g=round(t.value, 2), h=round(h(t), 2), f=round(t.value + h(t), 2)) for t in beam[:3]]))
        if finished and not beam:
            break
    if not finished:  # defensive: close whatever is in the beam
        finished = [_S(n_days, (), s.done + (s.today,) + tuple(() for _ in range(n_days - len(s.done) - 1)), s.used, hotel, s.visited, s.value, s.spend, s.travel, s.lunch) for s in beam]
    best = sorted(finished, key=lambda t: (-t.value, t.done))[0]
    days = list(best.done)[:n_days]
    while len(days) < n_days:
        days.append(())
    total_acts = sum(len(d) for d in days)
    if total_acts == 0:
        notes.append("No attraction in the dataset satisfies the current constraints for this destination.")
    elif any(len(d) == 0 for d in days):
        notes.append("Fewer eligible attractions than available time slots; some days are light because the dataset has no more suitable entries.")
    return dict(days=[dict(day=i + 1, activity_ids=list(d)) for i, d in enumerate(days)],
                search=dict(algorithm="beam search", beam_width=B, expanded=expanded, generated=generated, best_score=round(best.value, 3),
                            heuristic="optimistic sum of best remaining attraction values that can still fit", optimal=False,
                            note="Heuristic search: good plans, not proven globally optimal.", trace=trace,
                            eligible_attractions=len(pool)),
                notes=notes)
