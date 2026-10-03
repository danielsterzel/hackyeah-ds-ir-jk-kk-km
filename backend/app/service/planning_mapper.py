"""Plan -> PlotterPayload (punkty, odcinki i obszar mapy dla plotera)."""

from __future__ import annotations

from app.schemas.planning import (
    Coordinates,
    IPlanningMapper,
    Plan,
    PlotPoint,
    PlotSegment,
    PlotterPayload,
    TravelMode,
)


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
