"""Explicit knowledge representation: a typed triple store + query layer.

Facts are (subject, predicate, object) triples with provenance and confidence.
Entities have types (destination, attraction, activity, climate, season, state,
accommodation, transport_mode, origin, traveller_profile). Recommendations,
rules and chatbot answers all read from this store.

Predicates
----------
HAS_TYPE, HAS_CLIMATE, HAS_ACTIVITY, CONTAINS_ATTRACTION, LOCATED_IN, SUITABLE_FOR,
BEST_IN_SEASON, IN_STATE, HAS_ACCESSIBILITY, HAS_ESTIMATED_DURATION (minutes),
HAS_ENTRY_FEE (INR/person), HAS_INTENSITY (1-3), LOCATED_NEAR (<= 3 km),
CONNECTS (origin -> destination, with mode), OFFERS_ACCOMMODATION, HAS_MIN_DAYS, HAS_MAX_DAYS.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field, asdict
from typing import Any, Iterable

from .data_loader import Dataset
from .geo import haversine_km

SUITABLE = {
    "nature": "nature lovers", "mountains": "mountain lovers", "beaches": "beach lovers", "adventure": "adventure seekers",
    "historical": "history buffs", "culture": "culture seekers", "food": "food lovers", "shopping": "shoppers",
    "photography": "photographers", "wellness": "people seeking relaxation and wellness",
}


@dataclass(frozen=True)
class Fact:
    s: str
    p: str
    o: Any
    provenance: str = "sample dataset"
    confidence: float = 0.7
    meta: tuple = field(default_factory=tuple)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["meta"] = dict(self.meta)
        return d


class KnowledgeBase:
    def __init__(self) -> None:
        self.facts: list[Fact] = []
        self._by_s: dict[str, list[Fact]] = defaultdict(list)
        self._by_p: dict[str, list[Fact]] = defaultdict(list)
        self._by_o: dict[Any, list[Fact]] = defaultdict(list)
        self.entity_type: dict[str, str] = {}
        self.entity_label: dict[str, str] = {}

    # ---- building
    def add_entity(self, eid: str, etype: str, label: str | None = None) -> None:
        self.entity_type[eid] = etype
        self.entity_label[eid] = label or eid

    def add(self, s: str, p: str, o: Any, provenance: str = "sample dataset", confidence: float = 0.7, **meta) -> None:
        f = Fact(s, p, o, provenance, confidence, tuple(sorted(meta.items())))
        self.facts.append(f)
        self._by_s[s].append(f); self._by_p[p].append(f)
        try:
            self._by_o[o].append(f)
        except TypeError:
            pass

    # ---- query layer
    def query(self, s: str | None = None, p: str | None = None, o: Any = None) -> list[Fact]:
        """Pattern match; None is a wildcard. Uses the narrowest index."""
        if s is not None:
            pool: Iterable[Fact] = self._by_s.get(s, [])
        elif p is not None:
            pool = self._by_p.get(p, [])
        elif o is not None:
            pool = self._by_o.get(o, [])
        else:
            pool = self.facts
        return [f for f in pool if (s is None or f.s == s) and (p is None or f.p == p) and (o is None or f.o == o)]

    def objects(self, s: str, p: str) -> list[Any]:
        return [f.o for f in self.query(s=s, p=p)]

    def one(self, s: str, p: str, default: Any = None) -> Any:
        r = self.objects(s, p)
        return r[0] if r else default

    def subjects(self, p: str, o: Any) -> list[str]:
        return [f.s for f in self.query(p=p, o=o)]

    def describe(self, eid: str) -> dict:
        out = defaultdict(list)
        for f in self.query(s=eid):
            out[f.p].append(f.o)
        incoming = defaultdict(list)
        for f in self.query(o=eid):
            incoming[f.p].append(f.s)
        return dict(id=eid, type=self.entity_type.get(eid), label=self.entity_label.get(eid, eid), facts=dict(out), incoming=dict(incoming))

    def facts_for_destination(self, dest_id: str, limit: int = 60) -> list[dict]:
        fs = [f for f in self.query(s=dest_id) if f.p != "CONTAINS_ATTRACTION"]
        attrs = self.objects(dest_id, "CONTAINS_ATTRACTION")
        fs += [Fact(dest_id, "CONTAINS_ATTRACTION", a, confidence=0.7) for a in attrs[:8]]
        return [f.as_dict() for f in fs[:limit]]

    def stats(self) -> dict:
        preds: dict[str, int] = defaultdict(int)
        for f in self.facts:
            preds[f.p] += 1
        types: dict[str, int] = defaultdict(int)
        for t in self.entity_type.values():
            types[t] += 1
        return dict(n_facts=len(self.facts), n_entities=len(self.entity_type), predicates=dict(preds), entity_types=dict(types))

    # ---- inference helper (simple forward rule): destination SUITABLE_FOR <- HAS_ACTIVITY with >=2 attractions
    def attraction_count_with_tag(self, dest_id: str, tag: str) -> int:
        n = 0
        for a in self.objects(dest_id, "CONTAINS_ATTRACTION"):
            if tag in self.objects(a, "HAS_ACTIVITY"):
                n += 1
        return n


def build_kb(ds: Dataset, near_km: float = 3.0) -> KnowledgeBase:
    kb = KnowledgeBase()
    src = "sample dataset (illustrative)"
    for o in ds.origins.values():
        kb.add_entity(o["id"], "origin", o["name"])
    for d in ds.destinations.values():
        kb.add_entity(d["id"], "destination", d["name"])
        kb.add_entity(d["state"], "state"); kb.add(d["id"], "IN_STATE", d["state"], src, 0.9)
        kb.add(d["id"], "HAS_TYPE", d["type"], src, 0.8)
        if d.get("climate"):
            kb.add_entity(f"climate:{d['climate']}", "climate", d["climate"]); kb.add(d["id"], "HAS_CLIMATE", d["climate"], src, 0.7)
        for s in d["best_seasons"]:
            kb.add_entity(f"season:{s}", "season", s); kb.add(d["id"], "BEST_IN_SEASON", s, src, 0.6)
        for t in d["tags"]:
            kb.add_entity(f"activity:{t}", "activity", t); kb.add(d["id"], "HAS_ACTIVITY", t, src, 0.7)
            kb.add(d["id"], "SUITABLE_FOR", SUITABLE.get(t, t), src, 0.6)
        if d.get("accessibility"):
            kb.add(d["id"], "HAS_ACCESSIBILITY", d["accessibility"], src, 0.5)
        kb.add(d["id"], "HAS_MIN_DAYS", d["min_days"], src, 0.6); kb.add(d["id"], "HAS_MAX_DAYS", d["max_days"], src, 0.6)
    for a in ds.attractions.values():
        kb.add_entity(a["id"], "attraction", a["name"])
        kb.add(a["destination_id"], "CONTAINS_ATTRACTION", a["id"], src, 0.8)
        kb.add(a["id"], "LOCATED_IN", a["destination_id"], src, 0.9)
        for t in a["tags"]:
            kb.add(a["id"], "HAS_ACTIVITY", t, src, 0.7)
        kb.add(a["id"], "HAS_ESTIMATED_DURATION", int(a["duration_min"]), src, 0.5)
        if a.get("fee_known", True):
            kb.add(a["id"], "HAS_ENTRY_FEE", a["fee_inr"], src, 0.5)
        kb.add(a["id"], "HAS_INTENSITY", a["intensity"], src, 0.6)
    for s in ds.accommodation.values():
        kb.add_entity(s["id"], "accommodation", s["name"])
        kb.add(s["destination_id"], "OFFERS_ACCOMMODATION", s["id"], src, 0.4)
        kb.add(s["id"], "LOCATED_IN", s["destination_id"], src, 0.4)
        kb.add(s["id"], "HAS_TIER", s["tier"], src, 0.4)
        for a in ds.dest_attractions(s["destination_id"]):
            if haversine_km(s["lat"], s["lon"], a["lat"], a["lon"]) <= near_km:
                kb.add(s["id"], "LOCATED_NEAR", a["id"], "computed from coordinates", 0.5)
    seen = set()
    for t in ds.transport:
        key = (t["origin"], t["destination"], t["mode"])
        if key not in seen:
            seen.add(key)
            kb.add(t["origin"], "CONNECTS", t["destination"], "distance model v1 (estimate)", 0.4, mode=t["mode"], hours=t["duration_h"])
    return kb
