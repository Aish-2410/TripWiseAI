"""Transport matching. Only options present in the dataset are returned.

Prices/durations come from the documented distance model (dataset basis
"distance_model_v1"): they are ESTIMATES, not live fares or timetables, and nothing
here books or confirms anything.
"""
from __future__ import annotations

import math

from .data_loader import Dataset

SEATS_PER_VEHICLE = 4
ACCESSIBILITY_NOTE = {"train": "varies by station and coach; verify with the operator", "bus": "step-entry vehicles are common; verify",
                      "flight": "airlines offer assistance on request; verify", "car": "private vehicle; most flexible for mobility needs"}


def round_trip_total(link: dict, travellers: int) -> float:
    """Group round-trip cost. Per-person fares scale with travellers; per-vehicle fares scale with vehicles."""
    if link.get("price_basis") == "per_vehicle":
        return float(link["price_inr"]) * math.ceil(travellers / SEATS_PER_VEHICLE) * 2
    return float(link["price_inr"]) * travellers * 2


def options(ds: Dataset, origin: str, dest: str, modes: list[str] | None, travellers: int, limited_budget: bool = False, trip_days: int | None = None) -> list[dict]:
    links = ds.links(origin, dest, modes or None)
    out = []
    for l in links:
        total = round_trip_total(l, travellers)
        out.append(dict(
            mode=l["mode"], origin=origin, destination=dest, distance_km=l["distance_km"], one_way_hours=l["duration_h"],
            price_inr=l["price_inr"], price_basis=l.get("price_basis", "per_person"), round_trip_group_inr=round(total),
            per_person_round_trip_inr=round(total / travellers), comfort=l.get("comfort"),
            accessibility_note=ACCESSIBILITY_NOTE.get(l["mode"]), basis=l.get("basis", "estimate"),
            label="Estimated from a distance model - not a live fare or timetable"))
    if not out:
        return out
    lo_p, hi_p = min(o["round_trip_group_inr"] for o in out), max(o["round_trip_group_inr"] for o in out)
    lo_t, hi_t = min(o["one_way_hours"] for o in out), max(o["one_way_hours"] for o in out)
    wp, wt, wc = (0.65, 0.25, 0.10) if limited_budget else (0.40, 0.35, 0.25)
    for o in out:
        p = 1 - (o["round_trip_group_inr"] - lo_p) / (hi_p - lo_p) if hi_p > lo_p else 1.0
        t = 1 - (o["one_way_hours"] - lo_t) / (hi_t - lo_t) if hi_t > lo_t else 1.0
        c = (o["comfort"] or 3) / 5
        sc = wp * p + wt * t + wc * c
        o["eats_trip"] = bool(trip_days and 2 * o["one_way_hours"] > 0.4 * trip_days * 24)
        if o["eats_trip"]:
            sc -= 0.5  # journey would consume a large share of a short trip: rank it last unless the budget forces it
        o["score"] = round(sc, 4)
    return sorted(out, key=lambda o: (-o["score"], o["mode"]))


def best(ds: Dataset, origin: str, dest: str, modes: list[str] | None, travellers: int, limited_budget: bool = False, trip_days: int | None = None) -> dict | None:
    r = options(ds, origin, dest, modes, travellers, limited_budget, trip_days)
    return r[0] if r else None
