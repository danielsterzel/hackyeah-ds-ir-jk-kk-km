from __future__ import annotations

import json
from datetime import datetime, timedelta

import httpx
import pytest

from app.schemas.planning import (
    Coordinates,
    CostVector,
    OptionalCostVector,
    POI,
    PlanningConstraints,
    TravelMode,
)
from app.service.planning_or_solver import OrToolsSolver
from app.service.planning_ors_routing_service import ORS_PROFILES, OpenRouteService
from app.service.planning_service import PlanningService
from app.service.planning_simple_solver_decoder import SimpleSolverDecoder
from app.service.planning_simple_solver_encoder import SimpleSolverEncoder


def make_poi(poi_id: str, lat: float, lng: float) -> POI:
    return POI(
        id=poi_id,
        name=poi_id,
        location=Coordinates(lat=lat, lng=lng),
    )


def test_ors_profiles_cover_supported_modes():
    assert ORS_PROFILES == {
        TravelMode.WALK: "foot-walking",
        TravelMode.BICYCLE: "cycling-regular",
        TravelMode.DRIVE: "driving-car",
    }


@pytest.mark.asyncio
async def test_ors_matrix_uses_lon_lat_and_real_metrics():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/openrouteservice/v2/matrix/cycling-regular"
        assert request.headers["Authorization"] == "test-key"
        payload = json.loads(request.content)
        assert payload["locations"] == [
            [19.9372, 50.0614],
            [19.945, 50.0647],
        ]
        return httpx.Response(
            200,
            json={
                "distances": [[0, 1234.4], [1198.2, 0]],
                "durations": [[0, 321.2], [305.8, 0]],
            },
        )

    service = OpenRouteService(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )
    connections = await service.get_matrix_connections(
        [
            make_poi("start", 50.0614, 19.9372),
            make_poi("museum", 50.0647, 19.945),
        ],
        TravelMode.BICYCLE,
    )

    assert len(connections) == 2
    assert connections[0].distance_m == 1234
    assert connections[0].duration.total_seconds() == pytest.approx(321.2)
    assert connections[0].routing_fallback is False


@pytest.mark.asyncio
async def test_ors_direction_keeps_geojson_and_summary():
    geometry = {
        "type": "LineString",
        "coordinates": [
            [19.9372, 50.0614],
            [19.94, 50.063],
            [19.945, 50.0647],
        ],
    }

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == (
            "/openrouteservice/v2/directions/foot-walking/geojson"
        )
        payload = json.loads(request.content)
        assert payload["coordinates"] == [
            [19.9372, 50.0614],
            [19.945, 50.0647],
        ]
        return httpx.Response(
            200,
            json={
                "type": "FeatureCollection",
                "features": [
                    {
                        "type": "Feature",
                        "geometry": geometry,
                        "properties": {
                            "summary": {
                                "distance": 1400.4,
                                "duration": 900.2,
                            }
                        },
                    }
                ],
            },
        )

    service = OpenRouteService(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )
    connection = await service.get_direction(
        make_poi("start", 50.0614, 19.9372),
        make_poi("museum", 50.0647, 19.945),
        TravelMode.WALK,
    )

    assert connection.distance_m == 1400
    assert connection.duration.total_seconds() == pytest.approx(900.2)
    assert connection.geometry == geometry
    assert connection.routing_fallback is False


@pytest.mark.asyncio
async def test_planning_falls_back_when_ors_matrix_fails():
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("timeout")

    routing_service = OpenRouteService(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )
    planning_service = PlanningService(routing_service=routing_service)

    connections = await planning_service._get_connections(
        [
            make_poi("start", 50.0614, 19.9372),
            make_poi("museum", 50.0647, 19.945),
        ],
        TravelMode.WALK,
    )

    assert len(connections) == 2
    assert all(connection.routing_fallback for connection in connections)


@pytest.mark.asyncio
async def test_ors_matrix_drives_optimizer_and_timeline_from_user_start():
    start_at = datetime(2026, 10, 4, 10, 0)
    user_start = POI(
        id="__user_start__",
        name="Twoja lokalizacja",
        location=Coordinates(lat=50.0477, lng=19.9591),
        visit_cost=CostVector(),
        reward=0,
    )
    wawel = POI(
        id="wawel",
        name="Wawel",
        location=Coordinates(lat=50.0540, lng=19.9352),
        visit_cost=CostVector(time_s=60 * 60),
        reward=10,
    )
    rynek = POI(
        id="rynek",
        name="Rynek",
        location=Coordinates(lat=50.0617, lng=19.9373),
        visit_cost=CostVector(time_s=60 * 60),
        reward=10,
    )
    pois = [user_start, wawel, rynek]

    def handler(request: httpx.Request) -> httpx.Response:
        payload = json.loads(request.content)
        # The user's real GPS is the first matrix node, in ORS [lon, lat] order.
        assert payload["locations"][0] == [19.9591, 50.0477]
        return httpx.Response(
            200,
            json={
                "distances": [
                    [0, 1_000, 8_000],
                    [1_000, 0, 600],
                    [8_000, 600, 0],
                ],
                "durations": [
                    [0, 13 * 60, 100 * 60],
                    [13 * 60, 0, 8 * 60],
                    [100 * 60, 8 * 60, 0],
                ],
            },
        )

    routing_service = OpenRouteService(
        api_key="test-key",
        transport=httpx.MockTransport(handler),
    )
    planning_service = PlanningService(routing_service=routing_service)
    connections = await planning_service._get_connections(pois, TravelMode.WALK)
    connection_by_ids = {
        (connection.from_poi_id, connection.to_poi_id): connection
        for connection in connections
    }
    assert connection_by_ids[(user_start.id, wawel.id)].distance_m == 1_000
    assert connection_by_ids[(wawel.id, rynek.id)].distance_m == 600
    assert not connection_by_ids[(user_start.id, wawel.id)].routing_fallback
    constraints = PlanningConstraints(
        start_poi_id=user_start.id,
        days=1,
        travel_mode=TravelMode.WALK,
        budget_per_route=OptionalCostVector(time_s=150 * 60),
        must_visit_ids=[wawel.id, rynek.id],
        day_start=start_at.time(),
        plan_date=start_at,
    )

    solver_input = SimpleSolverEncoder().encode(pois, connections, constraints)
    edge_by_ids = {
        (
            solver_input.nodes[edge.source].poi_id,
            solver_input.nodes[edge.target].poi_id,
        ): edge.cost
        for edge in solver_input.edges
    }
    assert edge_by_ids[(user_start.id, wawel.id)].time_s == 13 * 60
    assert edge_by_ids[(wawel.id, rynek.id)].time_s == 8 * 60

    result = OrToolsSolver(time_limit_s=1).solve(solver_input)
    plan = SimpleSolverDecoder().decode(
        result,
        solver_input,
        pois,
        connections,
        constraints,
    )
    stops = plan.days[0].stops

    assert [stop.poi.id for stop in stops] == [user_start.id, wawel.id, rynek.id]
    assert stops[0].arrival == start_at
    assert stops[0].departure == start_at
    assert stops[1].arrival == start_at + timedelta(minutes=13)
    assert stops[1].departure == start_at + timedelta(minutes=73)
    assert stops[2].arrival == start_at + timedelta(minutes=81)
    assert stops[2].connection_from_previous is not None
    assert stops[2].connection_from_previous.duration == timedelta(minutes=8)
    assert plan.total_cost.time_s == 141 * 60
