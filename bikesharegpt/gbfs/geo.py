from __future__ import annotations

import math
from typing import Tuple


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in meters."""
    R = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def nearest_point(lat: float, lon: float, candidates: list[Tuple[float, float]]) -> tuple[int, float]:
    """Return (index, distance_m) for nearest candidate."""
    best_i = -1
    best_d = float("inf")
    for i, (clat, clon) in enumerate(candidates):
        d = haversine_m(lat, lon, clat, clon)
        if d < best_d:
            best_i, best_d = i, d
    return best_i, best_d
