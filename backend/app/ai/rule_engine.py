"""Configurable, inspectable IF-THEN rule engine.

Each rule has a human-readable IF/THEN text, a condition and an effect. Ranking rules
add or subtract points (on the 0-100 scale) and always record *why*. Itinerary rules set
flags consumed by the itinerary generator. Every evaluation returns a trace (fired and
not-fired) so the reasoning can be shown in the UI and defended in a viva.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .data_loader import CLIMATES
from .knowledge_base import KnowledgeBase


@dataclass
class Rule:
    id: str
    name: str
    kind: str                       # ranking | itinerary | budget
    if_text: str
    then_text: str
    cond: Callable[[dict], bool]
    effect: Callable[[dict], tuple[float, str]] = lambda c: (0.0, "")
    params: dict = field(default_factory=dict)

    def describe(self) -> dict:
        return dict(id=self.id, name=self.name, kind=self.kind, **{"if": self.if_text, "then": self.then_text}, params=self.params)


class RuleEngine:
    def __init__(self, cfg: dict, kb: KnowledgeBase | None = None):
        self.cfg, self.kb = cfg, kb
        short, lim = cfg["short_trip_days"], cfg["limited_budget_per_person_day"]
        pp = lambda c: (c["prefs"].budget / (c["prefs"].travellers * (c["prefs"].duration_days or 1))) if c["prefs"].budget else None

        self.rules: list[Rule] = [
            Rule("R1_COOL_CLIMATE", "Cool-climate preference", "ranking",
                 "IF the traveller prefers cold/cool weather AND the destination has a recorded cool/cold climate",
                 "THEN raise its ranking by 6 points (verified climate fact in the knowledge base)",
                 lambda c: c["prefs"].climate in ("cold", "cool") and c["dest"].get("climate") in ("cold", "cool"),
                 lambda c: (6.0, f"{c['dest']['name']} has a recorded {c['dest']['climate']} climate, matching your preference"), dict(points=6)),
            Rule("R1B_CLIMATE_CONTRADICTION", "Climate contradicts preference", "ranking",
                 "IF the destination's climate is 3+ steps away from the stated preference on the cold-cool-mild-warm-hot scale (2 steps for a smaller penalty)",
                 "THEN lower its ranking by 10 points (3+ steps) or 4 points (2 steps)",
                 lambda c: bool(c["prefs"].climate) and c["dest"].get("climate") in CLIMATES and abs(CLIMATES.index(c["dest"]["climate"]) - CLIMATES.index(c["prefs"].climate)) >= 2,
                 lambda c: ((-10.0 if abs(CLIMATES.index(c["dest"]["climate"]) - CLIMATES.index(c["prefs"].climate)) >= 3 else -4.0),
                            f"its {c['dest']['climate']} climate conflicts with your wish for {c['prefs'].climate} weather"), dict(points="-10 / -4")),
            Rule("R2_LIMITED_BUDGET", "Limited budget", "ranking",
                 f"IF budget per person per day is below INR {lim}",
                 "THEN favour lower-priced destinations (+4) and penalise pricier ones (-4); the planner also prefers cheaper transport, stays and paid activities",
                 lambda c: pp(c) is not None and pp(c) < lim,
                 lambda c: (4.0, "local price level is low for your tight budget") if c["dest"]["price_index"] <= 0.95 else
                           ((-4.0, "local price level is high for your tight budget") if c["dest"]["price_index"] >= 1.2 else (0.0, "")),
                 dict(threshold_inr_pp_day=lim)),
            Rule("R3_ACCESSIBLE_TRAVEL", "Elderly / accessibility needs", "ranking",
                 "IF the party includes elderly travellers OR accessibility is required",
                 "THEN favour destinations with good accessibility data (+5), penalise limited (-6) or unknown (-2); itinerary uses gentler activities and a relaxed pace",
                 lambda c: c["prefs"].elderly or c["prefs"].accessibility_required,
                 lambda c: {"good": (5.0, "accessibility data is good"), "limited": (-6.0, "accessibility is limited (steep or uneven terrain)"),
                            "moderate": (0.0, ""), None: (-2.0, "accessibility is not verified in the data")}[c["dest"].get("accessibility")]),
            Rule("R4_SHORT_TRIP", "Short trip", "ranking",
                 f"IF the trip is {short} days or fewer",
                 "THEN prioritise nearby destinations: +4 if one-way travel is 6 h or less, -8 if 12 h or more",
                 lambda c: (c["prefs"].duration_days or 99) <= short and c.get("one_way_hours") is not None,
                 lambda c: (4.0, f"only about {c['one_way_hours']} h each way for a short trip") if c["one_way_hours"] <= 6 else
                           ((-8.0, f"about {c['one_way_hours']} h each way is long for a short trip") if c["one_way_hours"] >= 12 else (0.0, "")),
                 dict(max_days=short)),
            Rule("R5_NATURE", "Nature preference", "ranking",
                 "IF the traveller prefers nature AND the destination has at least 3 nature-related attractions",
                 "THEN raise its ranking by 5 points",
                 lambda c: "nature" in c["prefs"].interests and c.get("tag_counts", {}).get("nature", 0) >= 3,
                 lambda c: (5.0, f"{c['tag_counts']['nature']} nature-related attractions in the data"), dict(min_attractions=3)),
            Rule("R8_SEASON", "Travel season", "ranking",
                 "IF a travel season is given",
                 "THEN +3 when it is among the destination's best seasons, otherwise -4",
                 lambda c: bool(c["prefs"].season) and bool(c["dest"].get("best_seasons")),
                 lambda c: (3.0, f"{c['prefs'].season} is a recommended season") if c["prefs"].season in c["dest"]["best_seasons"]
                           else (-4.0, f"{c['prefs'].season} is not among its recommended seasons")),
            Rule("R9_FRIENDS_ADVENTURE", "Friends who want adventure", "ranking",
                 "IF travelling with friends AND interested in adventure AND the destination has 2+ adventure attractions",
                 "THEN raise its ranking by 3 points",
                 lambda c: c["prefs"].travel_style == "friends" and "adventure" in c["prefs"].interests and c.get("tag_counts", {}).get("adventure", 0) >= 2,
                 lambda c: (3.0, "several adventure activities for the group")),
            Rule("R10_FAMILY", "Family with children", "ranking",
                 "IF travelling with children or as a family",
                 "THEN +2 for destinations whose accessibility is not limited, -3 for limited",
                 lambda c: c["prefs"].children or c["prefs"].travel_style == "family",
                 lambda c: (-3.0, "terrain is demanding for young children") if c["dest"].get("accessibility") == "limited" else (2.0, "manageable terrain for families")),
            Rule("R7_PROXIMITY", "Nearby attractions share a day", "itinerary",
                 "IF two attractions are within 3 km of each other",
                 "THEN the itinerary search prefers scheduling them on the same day (travel-time penalty in the search cost)",
                 lambda c: True, params=dict(radius_km=3)),
            Rule("R3b_GENTLE_ITINERARY", "Gentle itinerary", "itinerary",
                 "IF elderly travellers OR a relaxed pace",
                 "THEN exclude strenuous attractions (intensity 3), cap at 3 activities per day and add rest breaks",
                 lambda c: c["prefs"].elderly or c["prefs"].pace == "relaxed"),
            Rule("R6_OVER_BUDGET", "Itinerary over budget", "budget",
                 "IF the estimated trip cost exceeds the budget",
                 "THEN invoke the Budget Guardian optimiser (ranked, explained changes; mandatory constraints are never dropped silently)",
                 lambda c: bool(c.get("over_budget"))),
        ]

    def describe(self) -> list[dict]:
        return [r.describe() for r in self.rules]

    def evaluate_ranking(self, prefs, dest: dict, features: dict) -> list[dict]:
        ctx = dict(prefs=prefs, dest=dest, **features)
        out = []
        for r in self.rules:
            if r.kind != "ranking":
                continue
            try:
                fired = bool(r.cond(ctx))
            except Exception:  # a rule that cannot be evaluated is reported, never crashes ranking
                fired = False
            pts, why = r.effect(ctx) if fired else (0.0, "")
            out.append(dict(rule_id=r.id, name=r.name, fired=fired and pts != 0.0, points=pts, reason=why, if_text=r.if_text))
        return out

    def itinerary_context(self, prefs, dest: dict, over_budget: bool = False) -> dict:
        ctx = dict(prefs=prefs, dest=dest, over_budget=over_budget)
        fired = [r.id for r in self.rules if r.kind in ("itinerary", "budget") and r.cond(ctx)]
        return dict(fired=fired)
