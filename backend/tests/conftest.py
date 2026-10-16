"""Small, reproducible fixture dataset used by every test (independent of the real sample files)."""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from app.ai.data_loader import load_dataset
from app.ai.engine import Engine
from app.ai.geo import haversine_km
from app.config import load_config

ORIGINS = [dict(id="orig", name="Origin City", lat=17.385, lon=78.4867), dict(id="o2", name="Second City", lat=12.9716, lon=77.5946)]

DESTS = [
    dict(id="hilla", name="Hill A", state="S1", region="South", type="hill station", climate="cool", lat=11.41, lon=76.69, best_seasons=["summer", "winter"],
         min_days=2, max_days=5, tags=["nature", "mountains", "photography"], accessibility="good", airport="x", airport_km=50, railhead="y", railhead_km=20,
         price_index=1.0, description="Cool hill station", food_per_person_day={"budget": 300, "mid": 600, "premium": 1200}),
    dict(id="beachb", name="Beach B", state="S2", region="West", type="beach", climate="warm", lat=15.49, lon=73.83, best_seasons=["winter"],
         min_days=3, max_days=7, tags=["beaches", "food"], accessibility="moderate", airport="x", airport_km=30, railhead="y", railhead_km=20,
         price_index=1.3, description="Beach", food_per_person_day={"budget": 400, "mid": 800, "premium": 1500}),
    dict(id="coldc", name="Cold C", state="S3", region="Himalaya", type="mountain resort", climate="cold", lat=32.24, lon=77.19, best_seasons=["summer"],
         min_days=3, max_days=6, tags=["mountains", "adventure"], accessibility="limited", airport="x", airport_km=50, railhead="y", railhead_km=250,
         price_index=1.1, description="Cold", food_per_person_day={"budget": 350, "mid": 700, "premium": 1400}),
    dict(id="heritd", name="Heritage D", state="S4", region="North", type="heritage city", climate=None, lat=26.91, lon=75.79, best_seasons=[],
         min_days=2, max_days=4, tags=["historical", "culture"], accessibility=None, airport="x", airport_km=12, railhead="y", railhead_km=3,
         price_index=1.0, description="Heritage with missing climate", food_per_person_day={"budget": 350, "mid": 700, "premium": 1500}),
]

# (dest, name, tags, dlat, dlon, duration, fee, intensity, accessible, slot, significance)
ATTR = [
    ("hilla", "Botanic Garden", ["nature", "photography"], 0.010, 0.020, 90, 30, 1, True, "morning", 3),
    ("hilla", "Lake Walk", ["nature"], -0.005, 0.000, 60, 0, 1, True, "afternoon", 2),
    ("hilla", "Summit Trek", ["adventure", "mountains"], 0.000, 0.045, 150, 10, 3, False, "morning", 3),
    ("hilla", "Tea Museum", ["culture"], 0.003, 0.010, 60, 20, 1, True, "afternoon", 2),
    ("hilla", "Waterfall Hike", ["nature", "adventure"], -0.040, -0.060, 120, 0, 2, False, "morning", 2),
    ("hilla", "Viewpoint", ["mountains", "photography"], 0.012, 0.030, 45, 0, 1, None, "evening", 2),
    ("hilla", "Rose Park", ["nature"], 0.006, 0.012, 60, 30, 1, True, "afternoon", 1),
    ("beachb", "Main Beach", ["beaches"], 0.05, -0.08, 150, 0, 1, True, "afternoon", 3),
    ("beachb", "Old Fort", ["historical"], 0.00, -0.05, 75, 0, 1, None, "evening", 2),
    ("beachb", "Spice Market", ["food", "shopping"], 0.01, 0.00, 90, 0, 1, True, "morning", 2),
    ("coldc", "Snow Valley", ["adventure", "mountains"], 0.07, -0.03, 240, 500, 2, False, "morning", 3),
    ("coldc", "Old Temple", ["culture"], 0.01, -0.01, 60, 0, 1, True, "morning", 2),
    ("coldc", "Cafe Lane", ["food"], 0.02, 0.00, 90, 0, 1, True, "afternoon", 1),
    ("heritd", "City Palace", ["historical", "culture"], 0.01, 0.04, 120, 200, 1, True, "morning", 3),
    ("heritd", "Observatory", ["historical"], 0.011, 0.04, 60, 50, 1, True, "afternoon", 2),
    ("heritd", "Bazaar", ["shopping"], 0.004, 0.03, 90, 0, 1, True, "evening", 2),
]

TIERS = [("hostel", 450, "per_bed", 1, False), ("budget", 1100, "per_room", 2, False), ("homestay", 1600, "per_room", 2, None),
         ("midrange", 2900, "per_room", 2, True), ("premium", 6500, "per_room", 2, True)]


def _links():
    rows = []
    for o in ORIGINS:
        for d in DESTS:
            km = haversine_km(o["lat"], o["lon"], d["lat"], d["lon"]) * 1.3
            rows.append(dict(origin=o["id"], destination=d["id"], mode="bus", distance_km=round(km), price_inr=round(km * 1.9, -1), duration_h=round(km / 45 + .5, 1), comfort=2, price_basis="per_person"))
            rows.append(dict(origin=o["id"], destination=d["id"], mode="train", distance_km=round(km), price_inr=round(km * 1.1 + 60, -1), duration_h=round(km / 55 + 1, 1), comfort=3, price_basis="per_person"))
            if km > 500:
                rows.append(dict(origin=o["id"], destination=d["id"], mode="flight", distance_km=round(km), price_inr=round(2600 + km * 2.2, -1), duration_h=round(km / 650 + 4, 1), comfort=5, price_basis="per_person"))
            if km < 800:
                rows.append(dict(origin=o["id"], destination=d["id"], mode="car", distance_km=round(km), price_inr=round(km * 12, -2), duration_h=round(km / 50 + .5, 1), comfort=4, price_basis="per_vehicle"))
    return rows


def write_fixture(path: Path) -> None:
    dests = {d["id"]: d for d in DESTS}
    attrs, stays = [], []
    for i, (did, name, tags, dlat, dlon, dur, fee, inten, acc, slot, sig) in enumerate(ATTR):
        d = dests[did]
        attrs.append(dict(id=f"{did}-{i:03d}", destination_id=did, name=name, tags=tags, lat=round(d["lat"] + dlat, 5), lon=round(d["lon"] + dlon, 5), duration_min=dur,
                          fee_inr=fee, intensity=inten, accessible=acc, best_slot=slot, significance=sig, description=name))
    for d in DESTS:
        for k, (tier, price, unit, cap, acc) in enumerate(TIERS):
            stays.append(dict(id=f"{d['id']}-{tier}", destination_id=d["id"], name=f"{d['name']} {tier} (sample)", tier=tier, price_inr=round(price * d["price_index"], -1), price_unit=unit,
                              capacity=cap, amenities=["wifi"], comfort=k + 1, accessible=acc, lat=round(d["lat"] + (k - 2) * 0.004, 5), lon=d["lon"], is_sample=True))
    path.mkdir(parents=True, exist_ok=True)
    for name, obj in dict(destinations=[dict(d, country="India") for d in DESTS], attractions=attrs, accommodation=stays, transport_links=_links(), origins=ORIGINS,
                          meta=dict(dataset="test fixture", disclaimer="fixture")).items():
        (path / f"{name}.json").write_text(json.dumps(obj), encoding="utf-8")


@pytest.fixture(scope="session")
def fixture_dir(tmp_path_factory) -> Path:
    p = tmp_path_factory.mktemp("fixture_data")
    write_fixture(p)
    return p


@pytest.fixture()
def ds(fixture_dir):
    return load_dataset(fixture_dir)


@pytest.fixture()
def engine(ds):
    return Engine(ds=ds, cfg=load_config())


@pytest.fixture(autouse=True)
def _no_real_gemini(monkeypatch):
    """Tests never call the real API or consume quota: the key is removed (even if backend/.env has one) and provider state is reset.
    Tests that exercise Gemini behaviour set a fake key and mock `llm._generate`."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    from app.ai import llm
    llm.reset_for_tests()
    yield
    llm.reset_for_tests()
