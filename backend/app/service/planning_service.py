"""Application service that turns normalized LLM preferences into trip plans."""

from __future__ import annotations

import asyncio
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from app.schemas.llm import Coordinates as LLMCoordinates
from app.schemas.llm import LLMOutput
from app.schemas.planning import (
    Coordinates,
    CostVector,
    CostWeights,
    IPOICostService,
    OptionalCostVector,
    Plan,
    PlanDay,
    PlanningConstraints,
    PlanningRequest,
    PlanningResultResponse,
    RoutePlan,
    TravelMode,
)
from app.service.planning_json_poi_service import JsonPOIService
from app.service.planning_mapper import RoutePlanMapper
from app.service.planning_or_solver import OrToolsSolver
from app.service.planning_ollama_poi_cost_service import OllamaPOICostService
from app.service.planning_poi_filter_service import PreferencePOIFilterService
from app.service.planning_simple_connection_service import SimpleConnectionService
from app.service.planning_simple_solver_decoder import SimpleSolverDecoder
from app.service.planning_simple_solver_encoder import SimpleSolverEncoder

DEFAULT_DATASET_PATH = (
    Path(__file__).parents[2]
    / "resources"
    / "dataset_crawler-google-places_2026-10-03_15-34-29-547.json"
)


class PlanningServiceError(Exception):
    """Base error raised by the planning pipeline."""


class NoPoisFoundError(PlanningServiceError):
    """Raised when no points of interest are available for planning."""


class NoFeasiblePlanError(PlanningServiceError):
    """Raised when the solver cannot produce a feasible plan."""


class UnsupportedTransportModeError(PlanningServiceError):
    """Raised when an LLM transport mode cannot be mapped to the planner."""


class PlanningService:
    def __init__(
        self,
        dataset_path: Path = DEFAULT_DATASET_PATH,
        search_radius_m: int = 25_000,
        candidate_limits: tuple[int, ...] = (30, 60, 100),
        poi_cost_service: IPOICostService | None = None,
    ) -> None:
        self._dataset_path = dataset_path
        self._search_radius_m = search_radius_m
        self._candidate_limits = candidate_limits
        self._poi_cost_service = poi_cost_service or OllamaPOICostService()
        self._statuses: dict[UUID, str] = {}
        self._results: dict[UUID, list[Plan]] = {}
        self._routes: dict[UUID, RoutePlan] = {}
        self._llm_outputs: dict[UUID, LLMOutput] = {}
        self._errors: dict[UUID, str] = {}

    def mark_planning(self, user_id: UUID) -> None:
        self._statuses[user_id] = "planning"
        self._results.pop(user_id, None)
        self._routes.pop(user_id, None)
        self._llm_outputs.pop(user_id, None)
        self._errors.pop(user_id, None)

    def mark_failed(self, user_id: UUID, error: str) -> None:
        self._statuses[user_id] = "failed"
        self._errors[user_id] = error

    def get_result(self, user_id: UUID) -> PlanningResultResponse | None:
        status = self._statuses.get(user_id)
        if status is None:
            return None

        return PlanningResultResponse(
            status=status,
            plan=self._routes.get(user_id),
            plans=self._results.get(user_id),
            llm_output=self._llm_outputs.get(user_id),
            error=self._errors.get(user_id),
        )

    async def create_plans_for_user(
        self,
        user_id: UUID,
        payload: LLMOutput,
    ) -> list[Plan]:
        self.mark_planning(user_id)
        self._llm_outputs[user_id] = payload

        try:
            plans = await self.create_plans(payload)
            selected_plan = self._select_plan(plans, payload.optimization_strategy)
            request = self._to_planning_request(payload)
            route = RoutePlanMapper().to_route_plan(selected_plan, request)
            if route is None:
                raise NoFeasiblePlanError("Planner nie zwrócił trasy do wyświetlenia.")
        except Exception as exc:
            self.mark_failed(user_id, str(exc))
            raise

        self._results[user_id] = plans
        self._routes[user_id] = route
        self._statuses[user_id] = "ready"
        return plans

    @staticmethod
    def _select_plan(plans: list[Plan], strategy: str) -> Plan:
        def attractions_count(plan: Plan) -> int:
            return sum(len(day.stops) for day in plan.days)

        usable_plans = [plan for plan in plans if attractions_count(plan) > 0]
        if not usable_plans:
            raise NoFeasiblePlanError("Planner nie zwrócił wykonalnej trasy.")

        if strategy == "cheapest":
            return min(
                usable_plans,
                key=lambda plan: (
                    plan.total_cost.money_minor,
                    -attractions_count(plan),
                    plan.total_cost.time_s,
                ),
            )
        if strategy == "fastest":
            return min(
                usable_plans,
                key=lambda plan: (
                    plan.total_cost.time_s,
                    -attractions_count(plan),
                ),
            )
        if strategy == "most_places":
            return max(
                usable_plans,
                key=lambda plan: (
                    attractions_count(plan),
                    plan.total_reward,
                    -plan.total_cost.time_s,
                ),
            )
        return max(
            usable_plans,
            key=lambda plan: (
                plan.total_reward,
                attractions_count(plan),
                -plan.total_cost.time_s,
            ),
        )

    async def create_plans(self, payload: LLMOutput) -> list[Plan]:
        request = self._to_planning_request(payload)
        mode = self._select_travel_mode(request)
        poi_service = JsonPOIService(self._dataset_path)

        pois = await poi_service.get_pois(
            query="",
            center=request.start_location,
            radius_m=self._search_radius_m,
        )
        if not pois:
            raise NoPoisFoundError("Nie znaleziono POI w obszarze planowania.")

        plans: list[Plan] = []
        seen: set[tuple[tuple[str, ...], ...]] = set()

        for limit in self._candidate_limits:
            filtered_pois = PreferencePOIFilterService(
                max_results=limit,
                max_distance_m=self._search_radius_m,
            ).filter_pois(pois, request)
            if not filtered_pois:
                continue

            constraints = self._to_constraints(request, mode)
            connections = await SimpleConnectionService().get_connections(
                filtered_pois,
                mode,
            )
            solver_input = SimpleSolverEncoder().encode(
                filtered_pois,
                connections,
                constraints,
            )
            result = await asyncio.to_thread(
                OrToolsSolver(time_limit_s=5).solve,
                solver_input,
            )
            plan = SimpleSolverDecoder().decode(
                result,
                solver_input,
                filtered_pois,
                connections,
                constraints,
            )
            plan = await self._enrich_plan_costs(plan)

            # Candidate limits can produce the same route with a different
            # skipped_poi_ids list. Only the actual itinerary identifies a
            # distinct plan returned to the client.
            fingerprint = tuple(
                tuple(stop.poi.id for stop in day.stops) for day in plan.days
            )
            if fingerprint in seen:
                continue

            seen.add(fingerprint)
            plans.append(plan)
            if len(plans) == 3:
                break

        if not plans:
            raise NoFeasiblePlanError("Nie udało się utworzyć wykonalnego planu.")

        return plans

    async def _enrich_plan_costs(self, plan: Plan) -> Plan:
        """Uzupełnij koszty wyłącznie dla POI obecnych w zdekodowanej trasie."""
        pois = {
            stop.poi.id: stop.poi
            for day in plan.days
            for stop in day.stops
        }
        if not pois:
            return plan

        enriched = {
            poi_id: await self._poi_cost_service.enrich_poi_cost(poi)
            for poi_id, poi in pois.items()
        }
        days: list[PlanDay] = []
        for day in plan.days:
            stops = [
                stop.model_copy(update={"poi": enriched[stop.poi.id]})
                for stop in day.stops
            ]
            time_delta = sum(
                stop.poi.visit_cost.time_s - original.poi.visit_cost.time_s
                for stop, original in zip(stops, day.stops)
            )
            money_delta = sum(
                stop.poi.visit_cost.money_minor - original.poi.visit_cost.money_minor
                for stop, original in zip(stops, day.stops)
            )
            days.append(
                day.model_copy(
                    update={
                        "stops": stops,
                        "total_cost": CostVector(
                            time_s=day.total_cost.time_s + time_delta,
                            money_minor=day.total_cost.money_minor + money_delta,
                        ),
                    }
                )
            )

        return plan.model_copy(
            update={
                "days": days,
                "total_cost": sum((day.total_cost for day in days), CostVector()),
            }
        )

    def _to_planning_request(self, payload: LLMOutput) -> PlanningRequest:
        return PlanningRequest(
            start_at=payload.start_at,
            end_at=payload.end_at,
            start_location=self._coordinates(payload.start_location),
            end_location=(
                self._coordinates(payload.end_location)
                if payload.end_location is not None
                else None
            ),
            budget_pln=self._budget_for_strategy(payload.optimization_strategy),
            preferred_categories=payload.preferred_categories,
            food_preferences=payload.food_preferences,
            transport_modes=[
                self._parse_travel_mode(mode) for mode in payload.transport_modes
            ],
            prefer_walking="walking" in payload.transport_modes,
            avoid_crowds=payload.avoid_crowds,
            weather_sensitive=payload.weather_sensitive,
            optimization_strategy=payload.optimization_strategy,
            excluded_categories=payload.excluded_categories,
        )

    @staticmethod
    def _budget_for_strategy(strategy: str) -> Decimal:
        budgets = {
            "cheapest": Decimal("50"),
            "fastest": Decimal("150"),
            "most_places": Decimal("300"),
            "least_crowded": Decimal("150"),
        }
        return budgets[strategy]

    @staticmethod
    def _coordinates(value: LLMCoordinates) -> Coordinates:
        return Coordinates(lat=value.latitude, lng=value.longitude)

    @staticmethod
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
            raise UnsupportedTransportModeError(
                f"Nieobsługiwany środek transportu: {value}"
            ) from exc

    @staticmethod
    def _select_travel_mode(request: PlanningRequest) -> TravelMode:
        if request.prefer_walking:
            return TravelMode.WALK
        if request.transport_modes:
            return request.transport_modes[0]
        return TravelMode.WALK

    @staticmethod
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


planning_service = PlanningService()
