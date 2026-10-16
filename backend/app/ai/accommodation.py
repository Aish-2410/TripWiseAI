"""Accommodation matching and ranking (sample, fictional records)."""
from __future__ import annotations

import math

from .data_loader import Dataset, TIERS
from .geo import haversine_km


def stay_cost(stay: dict, travellers: int, nights: int) -> int:
    """Hostels are priced per bed; every other tier per room (rooms = ceil(travellers / capacity))."""
    if nights <= 0:
        return 0
    if stay["price_unit"] == "per_bed":
        return int(stay["price_inr"] * travellers * nights)
    rooms = math.ceil(travellers / max(stay.get("capacity", 2), 1))
    return int(stay["price_inr"] * rooms * nights)


def options(ds: Dataset, dest_id: str, travellers: int, nights: int, tier: str | None = None, accessibility_required: bool = False,
            planned_attraction_ids: list[str] | None = None, budget_for_stay: float | None = None) -> list[dict]:
    attrs = [ds.attractions[a] for a in (planned_attraction_ids or []) if a in ds.attractions] or ds.dest_attractions(dest_id)
    out = []
    for s in ds.dest_stays(dest_id):
        if accessibility_required and s.get("accessible") is False:
            continue
        total = stay_cost(s, travellers, nights)
        dists = [haversine_km(s["lat"], s["lon"], a["lat"], a["lon"]) for a in attrs]
        avg_d = sum(dists) / len(dists) if dists else None
        score = 0.0
        score += 0.35 * (1 - min(s["price_inr"], 7000) / 7000)
        score += 0.25 * ((s.get("comfort") or 2) / 5)
        score += 0.25 * (1.0 if tier and s["tier"] == tier else 0.0)
        score += 0.15 * (1 - min(avg_d, 15) / 15 if avg_d is not None else 0.3)
        if accessibility_required and s.get("accessible") is None:
            score -= 0.15  # unknown accessibility is not a match
        if budget_for_stay is not None and total > budget_for_stay:
            score -= 0.2
        out.append(dict(id=s["id"], name=s["name"], tier=s["tier"], price_inr=s["price_inr"], price_unit=s["price_unit"],
                        total_inr=total, nights=nights, amenities=s["amenities"], comfort=s.get("comfort"), accessible=s.get("accessible"),
                        lat=s["lat"], lon=s["lon"], avg_distance_to_planned_km=round(avg_d, 1) if avg_d is not None else None,
                        is_sample=True, note=s.get("note"), score=round(score, 4)))
    return sorted(out, key=lambda o: (-o["score"], o["id"]))


def stay_for_tier(ds: Dataset, dest_id: str, tier: str) -> dict | None:
    for s in ds.dest_stays(dest_id):
        if s["tier"] == tier:
            return s
    return None


def cheaper_tiers(tier: str) -> list[str]:
    i = TIERS.index(tier) if tier in TIERS else len(TIERS) - 1
    return list(reversed(TIERS[:i]))
