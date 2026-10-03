"""
Solver oparty o OR-Tools Routing: orienteering z opcjonalnymi węzłami.

Model:
  - węzły opcjonalne: pominięcie węzła kosztuje jego reward (disjunction penalty),
    więc minimalizacja kosztu == maksymalizacja  sum(reward) - koszty
  - każda trasa (dzień) to osobny "pojazd" z własnymi budżetami
  - wymiary: Time (przejazd + wizyta, okna czasowe, budżet czasu),
             Money (opcjonalnie), Count (opcjonalnie: max węzłów na trasę)
  - brak krawędzi w grafie = przejazd niedozwolony
  - brak start/end -> sztuczny węzeł "dummy" o zerowych kosztach (trasa otwarta)
"""

from __future__ import annotations

import time as _time

from ortools.constraint_solver import pywrapcp, routing_enums_pb2

from app.schemas.planning import (
    CostVector,
    ISolver,
    SolverInput,
    SolverResult,
    SolverRoute,
    SolverStatus,
)

SCALE = 1000  # float -> int (OR-Tools liczy na całkowitych)
DEFAULT_HORIZON_S = 10**6  # gdy brak budżetu czasu
MISSING_ARC_TIME = 10**8  # > horyzont => łuk niedozwolony
TIE_BREAK_DIVISOR = 10  # +1 do kosztu łuku za każde 10 s: skraca zbędne zygzaki


class OrToolsSolver(ISolver):
    def __init__(self, time_limit_s: int = 5) -> None:
        self._time_limit_s = time_limit_s

    def solve(self, solver_input: SolverInput) -> SolverResult:
        started = _time.perf_counter()
        si = solver_input
        n = len(si.nodes)
        if n == 0:
            return SolverResult(status=SolverStatus.OPTIMAL, objective_value=0.0)

        # --- depot: realny albo sztuczny (dummy) -----------------------------
        dummy = n if (si.start_index is None or si.end_index is None) else None
        total = n + (1 if dummy is not None else 0)
        start = si.start_index if si.start_index is not None else dummy
        end = si.end_index if si.end_index is not None else dummy
        anchors = {start, end}
        V = si.num_routes

        manager = pywrapcp.RoutingIndexManager(total, V, [start] * V, [end] * V)
        routing = pywrapcp.RoutingModel(manager)

        # --- macierze (koszt wyjścia z i do j; wizyta w i doliczana przy wyjściu) ---
        edges = {(e.source, e.target): e.cost for e in si.edges}
        w = si.weights
        time_m = [[0] * total for _ in range(total)]
        money_m = [[0] * total for _ in range(total)]
        cost_m = [[0] * total for _ in range(total)]
        for i in range(total):
            for j in range(total):
                if i == j or i == dummy:
                    continue  # zero: pusta trasa / dojście do dummy
                if j == dummy:
                    # Przy trasie otwartej nie ma realnego węzła końcowego,
                    # więc ostatnia wizyta musi zostać doliczona na łuku do
                    # sztucznego węzła. Bez tego ograniczenia budżetowego
                    # pomijały koszt ostatniego POI.
                    visit = si.nodes[i].visit_cost
                    time_m[i][j] = visit.time_s
                    money_m[i][j] = visit.money_minor
                    cost_m[i][j] = round(
                        (
                            w.time_weight * visit.time_s
                            + w.money_weight * visit.money_minor
                        )
                        * SCALE
                    )
                    continue
                if (i, j) == (start, end):
                    continue  # bezpośredni start->end = pusta trasa
                edge = edges.get((i, j))
                if edge is None:
                    time_m[i][j] = MISSING_ARC_TIME
                    continue
                visit = si.nodes[i].visit_cost
                t = edge.time_s + visit.time_s
                m = edge.money_minor + visit.money_minor
                time_m[i][j], money_m[i][j] = t, m
                cost_m[i][j] = (
                    round((w.time_weight * t + w.money_weight * m) * SCALE)
                    + t // TIE_BREAK_DIVISOR
                )

        def register(matrix: list[list[int]]) -> int:
            return routing.RegisterTransitCallback(
                lambda a, b: matrix[manager.IndexToNode(a)][manager.IndexToNode(b)]
            )

        routing.SetArcCostEvaluatorOfAllVehicles(register(cost_m))

        # --- wymiary ----------------------------------------------------------
        horizon = si.budget_per_route.time_s or DEFAULT_HORIZON_S
        routing.AddDimension(register(time_m), horizon, horizon, False, "Time")
        time_dim = routing.GetDimensionOrDie("Time")

        if si.budget_per_route.money_minor is not None:
            routing.AddDimension(
                register(money_m), 0, si.budget_per_route.money_minor, True, "Money"
            )

        if si.max_nodes_per_route is not None:

            def count(index: int) -> int:
                node = manager.IndexToNode(index)
                return 0 if node in anchors or node == dummy else 1

            routing.AddDimension(
                routing.RegisterUnaryTransitCallback(count),
                0,
                si.max_nodes_per_route,
                True,
                "Count",
            )

        # --- węzły: okna czasowe i opcjonalność -------------------------------
        for node in si.nodes:
            if node.index in anchors:
                continue
            idx = manager.NodeToIndex(node.index)

            if node.time_windows:
                windows = sorted(node.time_windows)
                lo, hi = windows[0][0], min(windows[-1][1], horizon)
                if lo > hi:  # okno poza budżetem czasu
                    if node.mandatory:
                        return SolverResult(status=SolverStatus.INFEASIBLE)
                    routing.ActiveVar(idx).SetValue(0)
                    continue
                var = time_dim.CumulVar(idx)
                var.SetRange(lo, hi)
                for (_, prev_hi), (next_lo, _) in zip(windows, windows[1:]):
                    if next_lo > prev_hi + 1:
                        var.RemoveInterval(prev_hi + 1, next_lo - 1)

            if not node.mandatory:
                routing.AddDisjunction([idx], round(node.reward * SCALE))

        # --- rozwiązanie ------------------------------------------------------
        params = pywrapcp.DefaultRoutingSearchParameters()
        params.first_solution_strategy = (
            routing_enums_pb2.FirstSolutionStrategy.PATH_CHEAPEST_ARC
        )
        params.local_search_metaheuristic = (
            routing_enums_pb2.LocalSearchMetaheuristic.GUIDED_LOCAL_SEARCH
        )
        params.time_limit.FromSeconds(self._time_limit_s)

        solution = routing.SolveWithParameters(params)
        elapsed = _time.perf_counter() - started
        if solution is None:
            return SolverResult(
                status=self._failure_status(routing), solve_time_s=elapsed
            )

        routes = self._extract_routes(routing, manager, solution, si, start, end, dummy)
        total_cost = sum((r.cost for r in routes), CostVector())
        objective = (
            sum(r.reward for r in routes)
            - w.time_weight * total_cost.time_s
            - w.money_weight * total_cost.money_minor
        )
        optimal = getattr(routing, "ROUTING_OPTIMAL", None)
        status = (
            SolverStatus.OPTIMAL
            if optimal is not None and routing.status() == optimal
            else SolverStatus.FEASIBLE
        )
        return SolverResult(
            status=status,
            objective_value=objective,
            routes=routes,
            solve_time_s=elapsed,
        )

    @staticmethod
    def _failure_status(routing: pywrapcp.RoutingModel) -> SolverStatus:
        status = routing.status()
        if status == routing.ROUTING_FAIL_TIMEOUT:
            return SolverStatus.TIMEOUT
        if status == routing.ROUTING_INVALID:
            return SolverStatus.ERROR
        return SolverStatus.INFEASIBLE

    @staticmethod
    def _extract_routes(
        routing,
        manager,
        solution,
        si: SolverInput,
        start: int,
        end: int,
        dummy: int | None,
    ) -> list[SolverRoute]:
        edges = {(e.source, e.target): e.cost for e in si.edges}
        routes: list[SolverRoute] = []
        for v in range(si.num_routes):
            index = routing.Start(v)
            path: list[int] = []
            while True:
                path.append(manager.IndexToNode(index))
                if routing.IsEnd(index):
                    break
                index = solution.Value(routing.NextVar(index))

            if len(path) <= 2:  # tylko start->end: trasa nieużywana
                continue
            path = [x for x in path if x != dummy]

            cost = CostVector()
            for a, b in zip(path, path[1:]):
                cost = cost + edges[(a, b)]
            reward = 0.0
            for node_index in path:
                node = si.nodes[node_index]
                cost = cost + node.visit_cost
                reward += node.reward
            routes.append(SolverRoute(node_path=path, reward=reward, cost=cost))
        return routes
