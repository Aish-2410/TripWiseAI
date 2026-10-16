"""Geographic helpers."""
from __future__ import annotations

import math

EARTH_KM = 6371.0088


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_KM * math.asin(min(1.0, math.sqrt(a)))


def local_leg(km_straight: float, road_factor: float = 1.35) -> tuple[float, float]:
    """(road km, minutes) for a short in-destination hop. Slower in town (20 km/h), faster on longer hops (35 km/h)."""
    km = km_straight * road_factor
    speed = 20.0 if km < 8 else 35.0
    return km, km / speed * 60.0 + 8.0  # +8 min to find transport / park
