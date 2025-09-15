# app/utils/geo.py
from math import radians, sin, cos, asin, sqrt
from typing import Optional

def haversine_km(lat1: float, lon1: float, lat2: Optional[float], lon2: Optional[float]) -> Optional[float]:
    if lat2 is None or lon2 is None:
        return None
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * asin(sqrt(a))
    r = 6371
    return r * c
