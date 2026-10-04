"""
Prosta implementacja IPOIConnectionService: odległość euklidesowa (po rzutowaniu
współrzędnych na płaszczyznę w metrach) + stałe średnie prędkości i koszty na tryb podróży.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import timedelta
from itertools import permutations
from typing import Sequence

from app.schemas.planning import (
    Coordinates,
    IPOIConnectionService,
    POI,
    POIConnection,
    TravelMode,
)

METERS_PER_DEG_LAT = 111_320.0


@dataclass(frozen=True)
class ModeProfile:
    speed_kmh: float  # średnia prędkość
    cost_per_km: float  # koszt (paliwo/bilet) za km w walucie głównej
    detour_factor: float = 1.0  # mnożnik dystansu: droga jest dłuższa niż linia prosta


DEFAULT_PROFILES: dict[TravelMode, ModeProfile] = {
    TravelMode.WALK: ModeProfile(speed_kmh=4.5, cost_per_km=0.0, detour_factor=1.3),
    TravelMode.BICYCLE: ModeProfile(speed_kmh=15.0, cost_per_km=0.0, detour_factor=1.3),
    TravelMode.TRANSIT: ModeProfile(speed_kmh=20.0, cost_per_km=0.3, detour_factor=1.3),
    TravelMode.DRIVE: ModeProfile(speed_kmh=40.0, cost_per_km=0.5, detour_factor=1.3),
}


def euclidean_distance_m(a: Coordinates, b: Coordinates) -> float:
    """Odległość euklidesowa na lokalnej płaszczyźnie (stopnie -> metry)."""
    mean_lat = math.radians((a.lat + b.lat) / 2)
    dx = (b.lng - a.lng) * METERS_PER_DEG_LAT * math.cos(mean_lat)
    dy = (b.lat - a.lat) * METERS_PER_DEG_LAT
    return math.hypot(dx, dy)


class SimpleConnectionService(IPOIConnectionService):
    def __init__(self, profiles: dict[TravelMode, ModeProfile] | None = None) -> None:
        self._profiles = profiles or DEFAULT_PROFILES

    async def get_connections(
        self, pois: Sequence[POI], mode: TravelMode
    ) -> list[POIConnection]:
        profile = self._profiles[mode]
        # graf pełny skierowany: każda uporządkowana para (A->B oraz B->A)
        return [self._connection(a, b, mode, profile) for a, b in permutations(pois, 2)]

    @staticmethod
    def _connection(a: POI, b: POI, mode: TravelMode, p: ModeProfile) -> POIConnection:
        distance_m = euclidean_distance_m(a.location, b.location) * p.detour_factor
        hours = (distance_m / 1000) / p.speed_kmh
        return POIConnection(
            from_poi_id=a.id,
            to_poi_id=b.id,
            mode=mode,
            distance_m=round(distance_m),
            duration=timedelta(hours=hours),
            fuel_cost=round(distance_m / 1000 * p.cost_per_km, 2),
            routing_fallback=True,
        )
