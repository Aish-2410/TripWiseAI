"""Plan B generator and dynamic replanning.

A change request (new budget, fewer days, excluded activity, extra interest, pace,
accommodation...) is applied to the stored preferences, then:
  1. the affected parts are identified (itinerary / transport / stay / costs),
  2. activities that are still valid are LOCKED in place (released only when the new
     pace/duration or exclusions force it, or to make room for a newly requested interest),
  3. the beam search fills only the freed slots,
  4. costs are recomputed and, if over budget, the Budget Guardian optimiser runs,
  5. a diff (added / removed / cost change) is returned and the previous version is kept.
"""
from __future__ import annotations

import copy
import math

from .budget import optimize, plan_value, price_plan
from .data_loader import Dataset, norm_tag
from .itinerary import attraction_value, eligible, matches_exclusion
from .planner import PlanError, build_plan, is_limited_budget
from ..schemas.prefs import Preferences

LIST_FIELDS = {"interests", "excluded_activities", "excluded_destinations", "transport", "dietary"}


def patch_prefs(prefs: Preferences, changes: dict) -> Preferences:
    data = prefs.model_dump()
    for k in ("add_interests", "remove_interests", "exclude_activities", "include_activities"):
        vals = [norm_tag(v) if k.endswith("interests") else str(v).lower() for v in changes.get(k, [])]
        if k == "add_interests":
            data["interests"] = sorted(set(data["interests"]) | set(vals))
        elif k == "remove_interests":
            data["interests"] = sorted(set(data["interests"]) - set(vals))
        elif k == "exclude_activities":
            data["excluded_activities"] = sorted(set(data["excluded_activities"]) | set(vals))
        elif k == "include_activities":
            data["excluded_activities"] = sorted(set(data["excluded_activities"]) - set(vals))
    for k, v in changes.items():
        if k in data and k not in ("add_interests", "remove_interests", "exclude_activities", "include_activities"):
            data[k] = v
    return Preferences(**data)


def _names(ds, ids):
    return [ds.attractions[i]["name"] for i in ids]


def apply_changes(ds: Dataset, cfg: dict, kb, rules, plan: dict, changes: dict) -> dict:
    old_prefs = Preferences(**plan["prefs"])
    new_prefs = patch_prefs(old_prefs, changes)
    if new_prefs.duration_days is None:
        new_prefs = new_prefs.model_copy(update=dict(duration_days=len(plan["days"])))
    dest_id = plan["destination_id"]
    n_days = new_prefs.duration_days
    limited = is_limited_budget(cfg, new_prefs)
    impacts = sorted({k for k in changes if k in ("budget", "duration_days", "pace", "accommodation", "transport", "travellers", "elderly", "accessibility_required")}
                     | ({"itinerary"} if any(k in changes for k in ("add_interests", "remove_interests", "exclude_activities", "include_activities", "interests")) else set()))

    elig_ids = {a["id"] for a in eligible(ds, dest_id, new_prefs, cfg)}
    from .itinerary import _day_limit
    locked: dict[int, list[str]] = {}
    released: list[str] = []
    for i, d in enumerate(plan["days"]):
        if i >= n_days:
            released += d["activity_ids"]; continue
        lim, cap = _day_limit(new_prefs, cfg, i, n_days)
        keep = [a for a in d["activity_ids"] if a in elig_ids and a not in released]
        dropped_inelig = [a for a in d["activity_ids"] if a not in elig_ids]
        released += dropped_inelig
        if len(keep) > cap:                         # new pace allows fewer: release the lowest-value extras
            ranked = sorted(keep, key=lambda a: (-attraction_value(ds.attractions[a], new_prefs, limited), a))
            released += ranked[cap:]; keep = [a for a in keep if a in ranked[:cap]]
        locked[i] = keep
    if changes.get("add_interests") or changes.get("interests"):
        # make room for the newly requested interest: release the lowest-value activities that do not match it
        want = set(new_prefs.interests)
        cand = sorted([a for ids in locked.values() for a in ids if not (want & set(ds.attractions[a]["tags"]))],
                      key=lambda a: (attraction_value(ds.attractions[a], new_prefs, limited), a))
        n_rel = min(len(cand), max(1, math.ceil(0.3 * sum(len(v) for v in locked.values()))))
        for a in cand[:n_rel]:
            for i in locked:
                if a in locked[i]:
                    locked[i].remove(a); released.append(a)
    pinned = [a for a in plan.get("pinned", []) if a in elig_ids]
    keep_mode = plan["transport"]["mode"] if plan.get("transport") and (not new_prefs.transport or plan["transport"]["mode"] in new_prefs.transport) else None
    tier_arg = new_prefs.accommodation if ("accommodation" in changes) else plan["accommodation_tier"]
    try:
        new_plan = build_plan(ds, cfg, kb, rules, new_prefs, dest_id, transport_mode=keep_mode, tier=tier_arg, food_tier=plan["food_tier"],
                              locked=locked, pinned=pinned)
    except PlanError as e:
        return dict(ok=False, error=str(e))
    optimiser = None
    if new_plan["costs"]["over_budget"]:
        optimiser = optimize(ds, cfg, new_prefs, new_plan)
        new_plan = optimiser["plan"]
    new_plan["version"] = plan.get("version", 1) + 1
    new_plan["notes"] = list(dict.fromkeys(new_plan["notes"]))
    summary = diff_plans(ds, plan, new_plan)
    summary["impacts"] = impacts or ["costs"]
    summary["changes_requested"] = changes
    if optimiser:
        summary["optimiser"] = {k: optimiser[k] for k in ("original_total", "final_total", "resolved", "message", "steps")}
    return dict(ok=True, plan=new_plan, previous=plan, summary=summary)


def diff_plans(ds: Dataset, old: dict, new: dict) -> dict:
    o = {a for d in old["days"] for a in d["activity_ids"]}
    n = {a for d in new["days"] for a in d["activity_ids"]}
    oc, nc = old["costs"], new["costs"]
    cat = {k: nc["breakdown"][k] - oc["breakdown"][k] for k in nc["breakdown"] if nc["breakdown"][k] != oc["breakdown"][k]}
    lines = []
    if n - o:
        lines.append("Added: " + ", ".join(_names(ds, sorted(n - o))))
    if o - n:
        lines.append("Removed: " + ", ".join(_names(ds, sorted(o - n))))
    if old["accommodation_tier"] != new["accommodation_tier"]:
        lines.append(f"Accommodation: {old['accommodation_tier']} -> {new['accommodation_tier']}")
    if (old.get("transport") or {}).get("mode") != (new.get("transport") or {}).get("mode"):
        lines.append(f"Transport: {(old.get('transport') or {}).get('mode')} -> {(new.get('transport') or {}).get('mode')}")
    if len(old["days"]) != len(new["days"]):
        lines.append(f"Duration: {len(old['days'])} -> {len(new['days'])} days")
    lines.append(f"Estimated total: INR {oc['total']:,} -> INR {nc['total']:,} ({nc['total'] - oc['total']:+,})")
    return dict(added=_names(ds, sorted(n - o)), removed=_names(ds, sorted(o - n)), unchanged=len(o & n), cost_before=oc["total"], cost_after=nc["total"],
                cost_delta=nc["total"] - oc["total"], category_delta=cat, lines=lines)


# ------------------------------------------------------------------ manual edits
def edit_plan(ds: Dataset, cfg: dict, plan: dict, op: dict) -> dict:
    """op: {type: remove|add|move, activity_id, day (1-based), position?}. Re-prices and returns warnings; never silently drops."""
    prefs = Preferences(**plan["prefs"])
    new = copy.deepcopy(plan)
    t, aid = op.get("type"), op.get("activity_id")
    warnings: list[str] = []
    if aid not in ds.attractions or ds.attractions[aid]["destination_id"] != plan["destination_id"]:
        return dict(ok=False, error="That attraction does not belong to this destination.")
    cur = None
    for d in new["days"]:
        if aid in d["activity_ids"]:
            cur = d
    if t == "remove":
        if not cur:
            return dict(ok=False, error="That attraction is not in the itinerary.")
        cur["activity_ids"].remove(aid)
        new["pinned"] = [p for p in new.get("pinned", []) if p != aid]
    elif t in ("add", "move"):
        day = int(op.get("day", 1))
        if not 1 <= day <= len(new["days"]):
            return dict(ok=False, error=f"Day must be between 1 and {len(new['days'])}.")
        if t == "add" and cur:
            return dict(ok=False, error="That attraction is already in the itinerary.")
        if t == "move" and not cur:
            return dict(ok=False, error="That attraction is not in the itinerary.")
        if cur:
            cur["activity_ids"].remove(aid)
        tgt = new["days"][day - 1]["activity_ids"]
        pos = op.get("position")
        tgt.insert(min(pos, len(tgt)) if isinstance(pos, int) else len(tgt), aid)
        if t == "add":
            new["pinned"] = sorted(set(new.get("pinned", [])) | {aid})
        a = ds.attractions[aid]
        if any(matches_exclusion(a, kw) for kw in prefs.excluded_activities):
            warnings.append(f"'{a['name']}' conflicts with an exclusion you set.")
        if prefs.accessibility_required and a.get("accessible") is False:
            warnings.append(f"'{a['name']}' is not step-free according to the data.")
    else:
        return dict(ok=False, error="Unknown edit type.")
    price_plan(ds, cfg, prefs, new)
    from .itinerary import _day_limit
    for i, d in enumerate(new["days"]):
        lim, cap = _day_limit(prefs, cfg, i, len(new["days"]))
        s = d["schedule"]
        if s["activity_minutes"] + s["travel_minutes"] > lim + 1:
            warnings.append(f"Day {i + 1} is over the {prefs.pace} time limit ({s['activity_minutes'] + s['travel_minutes']} > {int(lim)} min).")
        if len(d["activity_ids"]) > cap:
            warnings.append(f"Day {i + 1} has more than {cap} activities for a {prefs.pace} pace.")
    if new["costs"]["over_budget"]:
        warnings.append(f"Estimated total INR {new['costs']['total']:,} exceeds your budget.")
    new["version"] = plan.get("version", 1) + 1
    return dict(ok=True, plan=new, previous=plan, warnings=warnings, summary=diff_plans(ds, plan, new))
