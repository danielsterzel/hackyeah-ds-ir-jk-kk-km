"""POI -> węzły (reward, visit_cost), POIConnection -> krawędzie (CostVector)."""
from __future__ import annotations

import math
from datetime import time
from typing import Callable, Sequence

from schemas.planning import (
    CostVector,
    ISolverEncoder,
    POI,
    POIConnection,
    PlanningConstraints,
    SolverEdge,
    SolverInput,
    SolverNode,
)

RewardFn = Callable[[POI], float]


def default_reward(poi: POI) -> float:
    """
    Nagroda z ocen: rating * (1 + log10(1 + liczba opinii)).
    Brak oceny = neutralne 3.0. Popularność wzmacnia ocenę, ale logarytmicznie.
    Przykłady: 3.0 / 2 opinie -> ~4.4;  4.5 / 10 000 opinii -> ~22.5.
    """
    rating = poi.rating if poi.rating is not None else 3.0
    reviews = poi.user_ratings_total or 0
    return rating * (1 + math.log10(1 + reviews))


def _seconds(t: time) -> int:
    return t.hour * 3600 + t.minute * 60 + t.second


class SimpleSolverEncoder(ISolverEncoder):
    def __init__(self, reward_fn: RewardFn | None = None) -> None:
        self._reward_fn = reward_fn or default_reward

    def encode(
        self,
        pois: Sequence[POI],
        connections: Sequence[POIConnection],
        constraints: PlanningConstraints,
    ) -> SolverInput:
        known_ids = {p.id for p in pois}
        anchors = {i for i in (constraints.start_poi_id, constraints.end_poi_id) if i}
        must_visit = set(constraints.must_visit_ids)
        unknown = (anchors | must_visit) - known_ids
        if unknown:
            raise ValueError(f"Nieznane POI w ograniczeniach: {sorted(unknown)}")

        nodes: list[SolverNode] = []
        index_of: dict[str, int] = {}
        for poi in pois:
            if poi.id in index_of:
                continue
            is_anchor = poi.id in anchors
            mandatory = poi.id in must_visit

            windows: list[tuple[int, int]] = []
            if not is_anchor:
                found = self._time_windows(poi, constraints)
                if found is None:  # na pewno zamknięte w dniu planu
                    if mandatory:
                        raise ValueError(f"POI obowiązkowe jest zamknięte: {poi.id}")
                    continue
                windows = found

            index_of[poi.id] = len(nodes)
            nodes.append(
                SolverNode(
                    index=len(nodes),
                    poi_id=poi.id,
                    # punkty startu/końca to kotwice trasy: bez nagrody i bez kosztu wizyty
                    reward=0.0 if is_anchor else self._resolve_reward(poi),
                    visit_cost=CostVector() if is_anchor else poi.visit_cost,
                    mandatory=mandatory,
                    time_windows=windows,
                )
            )

        edges: dict[tuple[int, int], SolverEdge] = {}
        for c in connections:
            if c.mode != constraints.travel_mode:
                continue
            a, b = index_of.get(c.from_poi_id), index_of.get(c.to_poi_id)
            if a is None or b is None or a == b or (a, b) in edges:
                continue
            edges[(a, b)] = SolverEdge(
                source=a,
                target=b,
                cost=CostVector(
                    time_s=round(c.duration.total_seconds()),
                    money_minor=round(c.fuel_cost * 100),
                ),
            )

        return SolverInput(
            nodes=nodes,
            edges=list(edges.values()),
            num_routes=constraints.days,
            start_index=index_of.get(constraints.start_poi_id) if constraints.start_poi_id else None,
            end_index=index_of.get(constraints.end_poi_id) if constraints.end_poi_id else None,
            budget_per_route=constraints.budget_per_route,
            weights=constraints.weights,
            max_nodes_per_route=constraints.max_pois,  # limit na KAŻDĄ trasę
        )

    def _resolve_reward(self, poi: POI) -> float:
        return poi.reward if poi.reward is not None else self._reward_fn(poi)

    @staticmethod
    def _time_windows(
        poi: POI, constraints: PlanningConstraints
    ) -> list[tuple[int, int]] | None:
        """
        Okna czasowe w sekundach od początku trasy (day_start).
        []   -> brak ograniczeń (brak danych o godzinach albo planowanie bez daty)
        None -> zamknięte w tym dniu
        Okno kończy się o (zamknięcie - czas wizyty): wizyta ma się zmieścić przed zamknięciem.
        Uwaga: okna uwzględniane tylko dla planu jednodniowego z ustawionym plan_date.
        """
        if constraints.plan_date is None or constraints.days != 1 or not poi.opening_hours:
            return []
        weekday = constraints.plan_date.weekday()
        day_start = _seconds(constraints.day_start)
        service = poi.visit_cost.time_s

        windows = []
        for period in sorted(
            (p for p in poi.opening_hours if p.day_of_week == weekday),
            key=lambda p: p.open,
        ):
            lo = max(0, _seconds(period.open) - day_start)
            hi = _seconds(period.close) - day_start - service
            if hi >= lo:
                windows.append((lo, hi))
        return windows or None