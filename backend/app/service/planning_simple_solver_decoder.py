"""SolverResult (indeksy węzłów) -> Plan (POI, godziny przyjazdu/wyjazdu, koszty)."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Sequence

from schemas.planning import (
    CostVector,
    ISolverDecoder,
    POI,
    POIConnection,
    Plan,
    PlanDay,
    PlanStop,
    PlanningConstraints,
    SolverInput,
    SolverNode,
    SolverResult,
    SolverStatus,
)


class SimpleSolverDecoder(ISolverDecoder):
    def decode(
        self,
        result: SolverResult,
        solver_input: SolverInput,
        pois: Sequence[POI],
        connections: Sequence[POIConnection],
        constraints: PlanningConstraints,
    ) -> Plan:
        poi_by_id = {p.id: p for p in pois}
        conn_by_pair = {
            (c.from_poi_id, c.to_poi_id): c
            for c in connections
            if c.mode == constraints.travel_mode
        }
        edge_cost = {(e.source, e.target): e.cost for e in solver_input.edges}
        base_date = constraints.plan_date.date() if constraints.plan_date else date.today()

        days: list[PlanDay] = []
        visited: set[str] = set()
        if result.status not in (SolverStatus.INFEASIBLE, SolverStatus.ERROR):
            for day_index, route in enumerate(result.routes):
                day_start = datetime.combine(
                    base_date + timedelta(days=day_index), constraints.day_start
                )
                day = self._decode_route(
                    day_index, route.node_path, day_start,
                    solver_input.nodes, poi_by_id, conn_by_pair, edge_cost,
                )
                days.append(day)
                visited.update(stop.poi.id for stop in day.stops)

        return Plan(
            status=result.status,
            objective_value=result.objective_value,
            total_reward=sum(d.total_reward for d in days),
            total_cost=sum((d.total_cost for d in days), CostVector()),
            days=days,
            skipped_poi_ids=[p.id for p in pois if p.id not in visited],
        )

    @staticmethod
    def _decode_route(
        day_index: int,
        node_path: list[int],
        day_start: datetime,
        nodes: list[SolverNode],
        poi_by_id: dict[str, POI],
        conn_by_pair: dict[tuple[str, str], POIConnection],
        edge_cost: dict[tuple[int, int], CostVector],
    ) -> PlanDay:
        """Symulacja najwcześniejszego harmonogramu (z czekaniem na otwarcie)."""
        t = 0            # sekundy od day_start
        money = 0
        reward = 0.0
        stops: list[PlanStop] = []
        prev: int | None = None

        for order, idx in enumerate(node_path):
            node = nodes[idx]
            connection = None
            if prev is not None:
                edge = edge_cost[(prev, idx)]
                t += edge.time_s
                money += edge.money_minor
                connection = conn_by_pair.get((nodes[prev].poi_id, node.poi_id))
                t = SimpleSolverDecoder._wait_for_window(t, node.time_windows)

            arrival = t
            t += node.visit_cost.time_s
            money += node.visit_cost.money_minor
            reward += node.reward
            stops.append(
                PlanStop(
                    order=order,
                    poi=poi_by_id[node.poi_id],
                    arrival=day_start + timedelta(seconds=arrival),
                    departure=day_start + timedelta(seconds=t),
                    reward=node.reward,
                    connection_from_previous=connection,
                )
            )
            prev = idx

        return PlanDay(
            day_index=day_index,
            stops=stops,
            total_reward=reward,
            total_cost=CostVector(time_s=t, money_minor=money),
        )

    @staticmethod
    def _wait_for_window(t: int, windows: list[tuple[int, int]]) -> int:
        for lo, hi in sorted(windows):
            if t <= hi:
                return max(t, lo)
        return t