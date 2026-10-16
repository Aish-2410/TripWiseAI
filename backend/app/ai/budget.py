"""Budget Guardian: cost model, overrun detection and ranked optimisation.

Every figure is an ESTIMATE derived from the sample dataset (transport from a distance
model, hotels fictional, fees rounded) - never verified current pricing.

Group costing rules
-------------------
* Transport  : per-person fares x travellers x 2 (round trip); per-vehicle fares
               x ceil(travellers/4) x 2.
* Stay       : hostel = per bed x travellers x nights; others = per room x
               ceil(travellers / capacity) x nights.
* Food       : per person per day x travellers x days.
* Attractions: per-person entry fee x travellers.
* Local      : paid km x rate x ceil(travellers/4) vehicles (walking legs are free).
* Other      : contingency percentage on the subtotal.
"""
from __future__ import annotations

import copy
import math
from datetime import date, timedelta

from . import accommodation as acc
from . import transport as trn
from .data_loader import Dataset, TIERS
from .itinerary import attraction_value, generate_itinerary, schedule_day

FOOD_ORDER = ["premium", "mid", "budget"]


def _stay_record(ds: Dataset, plan: dict) -> dict:
    s = ds.accommodation.get(plan["stay_id"]) if plan.get("stay_id") else None
    if s is None:
        s = acc.stay_for_tier(ds, plan["destination_id"], plan["accommodation_tier"])
    return s


def price_plan(ds: Dataset, cfg: dict, prefs, plan: dict) -> dict:
    """(Re)build schedules and costs from plan['days'][i]['activity_ids']. Mutates and returns plan."""
    dest = ds.destinations[plan["destination_id"]]
    stay = _stay_record(ds, plan)
    plan["stay_id"] = stay["id"]; plan["accommodation_tier"] = stay["tier"]
    hotel = (stay["lat"], stay["lon"])
    n_days = len(plan["days"]); nights = max(n_days - 1, 0); T = prefs.travellers
    start = date.fromisoformat(prefs.start_date) if prefs.start_date else None
    daily, fee_sum, local_sum = [], 0, 0
    stay_total = acc.stay_cost(stay, T, nights)
    food_pp = dest["food_per_person_day"][plan["food_tier"]]
    for i, d in enumerate(plan["days"]):
        sch = schedule_day(ds, cfg, hotel, d["activity_ids"], T, rest_breaks=prefs.elderly or prefs.pace == "relaxed")
        d["schedule"] = sch; d["date"] = (start + timedelta(days=i)).isoformat() if start else None
        food_day = food_pp * T
        fee_sum += sch["fee_total"]; local_sum += sch["local_cost"]
        daily.append(dict(day=i + 1, attractions=sch["fee_total"], local_transport=sch["local_cost"], food=round(food_day),
                          accommodation=round(stay_total / nights) if (nights and i < nights) else 0,
                          activity_minutes=sch["activity_minutes"], travel_minutes=sch["travel_minutes"]))
    tr = plan.get("transport")
    transport_total = tr["round_trip_group_inr"] if tr else 0
    food_total = round(food_pp * T * n_days)
    subtotal = transport_total + stay_total + food_total + fee_sum + local_sum
    other = round(subtotal * cfg["contingency_pct"])
    total = subtotal + other
    budget = prefs.budget
    plan["costs"] = dict(
        currency="INR", label="Estimates from sample data - not verified current prices",
        breakdown=dict(transport=round(transport_total), accommodation=round(stay_total), food=food_total, attractions=round(fee_sum),
                       local_transport=round(local_sum), other=other),
        subtotal=round(subtotal), total=round(total), per_person=round(total / T), travellers=T, nights=nights,
        budget=budget, remaining=round(budget - total) if budget else None,
        over_budget=bool(budget and total > budget), overrun=round(total - budget) if budget and total > budget else 0,
        daily=daily,
        assumptions=[f"{T} traveller(s); {nights} night(s); stay tier '{stay['tier']}' ({stay['price_unit'].replace('_', ' ')})",
                     f"food tier '{plan['food_tier']}' at about INR {int(food_pp)} per person per day",
                     f"local transport at INR {cfg['local_km_rate']:g}/km per vehicle (4 seats); walking legs free",
                     f"{int(cfg['contingency_pct'] * 100)}% contingency for other expenses"])
    plan["activity_total"] = sum(len(d["activity_ids"]) for d in plan["days"])
    return plan


def plan_value(ds: Dataset, prefs, plan: dict, limited: bool = False) -> float:
    return sum(attraction_value(ds.attractions[a], prefs, limited) for d in plan["days"] for a in d["activity_ids"])


# ------------------------------------------------------------------ optimiser
def _moves(ds: Dataset, cfg: dict, prefs, plan: dict) -> list[dict]:
    base_total = plan["costs"]["total"]
    limited = bool(prefs.budget and prefs.budget / (prefs.travellers * len(plan["days"])) < cfg["limited_budget_per_person_day"])
    base_val = plan_value(ds, prefs, plan, limited)
    moves: list[dict] = []

    def add(kind: str, text: str, new: dict, violates: bool = False, extra: dict | None = None):
        price_plan(ds, cfg, prefs, new)
        saving = base_total - new["costs"]["total"]
        if saving > 0:
            loss = max(0.0, base_val - plan_value(ds, prefs, new, limited))
            moves.append(dict(kind=kind, description=text, saving=round(saving), new_total=new["costs"]["total"], value_loss=round(loss, 2),
                              violates_preference=violates, rank_key=saving / (1.0 + loss), plan=new, **(extra or {})))

    # 1. cheaper accommodation
    for t in acc.cheaper_tiers(plan["accommodation_tier"]):
        s = acc.stay_for_tier(ds, plan["destination_id"], t)
        if s and not (prefs.accessibility_required and s.get("accessible") is False):
            n = copy.deepcopy(plan); n["stay_id"] = s["id"]; n["accommodation_tier"] = t
            add("accommodation", f"Switch accommodation from {plan['accommodation_tier']} to {t}", n,
                violates=bool(prefs.accommodation and TIERS.index(t) < TIERS.index(prefs.accommodation)))
    # 2. cheaper transport mode
    for o in trn.options(ds, prefs.origin, plan["destination_id"], None, prefs.travellers):
        if plan.get("transport") and o["mode"] != plan["transport"]["mode"]:
            n = copy.deepcopy(plan); n["transport"] = o
            add("transport", f"Travel by {o['mode']} instead of {plan['transport']['mode']} (about {o['one_way_hours']} h one way)", n,
                violates=bool(prefs.transport and o["mode"] not in prefs.transport))
    # 3. cheaper food tier
    if plan["food_tier"] != "budget":
        for t in FOOD_ORDER[FOOD_ORDER.index(plan["food_tier"]) + 1:]:
            n = copy.deepcopy(plan); n["food_tier"] = t
            add("food", f"Choose {t} meals instead of {plan['food_tier']} meals", n)
    pinned = set(plan.get("pinned", []))
    floor_keep = max(len(plan["days"]), math.ceil(0.6 * plan.get("original_activity_total", plan["activity_total"])))
    in_plan = {a for d in plan["days"] for a in d["activity_ids"]}
    free_pool = [a for a in ds.dest_attractions(plan["destination_id"]) if a["fee_inr"] == 0 and a["id"] not in in_plan and a.get("fee_known", True)]
    from .itinerary import eligible
    elig_ids = {a["id"] for a in eligible(ds, plan["destination_id"], prefs, cfg)}
    # 4. swap paid -> free attraction (same day, same position), 5. drop a paid attraction
    for di, d in enumerate(plan["days"]):
        for pos, aid in enumerate(d["activity_ids"]):
            a = ds.attractions[aid]
            if a["fee_inr"] <= 0 or aid in pinned:
                continue
            alts = [f for f in free_pool if f["id"] in elig_ids and set(f["tags"]) & set(a["tags"])]
            alts.sort(key=lambda f: (-attraction_value(f, prefs, limited), f["id"]))
            if alts:
                f = alts[0]; n = copy.deepcopy(plan); n["days"][di]["activity_ids"][pos] = f["id"]
                add("swap_free", f"Replace {a['name']} (INR {int(a['fee_inr'])} pp) with the free {f['name']}", n)
            if plan["activity_total"] - 1 >= floor_keep:  # never gut the itinerary just to shave a few rupees
                n = copy.deepcopy(plan); del n["days"][di]["activity_ids"][pos]
                add("drop_paid", f"Skip {a['name']} (INR {int(a['fee_inr'])} per person)", n)
    # 6. regroup attractions to cut local travel
    stay = _stay_record(ds, plan)
    keep = plan["activity_total"] or 1
    regen = generate_itinerary(ds, cfg, prefs, plan["destination_id"], (stay["lat"], stay["lon"]), len(plan["days"]), limited_budget=True,
                               travel_weight=1.6, cost_weight=0.003, locked={}, banned_ids=set())
    if sum(len(x["activity_ids"]) for x in regen["days"]) >= max(1, keep - 1):
        n = copy.deepcopy(plan); n["days"] = [dict(day=x["day"], activity_ids=x["activity_ids"]) for x in regen["days"]]
        add("regroup", "Regroup nearby attractions to cut local travel and fees", n)
    return sorted(moves, key=lambda m: (-m["rank_key"], m["description"]))


def optimize(ds: Dataset, cfg: dict, prefs, plan: dict, allow_relax_preferences: bool = False, max_steps: int = 8) -> dict:
    """Greedy ranked optimisation until the plan fits the budget. Mandatory constraints are never relaxed silently."""
    if not prefs.budget:
        return dict(resolved=None, steps=[], ranked_options=[], message="No budget set, so there is nothing to optimise against.", plan=plan)
    price_plan(ds, cfg, prefs, plan)
    plan.setdefault("original_activity_total", plan["activity_total"])
    original = plan["costs"]["total"]
    ranked_first = [{k: v for k, v in m.items() if k not in ("plan", "rank_key")} for m in _moves(ds, cfg, prefs, plan)] if plan["costs"]["over_budget"] else []
    steps, cur = [], plan
    for _ in range(max_steps):
        if not cur["costs"]["over_budget"]:
            break
        moves = [m for m in _moves(ds, cfg, prefs, cur) if allow_relax_preferences or not m["violates_preference"]]
        if not moves:
            break
        m = moves[0]
        steps.append({k: v for k, v in m.items() if k not in ("plan", "rank_key")} | dict(running_total=m["new_total"]))
        cur = m["plan"]
    pref_blocked = [m for m in ranked_first if m["violates_preference"]]
    resolved = not cur["costs"]["over_budget"]
    msg = ("Within budget after the suggested changes." if resolved else
           f"The cheapest version I can build without dropping your stated requirements is about INR {cur['costs']['total']:,}, "
           f"which is INR {cur['costs']['overrun']:,} above your budget of INR {int(prefs.budget):,}. Consider raising the budget, shortening the trip or choosing a nearer destination" +
           (", or relaxing a stated preference (see flagged options)." if pref_blocked else "."))
    if not plan["costs"]["over_budget"]:
        msg = "The plan is already within budget."
    return dict(original_total=original, budget=prefs.budget, overrun=max(0, original - prefs.budget), final_total=cur["costs"]["total"], resolved=resolved,
                steps=steps, ranked_options=ranked_first, message=msg, plan=cur)


def suggest_savings(ds: Dataset, cfg: dict, prefs, plan: dict, limit: int = 5) -> list[dict]:
    """Ranked cost-saving alternatives (each carries a re-priced candidate plan). Works with or without a budget."""
    price_plan(ds, cfg, prefs, plan)
    plan.setdefault("original_activity_total", plan["activity_total"])
    return _moves(ds, cfg, prefs, plan)[:limit]
