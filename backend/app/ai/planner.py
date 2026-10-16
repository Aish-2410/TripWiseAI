"""Plan builder: chooses transport, stay and food tier, runs the itinerary search and prices the result."""
from __future__ import annotations

import copy

from . import accommodation as acc
from . import transport as trn
from .budget import price_plan
from .data_loader import Dataset, TIERS
from .itinerary import generate_itinerary
from .knowledge_base import KnowledgeBase
from .rule_engine import RuleEngine


class PlanError(ValueError):
    pass


def is_limited_budget(cfg: dict, prefs) -> bool:
    days = prefs.duration_days or 1
    return bool(prefs.budget and prefs.budget / (prefs.travellers * days) < cfg["limited_budget_per_person_day"])


def build_plan(ds: Dataset, cfg: dict, kb: KnowledgeBase, rules: RuleEngine, prefs, dest_id: str, transport_mode: str | None = None,
               tier: str | None = None, food_tier: str | None = None, locked: dict | None = None, banned_ids: set | None = None,
               pinned: list | None = None, travel_weight: float = 0.35, cost_weight: float | None = None) -> dict:
    if dest_id not in ds.destinations:
        raise PlanError(f"Unknown destination '{dest_id}'.")
    if not prefs.origin:
        raise PlanError("Starting city is required to cost the journey.")
    if prefs.origin not in ds.origins:
        raise PlanError(f"Origin '{prefs.origin}' is not in the sample data.")
    n_days = prefs.duration_days or max(ds.destinations[dest_id]["min_days"], 2)
    prefs = prefs.model_copy(update=dict(duration_days=n_days))
    limited = is_limited_budget(cfg, prefs)
    ctx = rules.itinerary_context(prefs, ds.destinations[dest_id])
    opts = trn.options(ds, prefs.origin, dest_id, prefs.transport or None, prefs.travellers, limited, n_days)
    if transport_mode:
        forced = trn.options(ds, prefs.origin, dest_id, [transport_mode], prefs.travellers, limited, n_days)
        opts = forced or opts
    if not opts:
        raise PlanError("No transport option in the dataset connects your origin to this destination with the allowed modes.")
    tr = opts[0]

    # accommodation: respect a stated tier; else the best tier that fits the budget
    base_stay = acc.stay_for_tier(ds, dest_id, "budget") or ds.dest_stays(dest_id)[0]
    gen = generate_itinerary(ds, cfg, prefs, dest_id, (base_stay["lat"], base_stay["lon"]), n_days, limited_budget=limited, locked=locked,
                             travel_weight=travel_weight, cost_weight=cost_weight, banned_ids=banned_ids)
    plan = dict(prefs=prefs.model_dump(), destination_id=dest_id, destination_name=ds.destinations[dest_id]["name"], transport=tr,
                accommodation_tier=base_stay["tier"], stay_id=base_stay["id"], food_tier=food_tier or "mid",
                days=[dict(day=d["day"], activity_ids=d["activity_ids"]) for d in gen["days"]], search=gen["search"], notes=list(gen["notes"]),
                pinned=list(pinned or []), rules_fired=ctx["fired"], disclaimer=ds.meta.get("disclaimer"))
    tiers_try = [tier or prefs.accommodation] if (tier or prefs.accommodation) else ["midrange", "homestay", "budget", "hostel"]
    foods = [food_tier] if food_tier else ["mid", "budget"]
    candidates = []
    for tr_opt in opts[:4]:                                   # transport options in rank order
        for t in tiers_try:
            st_ = acc.stay_for_tier(ds, dest_id, t)
            if not st_ or (prefs.accessibility_required and st_.get("accessible") is False):
                continue
            for f in foods:
                cand = copy.deepcopy(plan); cand["transport"] = tr_opt; cand["stay_id"] = st_["id"]; cand["accommodation_tier"] = t; cand["food_tier"] = f
                candidates.append(price_plan(ds, cfg, prefs, cand))
    if not candidates:
        raise PlanError("No accommodation tier in the data satisfies your requirements for this destination.")
    fits = [c for c in candidates if not c["costs"]["over_budget"]]
    chosen = fits[0] if fits else min(candidates, key=lambda c: c["costs"]["total"])
    h = chosen["transport"]["one_way_hours"]
    if 2 * h > 0.4 * n_days * 24:
        chosen["notes"].append(f"The journey takes about {h} h each way by {chosen['transport']['mode']}, which uses a large share of a {n_days}-day trip.")
    if chosen["costs"]["over_budget"]:
        chosen["notes"].append("Estimated cost exceeds the budget; see the Budget Guardian suggestions.")
    return chosen
