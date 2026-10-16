"""Dataset loading, validation and normalisation.

Reads the processed JSON files, normalises names/categories, drops invalid records, and
records every problem in `issues` so missing data is handled explicitly (never silently
treated as a match).
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..config import DATA_DIR

INTERESTS = ["nature", "mountains", "beaches", "adventure", "historical", "culture", "food", "shopping", "photography", "wellness"]
CLIMATES = ["cold", "cool", "mild", "warm", "hot"]
SEASONS = ["winter", "summer", "monsoon", "post-monsoon"]
TIERS = ["hostel", "budget", "homestay", "midrange", "premium"]
MODES = ["bus", "train", "car", "flight"]
TAG_ALIASES = {"wildlife": "nature", "relaxation": "wellness", "sightseeing": "photography", "trekking": "adventure", "heritage": "historical",
               "hill": "mountains", "beach": "beaches", "cuisine": "food", "history": "historical"}


ORIGIN_ALIASES = {"delhi": "delhi", "newdelhi": "delhi", "bangalore": "bengaluru", "bombay": "mumbai", "madras": "chennai", "calcutta": "kolkata", "vizag": "visakhapatnam", "cochin": "kochi"}
DEST_ALIASES = {"mysore": "mysuru", "kodagu": "coorg", "madikeri": "coorg", "udhagamandalam": "ooty", "pondy": "pondicherry", "puducherry": "pondicherry", "panaji": "goa", "benares": "varanasi", "kashi": "varanasi"}


def norm_name(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", str(s).lower())


def norm_tag(t: str) -> str:
    t = str(t).strip().lower()
    return TAG_ALIASES.get(t, t)


@dataclass
class Dataset:
    destinations: dict[str, dict] = field(default_factory=dict)
    attractions: dict[str, dict] = field(default_factory=dict)
    accommodation: dict[str, dict] = field(default_factory=dict)
    transport: list[dict] = field(default_factory=list)
    origins: dict[str, dict] = field(default_factory=dict)
    meta: dict[str, Any] = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)

    # ---- lookups
    def dest_attractions(self, dest_id: str) -> list[dict]:
        return [a for a in self.attractions.values() if a["destination_id"] == dest_id]

    def dest_stays(self, dest_id: str) -> list[dict]:
        return [a for a in self.accommodation.values() if a["destination_id"] == dest_id]

    def links(self, origin: str, dest: str, modes: list[str] | None = None) -> list[dict]:
        return [t for t in self.transport if t["origin"] == origin and t["destination"] == dest and (not modes or t["mode"] in modes)]

    def resolve_destination(self, text: str) -> str | None:
        n = norm_name(text)
        for d in self.destinations.values():
            if norm_name(d["name"]) == n or d["id"] == n:
                return d["id"]
        for d in self.destinations.values():  # alias: mysore / kodagu / pondy ...
            if n and (n in norm_name(d["name"]) or norm_name(d["name"]) in n):
                return d["id"]
        return None

    def resolve_origin(self, text: str) -> str | None:
        n = norm_name(text)
        n = ORIGIN_ALIASES.get(n, n)
        for o in self.origins.values():
            if norm_name(o["name"]) == n or o["id"] == n:
                return o["id"]
        return None


def _num(v: Any, default: float | None = None) -> float | None:
    try:
        if v is None or v == "":
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _valid_coord(lat: Any, lon: Any) -> bool:
    la, lo = _num(lat), _num(lon)
    return la is not None and lo is not None and 6 <= la <= 38 and 67 <= lo <= 98  # India bounding box


def load_dataset(data_dir: Path | None = None) -> Dataset:
    d = Path(data_dir or DATA_DIR)
    ds = Dataset()

    def read(name: str) -> list | dict:
        p = d / f"{name}.json"
        if not p.exists():
            ds.issues.append(f"missing file: {p.name}")
            return [] if name != "meta" else {}
        return json.loads(p.read_text(encoding="utf-8"))

    ds.meta = read("meta")  # type: ignore[assignment]
    for o in read("origins"):
        if _valid_coord(o.get("lat"), o.get("lon")):
            ds.origins[o["id"]] = o
        else:
            ds.issues.append(f"origin {o.get('id')} dropped: invalid coordinates")

    for x in read("destinations"):
        if not x.get("id") or not x.get("name"):
            ds.issues.append("destination dropped: missing id/name"); continue
        if x["id"] in ds.destinations:
            ds.issues.append(f"duplicate destination {x['id']} ignored"); continue
        if not _valid_coord(x.get("lat"), x.get("lon")):
            ds.issues.append(f"destination {x['id']} dropped: invalid coordinates"); continue
        x["tags"] = sorted({norm_tag(t) for t in x.get("tags", [])})
        x["climate"] = x.get("climate") if x.get("climate") in CLIMATES else None
        if x["climate"] is None:
            ds.issues.append(f"destination {x['id']}: climate missing")
        x["best_seasons"] = [s for s in x.get("best_seasons", []) if s in SEASONS]
        x["min_days"] = int(_num(x.get("min_days"), 1)); x["max_days"] = int(_num(x.get("max_days"), max(x["min_days"], 4)))
        x["price_index"] = _num(x.get("price_index"), 1.0)
        x.setdefault("accessibility", None)
        x.setdefault("food_per_person_day", {"budget": 350, "mid": 700, "premium": 1500})
        ds.destinations[x["id"]] = x

    seen = set()
    for a in read("attractions"):
        key = (a.get("destination_id"), norm_name(a.get("name", "")))
        if key in seen:
            ds.issues.append(f"duplicate attraction {a.get('name')} ignored"); continue
        seen.add(key)
        if a.get("destination_id") not in ds.destinations:
            ds.issues.append(f"attraction {a.get('name')} dropped: unknown destination"); continue
        if not _valid_coord(a.get("lat"), a.get("lon")):
            ds.issues.append(f"attraction {a.get('name')} dropped: invalid coordinates"); continue
        dur = _num(a.get("duration_min"))
        if dur is None or dur <= 0:
            ds.issues.append(f"attraction {a.get('name')}: duration missing, default 60 min applied"); dur = 60
        fee = _num(a.get("fee_inr"))
        a["fee_known"] = fee is not None
        a["fee_inr"] = max(fee, 0) if fee is not None else 0.0
        a["duration_min"] = dur
        a["intensity"] = int(_num(a.get("intensity"), 2))
        a["significance"] = int(_num(a.get("significance"), 1))
        a["tags"] = sorted({norm_tag(t) for t in a.get("tags", [])})
        a.setdefault("accessible", None)
        a.setdefault("best_slot", "any")
        ds.attractions[a["id"]] = a

    for s in read("accommodation"):
        if s.get("destination_id") in ds.destinations and s.get("tier") in TIERS and _num(s.get("price_inr")):
            ds.accommodation[s["id"]] = s
        else:
            ds.issues.append(f"accommodation {s.get('id')} dropped: invalid tier/destination/price")

    for t in read("transport_links"):
        if t.get("origin") in ds.origins and t.get("destination") in ds.destinations and t.get("mode") in MODES and _num(t.get("price_inr")) is not None:
            ds.transport.append(t)
        else:
            ds.issues.append(f"transport link dropped: {t.get('origin')}->{t.get('destination')} {t.get('mode')}")
    return ds
