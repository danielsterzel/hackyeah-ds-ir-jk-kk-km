"""Plan -> PlotterPayload (punkty, odcinki i obszar mapy dla plotera)."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Literal, get_args

from app.schemas.llm import PlaceCategory
from app.schemas.planning import (
    Coordinates,
    IPlanningMapper,
    Plan,
    PlanStop,
    PlanningRequest,
    PlotPoint,
    PlotSegment,
    PlotterPayload,
    RouteLeg,
    RoutePlace,
    RoutePlan,
    RouteStop,
    RouteSummary,
    RouteWarning,
    TravelMode,
)

INTERNAL_CATEGORIES = set(get_args(PlaceCategory))
CLOSES_SOON_THRESHOLD = timedelta(minutes=45)


class SimplePlanningMapper(IPlanningMapper):
    def __init__(self, fallback_mode: TravelMode = TravelMode.WALK) -> None:
        # tryb używany, gdy odcinek nie ma przypisanego połączenia
        self._fallback_mode = fallback_mode

    def to_plotter(self, plan: Plan) -> PlotterPayload:
        points: list[PlotPoint] = []
        segments: list[PlotSegment] = []

        for day in plan.days:
            previous: PlotPoint | None = None
            for stop in day.stops:
                point = PlotPoint(
                    poi_id=stop.poi.id,
                    label=stop.poi.name,
                    order=stop.order,
                    location=stop.poi.location,
                    day_index=day.day_index,
                )
                points.append(point)

                if previous is not None:
                    conn = stop.connection_from_previous
                    polyline = conn.polyline if conn else None
                    segments.append(
                        PlotSegment(
                            from_poi_id=previous.poi_id,
                            to_poi_id=point.poi_id,
                            day_index=day.day_index,
                            mode=conn.mode if conn else self._fallback_mode,
                            polyline=polyline,
                            # bez polyline plotter rysuje prostą linię między punktami
                            path=(
                                None
                                if polyline
                                else [previous.location, point.location]
                            ),
                        )
                    )
                previous = point

        sw, ne = self._bounds([p.location for p in points])
        return PlotterPayload(
            points=points, segments=segments, bounds_sw=sw, bounds_ne=ne
        )

    @staticmethod
    def _bounds(
        locations: list[Coordinates],
    ) -> tuple[Coordinates | None, Coordinates | None]:
        if not locations:
            return None, None
        lats = [c.lat for c in locations]
        lngs = [c.lng for c in locations]
        return (
            Coordinates(lat=min(lats), lng=min(lngs)),
            Coordinates(lat=max(lats), lng=max(lngs)),
        )


class RoutePlanMapper:
    """Maps the solver's domain Plan to the stable response consumed by the map."""

    def to_route_plan(
        self,
        plan: Plan,
        request: PlanningRequest,
    ) -> RoutePlan | None:
        day = next((item for item in plan.days if item.stops), None)
        if day is None:
            return None

        route_stops = [
            self._to_route_stop(stop, day.day_index, index + 1)
            for index, stop in enumerate(day.stops)
        ]
        legs: list[RouteLeg] = []
        warnings: list[RouteWarning] = []

        for index, stop in enumerate(day.stops[1:]):
            previous = day.stops[index]
            connection = stop.connection_from_previous
            leg_id = f"day-{day.day_index}-leg-{index + 1}"
            mode = self._route_mode(
                connection.mode
                if connection is not None
                else next(iter(request.transport_modes), TravelMode.WALK)
            )
            duration_min = (
                round(connection.duration.total_seconds() / 60)
                if connection is not None
                else round((stop.arrival - previous.departure).total_seconds() / 60)
            )

            legs.append(
                RouteLeg(
                    id=leg_id,
                    from_stop_id=route_stops[index].id,
                    to_stop_id=route_stops[index + 1].id,
                    mode=mode,
                    distance_m=connection.distance_m if connection is not None else 0,
                    duration_min=max(0, duration_min),
                    cost_pln=connection.fuel_cost if connection is not None else 0,
                    # Until a street-routing provider is connected, the map has a
                    # stable fallback: a straight segment in Leaflet [lat, lng] order.
                    coords=[
                        (previous.poi.location.lat, previous.poi.location.lng),
                        (stop.poi.location.lat, stop.poi.location.lng),
                    ],
                )
            )
            if connection is None or connection.polyline is None:
                warnings.append(
                    RouteWarning(
                        code="ROUTING_FALLBACK",
                        message=(
                            "Ten odcinek jest obecnie pokazany jako linia prosta. "
                            "Rzeczywista trasa ulicami może być dłuższa."
                        ),
                        leg_id=leg_id,
                    )
                )

        total_distance_m = sum(leg.distance_m for leg in legs)
        total_walking_m = sum(leg.distance_m for leg in legs if leg.mode == "walk")
        allowed_time_s = max(
            0, round((request.end_at - request.start_at).total_seconds())
        )
        time_over_s = max(0, plan.total_cost.time_s - allowed_time_s)

        if time_over_s:
            warnings.append(
                RouteWarning(
                    code="TIME_EXCEEDED",
                    message="Plan przekracza dostępny czas.",
                )
            )
        return RoutePlan(
            strategy=request.optimization_strategy,
            solver_status=plan.status,
            objective_value=plan.objective_value,
            total_reward=plan.total_reward,
            summary=RouteSummary(
                total_cost_pln=plan.total_cost.money_minor / 100,
                total_duration_min=round(plan.total_cost.time_s / 60),
                total_distance_m=total_distance_m,
                total_walking_m=total_walking_m,
                attractions_count=len(route_stops),
                fits_time=time_over_s == 0,
                # The current planner has an internal technical limit, but the
                # user does not provide a real budget yet.
                fits_budget=None,
                time_over_min=round(time_over_s / 60),
                budget_over_pln=None,
            ),
            stops=route_stops,
            legs=legs,
            warnings=warnings,
            skipped_poi_ids=plan.skipped_poi_ids,
        )

    def _to_route_stop(
        self,
        stop: PlanStop,
        day_index: int,
        order: int,
    ) -> RouteStop:
        stop_id = f"day-{day_index}-stop-{order}"
        opens_at, closes_at, warnings = self._opening_window(stop, stop_id)
        category = next(
            (item for item in stop.poi.types if item in INTERNAL_CATEGORIES),
            stop.poi.types[0] if stop.poi.types else None,
        )

        return RouteStop(
            id=stop_id,
            order=order,
            kind="attraction",
            place=RoutePlace(
                id=stop.poi.id,
                name=stop.poi.name,
                lat=stop.poi.location.lat,
                lng=stop.poi.location.lng,
                category=category,
                address=stop.poi.address,
            ),
            arrival_at=stop.arrival,
            departure_at=stop.departure,
            visit_duration_min=max(
                0, round((stop.departure - stop.arrival).total_seconds() / 60)
            ),
            price_pln=(
                stop.poi.visit_cost.money_minor / 100
                if stop.poi.visit_cost.money_minor > 0
                else None
            ),
            opens_at=opens_at,
            closes_at=closes_at,
            warnings=warnings,
        )

    @staticmethod
    def _opening_window(
        stop: PlanStop,
        stop_id: str,
    ) -> tuple[datetime | None, datetime | None, list[RouteWarning]]:
        if not stop.poi.opening_hours:
            return (
                None,
                None,
                [
                    RouteWarning(
                        code="OPENING_HOURS_UNKNOWN",
                        message="Brak potwierdzonych godzin otwarcia dla tego miejsca.",
                        stop_id=stop_id,
                    )
                ],
            )

        for period in stop.poi.opening_hours:
            if period.day_of_week != stop.arrival.weekday():
                continue
            opens_at = datetime.combine(
                stop.arrival.date(), period.open, tzinfo=stop.arrival.tzinfo
            )
            closes_at = datetime.combine(
                stop.arrival.date(), period.close, tzinfo=stop.arrival.tzinfo
            )
            if closes_at <= opens_at:
                closes_at += timedelta(days=1)
            if opens_at <= stop.arrival and stop.departure <= closes_at:
                warnings: list[RouteWarning] = []
                if closes_at - stop.departure <= CLOSES_SOON_THRESHOLD:
                    warnings.append(
                        RouteWarning(
                            code="CLOSES_SOON",
                            message="Miejsce zamyka się niedługo po planowanej wizycie.",
                            stop_id=stop_id,
                        )
                    )
                return opens_at, closes_at, warnings

        return (
            None,
            None,
            [
                RouteWarning(
                    code="OPENING_WINDOW_UNKNOWN",
                    message="Nie udało się dopasować godzin otwarcia do tej wizyty.",
                    stop_id=stop_id,
                )
            ],
        )

    @staticmethod
    def _route_mode(
        mode: TravelMode,
    ) -> Literal["walk", "bus", "bike", "scooter", "taxi", "car"]:
        return {
            TravelMode.WALK: "walk",
            TravelMode.BICYCLE: "bike",
            TravelMode.TRANSIT: "bus",
            TravelMode.DRIVE: "car",
        }[mode]
