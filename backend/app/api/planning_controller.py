"""Kontroler API dla planowania trasy na podstawie odpowiedzi LLM."""
from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from fastapi import APIRouter, HTTPException, status

from schemas.llm import LLMOutput
from schemas.planning import (
    Coordinates,
    CostWeights,
    OptionalCostVector,
    Plan,
    PlanningRequest,
    PlanningConstraints,
    TravelMode,
)
from service.planning_json_poi_service import JsonPOIService
from service.planning_or_solver import OrToolsSolver
from service.planning_poi_filter_service import PreferencePOIFilterService
from service.planning_simple_connection_service import SimpleConnectionService
from service.planning_simple_solver_decoder import SimpleSolverDecoder
from service.planning_simple_solver_encoder import SimpleSolverEncoder


router = APIRouter(prefix="/planning", tags=["planning"])

_DATASET_PATH = (
    Path(__file__).parents[2]
    / "resources"
    / "dataset_crawler-google-places_2026-10-03_15-34-29-547.json"
)
_SEARCH_RADIUS_M = 25_000
_CANDIDATE_LIMITS = (30, 60, 100)
_BUDGET_BY_STRATEGY: dict[str, Decimal] = {
    "cheapest": Decimal("50"),
    "fastest": Decimal("150"),
    "most_places": Decimal("300"),
    "least_crowded": Decimal("150"),
}


@router.post("", response_model=list[Plan], status_code=status.HTTP_200_OK)
async def create_plans(payload: LLMOutput) -> list[Plan]:
    """Mapuje wynik LLM na domenę i uruchamia pełny pipeline planowania."""
    request = _to_planning_request(payload)
    mode = _select_travel_mode(request)
    poi_service = JsonPOIService(_DATASET_PATH)

    pois = await poi_service.get_pois(
        query="",
        center=request.start_location,
        radius_m=_SEARCH_RADIUS_M,
    )
    if not pois:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nie znaleziono POI w obszarze planowania.",
        )

    plans: list[Plan] = []
    seen: set[str] = set()
    for limit in _CANDIDATE_LIMITS:
        filtered_pois = PreferencePOIFilterService(
            max_results=limit,
            max_distance_m=_SEARCH_RADIUS_M,
        ).filter_pois(pois, request)
        if not filtered_pois:
            continue

        constraints = _to_constraints(request, mode)
        connection_service = SimpleConnectionService()
        connections = await connection_service.get_connections(filtered_pois, mode)
        solver_input = SimpleSolverEncoder().encode(
            filtered_pois,
            connections,
            constraints,
        )
        result = OrToolsSolver(time_limit_s=5).solve(solver_input)
        plan = SimpleSolverDecoder().decode(
            result,
            solver_input,
            filtered_pois,
            connections,
            constraints,
        )

        fingerprint = plan.model_dump_json()
        if fingerprint in seen:
            continue
        seen.add(fingerprint)
        plans.append(plan)
        if len(plans) == 3:
            break

    if not plans:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Nie udało się utworzyć wykonalnego planu.",
        )
    return plans


def _to_planning_request(payload: LLMOutput) -> PlanningRequest:
    return PlanningRequest(
        start_at=payload.start_at,
        end_at=payload.end_at,
        start_location=_coordinates(payload.start_location),
        end_location=(
            _coordinates(payload.end_location)
            if payload.end_location is not None
            else None
        ),
        budget_pln=_budget_for_strategy(payload.optimization_strategy),
        preferred_categories=payload.preferred_categories,
        food_preferences=payload.food_preferences,
        transport_modes=[
            _parse_travel_mode(mode) for mode in payload.transport_modes
        ],
        prefer_walking="walking" in payload.transport_modes,
        avoid_crowds=payload.avoid_crowds,
        weather_sensitive=payload.weather_sensitive,
        optimization_strategy=payload.optimization_strategy,
        excluded_categories=payload.excluded_categories,
    )


def _budget_for_strategy(strategy: str) -> Decimal:
    return _BUDGET_BY_STRATEGY[strategy]


def _coordinates(value) -> Coordinates:
    return Coordinates(lat=value.latitude, lng=value.longitude)


def _parse_travel_mode(value: str) -> TravelMode:
    aliases = {
        "walking": TravelMode.WALK,
        "walk": TravelMode.WALK,
        "bicycle": TravelMode.BICYCLE,
        "cycling": TravelMode.BICYCLE,
        "transit": TravelMode.TRANSIT,
        "public_transport": TravelMode.TRANSIT,
        "tram": TravelMode.TRANSIT,
        "drive": TravelMode.DRIVE,
        "driving": TravelMode.DRIVE,
        "taxi": TravelMode.DRIVE,
        "car": TravelMode.DRIVE,
        "scooter": TravelMode.BICYCLE,
    }
    try:
        return aliases[value.casefold().strip()]
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Nieobsługiwany środek transportu: {value}",
        ) from exc


def _select_travel_mode(request: PlanningRequest) -> TravelMode:
    if request.prefer_walking:
        return TravelMode.WALK
    if request.transport_modes:
        return request.transport_modes[0]
    return TravelMode.WALK


def _to_constraints(
    request: PlanningRequest,
    mode: TravelMode,
) -> PlanningConstraints:
    duration_s = max(1, round((request.end_at - request.start_at).total_seconds()))
    budget_minor = max(0, int(request.budget_pln * Decimal("100")))
    return PlanningConstraints(
        days=1,
        travel_mode=mode,
        budget_per_route=OptionalCostVector(
            time_s=duration_s,
            money_minor=budget_minor,
        ),
        weights=CostWeights(),
        day_start=request.start_at.time(),
        plan_date=request.start_at,
    )
