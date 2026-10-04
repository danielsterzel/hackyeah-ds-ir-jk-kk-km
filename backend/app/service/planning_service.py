"""Application service that turns normalized LLM preferences into trip plans."""

from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from pathlib import Path
from uuid import UUID

from app.schemas.llm import Coordinates as LLMCoordinates
from app.schemas.llm import LLMOutput
from app.schemas.planning import (
    Coordinates,
    CostVector,
    CostWeights,
    OptionalCostVector,
    Plan,
    POI,
    POIConnection,
    PlanningConstraints,
    PlanningRequest,
    PlanningResultResponse,
    ROUTE_START_POI_ID,
    RoutePlan,
    TravelMode,
)
from app.service.planning_json_poi_service import JsonPOIService
from app.service.planning_mapper import RoutePlanMapper
from app.service.planning_or_solver import OrToolsSolver
from app.service.planning_ors_routing_service import OpenRouteService
from app.service.planning_poi_filter_service import (
    PreferencePOIFilterService,
    food_preference_matches,
)
from app.service.planning_simple_connection_service import SimpleConnectionService
from app.service.planning_simple_solver_decoder import SimpleSolverDecoder
from app.service.planning_simple_solver_encoder import SimpleSolverEncoder
from app.service.ticket_price.ticket_price import TicketService

DEFAULT_DATASET_PATH = (
    Path(__file__).parents[2]
    / "resources"
    / "dataset_crawler-google-places_2026-10-03_15-34-29-547.json"
)
MOST_PLACES_REWARD = 1_000.0
MOST_PLACES_PREFERRED_BONUS = 10.0
MOST_PLACES_FOOD_BONUS = 5.0


class PlanningServiceError(Exception):
    """Base error raised by the planning pipeline."""


class NoPoisFoundError(PlanningServiceError):
    """Raised when no points of interest are available for planning."""


class NoFeasiblePlanError(PlanningServiceError):
    """Raised when the solver cannot produce a feasible plan."""


class UnsupportedTransportModeError(PlanningServiceError):
    """Raised when an LLM transport mode cannot be mapped to the planner."""


class PlanningService:
    _MAX_TICKET_LOOKUPS_PER_PLAN = 12

    def __init__(
        self,
        dataset_path: Path = DEFAULT_DATASET_PATH,
        search_radius_m: int = 25_000,
        candidate_limits: tuple[int, ...] = (30,),
        routing_service: OpenRouteService | None = None,
    ) -> None:
        self._dataset_path = dataset_path
        self._search_radius_m = search_radius_m
        self._candidate_limits = candidate_limits
        self._statuses: dict[UUID, str] = {}
        self._results: dict[UUID, list[Plan]] = {}
        self._routes: dict[UUID, RoutePlan] = {}
        self._llm_outputs: dict[UUID, LLMOutput] = {}
        self._errors: dict[UUID, str] = {}
        self._ticket_service = TicketService()
        self._routing_service = routing_service or OpenRouteService()

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
            mode = self._select_travel_mode(request)
            selected_plan = await self._add_route_geometries(selected_plan, mode)
            selected_plan = await self._add_ticket_prices_to_plan(selected_plan)
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
            return sum(
                stop.poi.id != ROUTE_START_POI_ID
                for day in plan.days
                for stop in day.stops
            )

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
            filtered_pois = self._apply_strategy_rewards(
                filtered_pois,
                request.optimization_strategy,
                preferred_categories=request.preferred_categories,
                food_preferences=request.food_preferences,
            )

            start_poi = POI(
                id=ROUTE_START_POI_ID,
                name="Twoja lokalizacja",
                location=request.start_location,
                visit_cost=CostVector(),
                reward=0,
            )
            route_pois = [start_poi, *filtered_pois]
            constraints = self._to_constraints(request, mode).model_copy(
                update={"start_poi_id": ROUTE_START_POI_ID}
            )
            connections = await self._get_connections(route_pois, mode)
            solver_input = SimpleSolverEncoder().encode(
                route_pois,
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
                route_pois,
                connections,
                constraints,
            )

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

    @staticmethod
    def _apply_strategy_rewards(
        pois: list[POI],
        strategy: str,
        *,
        preferred_categories: list[str] | None = None,
        food_preferences: list[str] | None = None,
    ) -> list[POI]:
        if strategy != "most_places":
            return pois
        # A large, equal reward makes dropping any additional feasible POI
        # more expensive than travel-time tie breakers in the routing model.
        # Small bonuses preserve interview preferences when route counts tie.
        preferred_categories = preferred_categories or []
        food_preferences = food_preferences or []
        updated: list[POI] = []
        for poi in pois:
            type_tags = {item.casefold() for item in poi.types}
            reward = MOST_PLACES_REWARD
            if any(item.casefold() in type_tags for item in preferred_categories):
                reward += MOST_PLACES_PREFERRED_BONUS
            if food_preference_matches(poi, food_preferences):
                reward += MOST_PLACES_FOOD_BONUS
            updated.append(poi.model_copy(update={"reward": reward}))
        return updated

    async def _get_connections(
        self,
        pois: list[POI],
        mode: TravelMode,
    ) -> list[POIConnection]:
        fallback = await SimpleConnectionService().get_connections(pois, mode)
        if not self._routing_service.supports(mode):
            return fallback

        try:
            routed = await self._routing_service.get_matrix_connections(pois, mode)
        except Exception:
            logging.getLogger(__name__).exception(
                "ORS matrix routing failed; using simple routing fallback"
            )
            return fallback

        routed_by_pair = {
            (connection.from_poi_id, connection.to_poi_id): connection
            for connection in routed
        }
        return [
            routed_by_pair.get(
                (connection.from_poi_id, connection.to_poi_id),
                connection,
            )
            for connection in fallback
        ]

    async def _add_route_geometries(
        self,
        plan: Plan,
        mode: TravelMode,
    ) -> Plan:
        if not self._routing_service.supports(mode):
            return plan

        updated_days = []
        for day in plan.days:
            updated_stops = []
            money_minor = 0
            for stop in day.stops:
                connection = stop.connection_from_previous
                arrival = stop.arrival
                departure = stop.departure

                if updated_stops and connection is not None:
                    previous = updated_stops[-1]
                    if not connection.routing_fallback:
                        try:
                            connection = await self._routing_service.get_direction(
                                previous.poi,
                                stop.poi,
                                mode,
                            )
                        except Exception:
                            logging.getLogger(__name__).exception(
                                "ORS directions routing failed for %s -> %s; "
                                "keeping matrix leg without geometry",
                                previous.poi.id,
                                stop.poi.id,
                            )

                    earliest_arrival = previous.departure + connection.duration
                    arrival = max(arrival, earliest_arrival)
                    departure = arrival + (stop.departure - stop.arrival)
                    money_minor += round(connection.fuel_cost * 100)

                money_minor += stop.poi.visit_cost.money_minor
                updated_stops.append(
                    stop.model_copy(
                        update={
                            "arrival": arrival,
                            "departure": departure,
                            "connection_from_previous": connection,
                        }
                    )
                )

            time_s = (
                max(
                    0,
                    round(
                        (
                            updated_stops[-1].departure - updated_stops[0].arrival
                        ).total_seconds()
                    ),
                )
                if updated_stops
                else 0
            )
            updated_days.append(
                day.model_copy(
                    update={
                        "stops": updated_stops,
                        "total_cost": CostVector(
                            time_s=time_s,
                            money_minor=money_minor,
                        ),
                    }
                )
            )

        return plan.model_copy(
            update={
                "days": updated_days,
                "total_cost": sum(
                    (day.total_cost for day in updated_days),
                    CostVector(),
                ),
            }
        )

    def _to_planning_request(self, payload: LLMOutput) -> PlanningRequest:
        transport_modes = [
            self._parse_travel_mode(mode) for mode in payload.transport_modes
        ]

        return PlanningRequest(
            start_at=payload.start_at,
            end_at=payload.end_at,
            start_location=self._coordinates(payload.start_location),
            end_location=(
                self._coordinates(payload.end_location)
                if payload.end_location is not None
                else None
            ),
            budget_pln=payload.budget_pln,
            preferred_categories=payload.preferred_categories,
            food_preferences=payload.food_preferences,
            transport_modes=transport_modes,
            # The interview orders modes from the user's primary preference to
            # acceptable fallbacks. Walking should affect POI filtering only
            # when it is the preferred mode, not merely one of the alternatives.
            prefer_walking=bool(
                transport_modes and transport_modes[0] == TravelMode.WALK
            ),
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

    async def _add_ticket_prices_to_plan(self, plan: Plan) -> Plan:
        updated_days = []
        ticket_cost_delta = 0

        for day in plan.days:
            updated_stops = []
            for stop in day.stops:
                if stop.poi.id == ROUTE_START_POI_ID:
                    updated_stops.append(stop)
                    continue
                poi = stop.poi
                old_price = poi.visit_cost.money_minor
                try:
                    ticket = await self._ticket_service.get_ticket_info(poi.name)
                except Exception:
                    logging.getLogger(__name__).exception(
                        "Ticket price lookup failed for %s; using static fallback",
                        poi.name,
                    )
                    ticket = self._ticket_service.get_fallback_ticket_info(poi.name)

                price = ticket.max_price
                if price is None:
                    price = ticket.min_price
                if price is None:
                    updated_stops.append(stop)
                    continue

                new_price = max(0, round(price * 100))
                ticket_cost_delta += new_price - old_price
                updated_stops.append(
                    stop.model_copy(
                        update={
                            "poi": poi.model_copy(
                                update={
                                    "visit_cost": poi.visit_cost.model_copy(
                                        update={"money_minor": new_price}
                                    ),
                                    "ticket_price_known": True,
                                }
                            )
                        }
                    )
                )

            updated_days.append(day.model_copy(update={"stops": updated_stops}))

        return plan.model_copy(
            update={
                "days": updated_days,
                "total_cost": plan.total_cost.model_copy(
                    update={
                        "money_minor": max(
                            0,
                            plan.total_cost.money_minor + ticket_cost_delta,
                        )
                    }
                ),
            }
        )

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
            day_start=request.start_at.timetz(),
            plan_date=request.start_at,
        )


planning_service = PlanningService()
