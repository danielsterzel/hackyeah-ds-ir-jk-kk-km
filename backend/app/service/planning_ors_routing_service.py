"""Minimal OpenRouteService adapter for matrix costs and final leg geometry."""

from __future__ import annotations

from datetime import timedelta
from typing import Sequence

import httpx

from app.core.settings import settings
from app.schemas.planning import POI, POIConnection, TravelMode
from app.service.planning_simple_connection_service import DEFAULT_PROFILES

ORS_BASE_URL = "https://api.heigit.org/openrouteservice"

ORS_PROFILES: dict[TravelMode, str] = {
    TravelMode.WALK: "foot-walking",
    TravelMode.BICYCLE: "cycling-regular",
    TravelMode.DRIVE: "driving-car",
}


class ORSRoutingError(RuntimeError):
    """Raised when ORS cannot provide a usable routing response."""


class OpenRouteService:
    def __init__(
        self,
        api_key: str | None = settings.ors_api_key,
        *,
        base_url: str = ORS_BASE_URL,
        timeout_s: float = 12.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._timeout = httpx.Timeout(timeout_s)
        self._transport = transport

    def supports(self, mode: TravelMode) -> bool:
        return bool(self._api_key) and mode in ORS_PROFILES

    async def get_matrix_connections(
        self,
        pois: Sequence[POI],
        mode: TravelMode,
    ) -> list[POIConnection]:
        profile = self._profile(mode)
        payload = {
            "locations": [[poi.location.lng, poi.location.lat] for poi in pois],
            "metrics": ["distance", "duration"],
            "units": "m",
        }
        data = await self._post(f"/v2/matrix/{profile}", payload)
        distances = data.get("distances")
        durations = data.get("durations")
        if not isinstance(distances, list) or not isinstance(durations, list):
            raise ORSRoutingError("ORS matrix response has no distance/duration matrix")

        connections: list[POIConnection] = []
        for source_index, source in enumerate(pois):
            for target_index, target in enumerate(pois):
                if source_index == target_index:
                    continue
                try:
                    distance = distances[source_index][target_index]
                    duration = durations[source_index][target_index]
                except (IndexError, TypeError):
                    continue
                if distance is None or duration is None:
                    continue
                connections.append(
                    self._connection(
                        source,
                        target,
                        mode,
                        distance_m=float(distance),
                        duration_s=float(duration),
                    )
                )
        if not connections:
            raise ORSRoutingError("ORS matrix returned no usable routes")
        return connections

    async def get_direction(
        self,
        source: POI,
        target: POI,
        mode: TravelMode,
    ) -> POIConnection:
        profile = self._profile(mode)
        payload = {
            "coordinates": [
                [source.location.lng, source.location.lat],
                [target.location.lng, target.location.lat],
            ]
        }
        data = await self._post(
            f"/v2/directions/{profile}/geojson",
            payload,
        )
        features = data.get("features")
        if not isinstance(features, list) or not features:
            raise ORSRoutingError("ORS directions response has no route feature")

        feature = features[0]
        geometry = feature.get("geometry") if isinstance(feature, dict) else None
        properties = feature.get("properties") if isinstance(feature, dict) else None
        summary = properties.get("summary") if isinstance(properties, dict) else None
        if (
            not isinstance(geometry, dict)
            or geometry.get("type") != "LineString"
            or not isinstance(summary, dict)
            or summary.get("distance") is None
            or summary.get("duration") is None
        ):
            raise ORSRoutingError("ORS directions response is missing geometry/summary")

        return self._connection(
            source,
            target,
            mode,
            distance_m=float(summary["distance"]),
            duration_s=float(summary["duration"]),
            geometry=geometry,
        )

    async def _post(self, path: str, payload: dict[str, object]) -> dict[str, object]:
        if not self._api_key:
            raise ORSRoutingError("ORS_API_KEY is not configured")
        async with httpx.AsyncClient(
            base_url=self._base_url,
            headers={"Authorization": self._api_key},
            timeout=self._timeout,
            transport=self._transport,
        ) as client:
            response = await client.post(path, json=payload)
            response.raise_for_status()
            data = response.json()
        if not isinstance(data, dict):
            raise ORSRoutingError("ORS returned a non-object response")
        return data

    @staticmethod
    def _connection(
        source: POI,
        target: POI,
        mode: TravelMode,
        *,
        distance_m: float,
        duration_s: float,
        geometry: dict[str, object] | None = None,
    ) -> POIConnection:
        profile = DEFAULT_PROFILES[mode]
        return POIConnection(
            from_poi_id=source.id,
            to_poi_id=target.id,
            mode=mode,
            distance_m=max(0, round(distance_m)),
            duration=timedelta(seconds=max(0, duration_s)),
            fuel_cost=round(max(0, distance_m) / 1000 * profile.cost_per_km, 2),
            geometry=geometry,
        )

    def _profile(self, mode: TravelMode) -> str:
        if not self._api_key:
            raise ORSRoutingError("ORS_API_KEY is not configured")
        try:
            return ORS_PROFILES[mode]
        except KeyError as exc:
            raise ORSRoutingError(
                f"ORS profile is not available for {mode.value}"
            ) from exc
