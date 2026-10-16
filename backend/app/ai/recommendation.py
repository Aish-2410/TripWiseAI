"""Destination recommendation: constraint filtering -> weighted scoring -> rules -> explanations.

Pipeline
--------
1. HARD CONSTRAINTS remove destinations that cannot satisfy mandatory needs (budget floor,
   trip length, travel-time share, mandatory accessibility, explicit exclusions, no usable
   transport in the data). Every exclusion carries a reason.
2. SOFT SCORING combines six components (weights configurable, default
   interest .30 / budget .25 / climate .15 / duration .15 / convenience .10 / style .05).
   - Component the USER did not specify  -> dropped and the weights are re-normalised.
   - Destination data MISSING             -> scored low (config: missing_component_score) and flagged
     "unverified" (missing is never a free match).
3. RULES adjust the 0-100 score by small, explained amounts.
4. EXPLANATION text lists matches and limitations.
Deterministic: same input + dataset -> same output (tie-break by score then name) unless
`randomize` is set, in which case a seeded jitter is added.
"""
from __future__ import annotations

import math
import random

from . import accommodation as acc
from . import transport as trn
from .data_loader import Dataset, CLIMATES
from .itinerary import attraction_value, eligible
from .knowledge_base import KnowledgeBase
from .rule_engine import RuleEngine

COMPONENTS = ["interest", "budget", "climate", "duration", "convenience", "style"]
STYLE_TAGS = {"couple": {"culture", "wellness", "photography", "beaches", "food"}, "friends": {"adventure", "beaches", "food", "shopping", "nightlife"},
              "solo": {"culture", "adventure", "nature", "photography"}}


class Recommender:
    def __init__(self, ds: Dataset, kb: KnowledgeBase, rules: RuleEngine, cfg: dict):
        self.ds, self.kb, self.rules, self.cfg = ds, kb, rules, cfg

    # ------------------------------------------------------------ cost estimates
    def estimate_costs(self, prefs, dest: dict, opts: list[dict], elig: list[dict]) -> dict:
        d = prefs.duration_days or max(dest["min_days"], 2)
        T, nights = prefs.travellers, max(d - 1, 0)
        limited = bool(prefs.budget and prefs.budget / (T * d) < self.cfg["limited_budget_per_person_day"])
        cont = 1 + self.cfg["contingency_pct"]
        vehicles = math.ceil(T / 4)
        stays = {s["tier"]: s for s in self.ds.dest_stays(dest["id"])}
        usable = [s for t, s in stays.items() if not (prefs.accessibility_required and s.get("accessible") is False)]
        cheapest_stay = min((acc.stay_cost(s, T, nights) for s in usable), default=None)
        cheapest_tr = min((o["round_trip_group_inr"] for o in opts), default=None)
        food_b, food_m = dest["food_per_person_day"]["budget"], dest["food_per_person_day"]["mid"]
        n_pick = min(len(elig), d * 2)
        top = sorted(elig, key=lambda a: (-attraction_value(a, prefs, limited), a["id"]))[:n_pick]
        fees = sum(a["fee_inr"] for a in top) * T
        local = 250 * d * vehicles
        if None in (cheapest_stay, cheapest_tr):
            return dict(floor=None, typical=None)
        floor = (cheapest_tr + cheapest_stay + food_b * T * d) * cont
        # typical = the most comfortable transport/stay/food combination that fits the budget (same preference order the planner uses);
        # if nothing fits, the cheapest combination is reported (and flagged as over budget).
        tiers_try = [prefs.accommodation] if prefs.accommodation else ["homestay", "budget", "hostel"]
        combos = []
        for o in opts[:4]:
            for t in tiers_try:
                if t not in stays or stays[t] not in usable:
                    continue
                for fd, fp in (("mid", food_m), ("budget", food_b)):
                    tot = (o["round_trip_group_inr"] + acc.stay_cost(stays[t], T, nights) + fp * T * d + fees + local) * cont
                    combos.append((tot, o, t, fd))
        if not combos:
            return dict(floor=round(floor), typical=None)
        fit = [c for c in combos if not prefs.budget or c[0] <= prefs.budget]
        tot, o, t, fd = fit[0] if fit else min(combos, key=lambda c: c[0])
        return dict(floor=round(floor), typical=round(tot), tier_assumed=t, food_assumed=fd, option=o)

    # ------------------------------------------------------------ main entry
    def recommend(self, prefs, top_n: int = 10, sort: str = "match") -> dict:
        trace = dict(prefs=prefs.model_dump(), weights=self.cfg["weights"])
        if not prefs.origin:
            return dict(needs_info=["origin"], message="Where will you start your journey? Travel cost and time depend on it.", ranked=[], excluded=[], trace=trace)
        if prefs.origin not in self.ds.origins:
            names = ", ".join(sorted(o["name"] for o in self.ds.origins.values()))
            return dict(needs_info=["origin"], message=f"'{prefs.origin}' is not in the sample data. Available starting cities: {names}.", ranked=[], excluded=[], trace=trace)
        ranked, excluded = [], []
        rng = random.Random(prefs.seed)
        for dest in sorted(self.ds.destinations.values(), key=lambda x: x["id"]):
            item = self._evaluate(prefs, dest)
            (excluded if item.get("excluded_reasons") else ranked).append(item)
        if prefs.randomize:
            for r in ranked:
                r["match_score"] = round(min(100, max(0, r["match_score"] + rng.uniform(-3, 3))), 1)
        if sort == "cost":
            ranked.sort(key=lambda r: (r["cost"]["typical"] if r["cost"]["typical"] is not None else 1e12, -r["match_score"], r["name"]))
        else:
            ranked.sort(key=lambda r: (-r["match_score"], r["name"]))
        for i, r in enumerate(ranked, 1):
            r["rank"] = i
        out = dict(needs_info=[], ranked=ranked[:top_n], total_candidates=len(ranked), excluded=excluded, trace=trace)
        if not ranked:
            out["relaxation"] = self._relaxation(prefs, excluded)
            out["message"] = "No destination meets all of your hard constraints."
        return out

    # ------------------------------------------------------------ per destination
    def _evaluate(self, prefs, dest: dict) -> dict:
        ds, cfg = self.ds, self.cfg
        d = prefs.duration_days
        elig = eligible(ds, dest["id"], prefs, cfg)
        all_attr = ds.dest_attractions(dest["id"])
        opts = trn.options(ds, prefs.origin, dest["id"], prefs.transport or None, prefs.travellers,
                           bool(prefs.budget and d and prefs.budget / (prefs.travellers * d) < cfg["limited_budget_per_person_day"]), d)
        any_opts = trn.options(ds, prefs.origin, dest["id"], None, prefs.travellers)
        tag_counts = {t: sum(1 for a in elig if t in a["tags"]) for t in {t for a in elig for t in a["tags"]}}
        costs = self.estimate_costs(prefs, dest, opts, elig) if opts else dict(floor=None, typical=None)
        fastest = min((o["one_way_hours"] for o in opts), default=None)   # feasibility test uses the fastest allowed mode
        chosen_opt = costs.pop("option", None) or (opts[0] if opts else None)   # what the traveller would actually take
        hours = chosen_opt["one_way_hours"] if chosen_opt else None

        reasons: list[str] = []
        if dest["id"] in prefs.excluded_destinations or dest["name"].lower() in prefs.excluded_destinations:
            reasons.append("you excluded this destination")
        if not opts:
            reasons.append("no allowed transport mode connects your origin to it in the data" if any_opts else "no transport link from your origin in the data")
        if d is not None and d < dest["min_days"]:
            reasons.append(f"needs at least {dest['min_days']} days (you have {d})")
        if d is not None and fastest is not None and 2 * fastest > 0.5 * d * 24:
            reasons.append(f"round-trip travel (~{round(2 * fastest)} h) would consume most of a {d}-day trip")
        if d is not None and hours is not None and fastest is not None and 2 * fastest <= 0.5 * d * 24 < 2 * hours:
            reasons.append(f"the transport that fits your budget takes ~{hours} h each way, leaving little time on a {d}-day trip (faster modes exceed the budget)")
        if prefs.budget and costs.get("floor") is not None and costs["floor"] > prefs.budget:
            reasons.append(f"even the cheapest estimated plan (~INR {costs['floor']:,}) exceeds your budget of INR {int(prefs.budget):,}")
        need = min(max(2, d or 2), 4)
        if len(elig) < 2 or (len(elig) < need and len(elig) < len(all_attr)):
            # excluded only when YOUR exclusions/needs removed the attractions; a destination that is merely sparse in the data is kept (flagged below)
            reasons.append(f"only {len(elig)} attraction(s) remain after your exclusions/needs (at least {need} required)")
        if prefs.accessibility_required and dest.get("accessibility") == "limited":
            reasons.append("accessibility is limited at this destination (mandatory requirement)")
        if prefs.accessibility_required and sum(1 for a in all_attr if a.get("accessible") is True) < 2:
            reasons.append("too few attractions are verified accessible in the data")
        if reasons:
            return dict(id=dest["id"], name=dest["name"], state=dest["state"], excluded_reasons=reasons, cost=costs)

        # -------- component scores
        comps: dict[str, dict] = {}
        miss = cfg["missing_component_score"]

        def put(name, score, status, note):
            comps[name] = dict(score=round(score, 3), weight=cfg["weights"][name], status=status, note=note)

        if prefs.interests:
            vals = []
            for it in prefs.interests:
                cnt = tag_counts.get(it, 0)
                vals.append(0.6 * (it in dest["tags"]) + 0.4 * min(1.0, cnt / 3))
            put("interest", sum(vals) / len(vals), "ok", f"covers {sum(1 for v in vals if v >= 0.5)} of {len(vals)} interests")
        else:
            put("interest", 0, "not_specified", "no interests given")
        if prefs.budget and costs.get("typical"):
            r = costs["typical"] / prefs.budget
            s = 0.8 + 0.4 * r if r < 0.5 else 1.0 if r <= 0.9 else 0.9 if r <= 1.0 else max(0.0, 1 - (r - 1.0) / 0.3)
            put("budget", s, "ok", f"estimated ~INR {costs['typical']:,} vs budget INR {int(prefs.budget):,}")
        else:
            put("budget", 0, "not_specified", "no budget given")
        parts, notes = [], []
        if prefs.climate:
            if dest.get("climate") in CLIMATES:
                parts.append(max(0.0, 1 - abs(CLIMATES.index(dest["climate"]) - CLIMATES.index(prefs.climate)) / 2)); notes.append(f"{dest['climate']} vs preferred {prefs.climate}")
            else:
                parts.append(miss); notes.append("destination climate missing (unverified)")
        if prefs.season:
            if dest.get("best_seasons"):
                parts.append(1.0 if prefs.season in dest["best_seasons"] else 0.3); notes.append(f"season {prefs.season}")
            else:
                parts.append(miss); notes.append("season data missing (unverified)")
        if parts:
            put("climate", sum(parts) / len(parts), "missing_data" if any("missing" in n for n in notes) else "ok", "; ".join(notes))
        else:
            put("climate", 0, "not_specified", "no climate or season preference")
        if d is not None:
            s = 1.0 if dest["min_days"] <= d <= dest["max_days"] else max(0.4, 1 - 0.15 * (d - dest["max_days"]))
            put("duration", s, "ok", f"recommended {dest['min_days']}-{dest['max_days']} days; you have {d}")
        else:
            put("duration", 0, "not_specified", "no trip length given")
        if hours is not None:
            s = 1.0 if hours <= 6 else 1.0 - 0.4 * (hours - 6) / 6 if hours <= 12 else 0.6 - 0.4 * (hours - 12) / 12 if hours <= 24 else 0.1
            put("convenience", max(s, 0.05), "ok", f"~{hours} h one way by {chosen_opt['mode']}")
        else:
            put("convenience", miss, "missing_data", "no transport data")
        sparts, snotes = [], []
        avg_int = sum(a["intensity"] for a in elig) / len(elig)
        if prefs.pace == "relaxed" or prefs.elderly:
            sparts.append(max(0.0, 1 - (avg_int - 1) / 2)); snotes.append(f"avg activity intensity {avg_int:.1f}/3 for a relaxed pace")
        elif prefs.pace == "packed":
            sparts.append(min(1.0, len(elig) / ((d or 3) * 3))); snotes.append(f"{len(elig)} attractions for a packed pace")
        if prefs.travel_style == "family" or prefs.children:
            sparts.append({"good": 1.0, "moderate": 0.7, "limited": 0.3}.get(dest.get("accessibility"), miss)); snotes.append("family suitability")
        elif prefs.travel_style in STYLE_TAGS:
            ov = len(STYLE_TAGS[prefs.travel_style] & set(dest["tags"]))
            sparts.append(1.0 if ov >= 2 else 0.6 if ov == 1 else 0.3); snotes.append(f"{prefs.travel_style} travel fit")
        if prefs.accessibility_required:
            sparts.append({"good": 1.0, "moderate": 0.6}.get(dest.get("accessibility"), miss)); snotes.append("accessibility")
        if sparts:
            put("style", sum(sparts) / len(sparts), "ok", "; ".join(snotes))
        else:
            put("style", 0, "not_specified", "no style / pace / accessibility preference beyond defaults")

        active = {k: v for k, v in comps.items() if v["status"] != "not_specified"}
        wsum = sum(v["weight"] for v in active.values()) or 1.0
        base = 100.0 * sum(v["weight"] * v["score"] for v in active.values()) / wsum
        feats = dict(one_way_hours=hours, tag_counts=tag_counts)
        adj = self.rules.evaluate_ranking(prefs, dest, feats)
        pts = sum(a["points"] for a in adj if a["fired"])
        # rule points act with diminishing returns: +pts closes pts/30 of the remaining headroom; -pts removes pts/30 of the score.
        # This keeps scores inside 0-100 without saturating (which would erase ranking resolution).
        frac = min(abs(pts) / 30.0, 1.0)
        final = round(base + (100.0 - base) * frac if pts > 0 else base - base * frac if pts < 0 else base, 1)
        limits = [c["note"] for c in comps.values() if c["status"] == "missing_data"]
        limits += [f"{k}: {v['note']}" for k, v in comps.items() if v["status"] == "ok" and v["score"] < 0.5]
        if costs.get("typical") and prefs.budget and costs["typical"] > prefs.budget:
            limits.append("typical cost is above your budget; the Budget Guardian can suggest cheaper options")
        if len(elig) < need:
            limits.append(f"the dataset lists only {len(elig)} attraction(s) here, so some days may be light")
        if dest.get("accessibility") == "limited":
            limits.append("terrain/access is limited for travellers with mobility needs")
        d_all = d if d is not None else None
        return dict(
            id=dest["id"], name=dest["name"], state=dest["state"], country="India", region=dest["region"], type=dest["type"], description=dest["description"],
            climate=dest.get("climate"), best_seasons=dest["best_seasons"], min_days=dest["min_days"], max_days=dest["max_days"], tags=dest["tags"],
            accessibility=dest.get("accessibility"), wiki=dest.get("wiki"), lat=dest["lat"], lon=dest["lon"],
            match_score=final, base_score=round(base, 1), components=comps, adjustments=adj, cost=costs,
            transport_best=(chosen_opt["mode"] if chosen_opt else None), one_way_hours=hours, fastest_one_way_hours=fastest,
            attractions_preview=[a["name"] for a in sorted(elig, key=lambda a: (-a["significance"], a["name"]))[:4]],
            explanation=self._explain(prefs, dest, comps, adj, costs, limits, final), limitations=limits, is_sample=True)

    def _explain(self, prefs, dest, comps, adj, costs, limits, final) -> str:
        pos = []
        for k in ("interest", "climate", "duration", "convenience", "budget", "style"):
            c = comps[k]
            if k == "budget" and costs.get("typical") and prefs.budget and costs["typical"] > prefs.budget:
                continue  # never call an over-budget estimate a "fit"
            if c["status"] == "ok" and c["score"] >= 0.75:
                pos.append({"interest": "its attractions match your interests", "climate": f"its climate/season fits ({c['note']})",
                            "duration": f"the trip length suits it ({c['note']})", "convenience": f"it is easy to reach ({c['note']})",
                            "budget": f"the estimate fits your budget ({c['note']})", "style": "it suits your travel style and pace"}[k])
        pos += [a["reason"] for a in adj if a["fired"] and a["points"] > 0]
        txt = f"{dest['name']} scores {final:.0f}/100"
        txt += (": " + "; ".join(pos[:4]) + ".") if pos else ", a moderate fit."
        if limits:
            txt += " Limitations: " + "; ".join(limits[:3]) + "."
        txt += " Costs are estimates from sample data."
        return txt

    # ------------------------------------------------------------ relaxation advice
    def _relaxation(self, prefs, excluded: list[dict]) -> list[str]:
        tips: list[str] = []
        floors = [e["cost"]["floor"] for e in excluded if e.get("cost", {}).get("floor")]
        if prefs.budget and floors:
            tips.append(f"Raise the budget to about INR {min(floors):,} to admit the cheapest destination ({sum(1 for f in floors if f <= min(floors) * 1.2)} within 20% of that).")
        mins = [int(x.split("at least ")[1].split(" ")[0]) for e in excluded for x in e["excluded_reasons"] if x.startswith("needs at least")]
        if mins:
            tips.append(f"Add days: several destinations need {min(mins)}+ days.")
        if any("no allowed transport" in x for e in excluded for x in e["excluded_reasons"]):
            tips.append("Allow more transport modes (for example bus or car in addition to your selection).")
        if any("accessibility" in x for e in excluded for x in e["excluded_reasons"]):
            tips.append("Accessibility is a mandatory filter; consider destinations marked 'moderate' with extra planning or relax it for some activities.")
        if any("round-trip travel" in x for e in excluded for x in e["excluded_reasons"]):
            tips.append("Lengthen the trip or pick a nearer start city: long journeys would eat most of a short trip.")
        return tips or ["Relax one constraint at a time (budget, duration or exclusions) and recalculate."]
