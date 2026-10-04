"""
Testy kontraktowe pipeline'u: POIService -> ConnectionService -> Encoder
-> Solver -> Decoder -> Mapper.

Wymagania: pytest, pytest-asyncio  (pip install pytest pytest-asyncio)
W pytest.ini / pyproject:  asyncio_mode = auto   (albo zostaw znaczniki poniżej)

JAK UŻYĆ
1. Uzupełnij sekcję ADAPTER (importy modeli, fabryki, akcesory, fixture'y).
2. Dopóki fixture zwraca _wire(...), testy się skipują.
3. Testy NIE zakładają konkretnego algorytmu solvera, tylko niezmienniki:
   wykonalność, brak duplikatów, spójność id, determinizm, optimum na małych
   przykładach policzonych ręcznie.
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

sys.path.insert(0, str(Path(__file__).parents[2]))

# =========================================================================== #
# ADAPTER  -- modele i implementacje domenowe używane przez testy
# =========================================================================== #

from app.api.planning_controller import create_plans
from app.service.planning_json_poi_service import JsonPOIService
from app.service.planning_mapper import SimplePlanningMapper
from app.service.planning_or_solver import OrToolsSolver
from app.service.planning_poi_filter_service import PreferencePOIFilterService
from app.service.planning_service import PlanningService
from app.service.planning_simple_connection_service import SimpleConnectionService
from app.service.planning_simple_solver_decoder import SimpleSolverDecoder
from app.service.planning_simple_solver_encoder import SimpleSolverEncoder
from app.schemas.planning import (
    Coordinates,
    CostWeights,
    CostVector,
    OptionalCostVector,
    Plan,
    PlanningConstraints,
    PlanningRequest,
    PlotterPayload,
    POI,
    POIConnection,
    SolverEdge,
    SolverInput,
    SolverNode,
    SolverResult,
    TravelMode,
)
from app.schemas.llm import LLMOutput

# ---- fixture'y implementacji ---------------------------------------------- #
# Serwisy zewnętrzne (POI, połączenia) podawaj z podmienionym HTTP/fake'iem,
# żeby testy nie szły do sieci.


@pytest.fixture
def poi_service():
    return JsonPOIService(
        Path(__file__).parents[2]
        / "resources"
        / "dataset_crawler-google-places_2026-10-03_15-34-29-547.json"
    )


@pytest.fixture
def connection_service():
    return SimpleConnectionService()


@pytest.fixture
def encoder():
    return SimpleSolverEncoder()


@pytest.fixture
def solver():
    return OrToolsSolver(time_limit_s=5)


@pytest.fixture
def decoder():
    return SimpleSolverDecoder()


@pytest.fixture
def mapper():
    return SimplePlanningMapper()


# ---- fabryki modeli -------------------------------------------------------- #

KRAKOW = (50.0617, 19.9373)  # Rynek Główny (lat, lon)
DAY = datetime(2026, 10, 3)  # sobota


def make_coords(lat: float, lon: float) -> Coordinates:
    return Coordinates(lat=lat, lng=lon)


def make_poi(
    id: str,
    lat: float,
    lon: float,
    category: str = "museum",
    price: float = 0.0,
    visit_min: int = 60,
    reward: float = 1.0,
) -> POI:
    return POI(
        id=id,
        name=id,
        location=make_coords(lat, lon),
        types=[category],
        reward=reward,
        visit_cost=CostVector(
            time_s=visit_min * 60,
            money_minor=round(price * 100),
        ),
    )


def make_connection(
    a_id: str, b_id: str, mode, minutes: float, cost: float = 0.0, meters: float = 0.0
) -> POIConnection:
    return POIConnection(
        from_poi_id=a_id,
        to_poi_id=b_id,
        mode=mode,
        duration=timedelta(minutes=minutes),
        fuel_cost=cost,
        distance_m=round(meters),
    )


def walking():
    return TravelMode.WALK


def transit():
    return TravelMode.TRANSIT


def make_constraints(
    budget: float = 150.0,
    start=KRAKOW,
    start_at=DAY.replace(hour=10),
    end_at=DAY.replace(hour=17),
    **extra,
) -> PlanningConstraints:
    return PlanningConstraints(
        start_poi_id=extra.get("start_poi_id"),
        end_poi_id=extra.get("end_poi_id"),
        days=extra.get("days", 1),
        travel_mode=extra.get("travel_mode", walking()),
        budget_per_route=OptionalCostVector(
            time_s=max(1, round(budget * 100)),
            money_minor=round(budget * 100),
        ),
        weights=CostWeights(),
        max_pois=extra.get("max_pois"),
        must_visit_ids=extra.get("must_visit_ids", []),
        day_start=start_at.time(),
        plan_date=start_at,
    )


def make_solver_input(
    rewards: dict, visit_costs: dict, edges: dict, budget: float, start: str
) -> SolverInput:
    """Ręcznie zbuduj SolverInput.
    rewards: {node: reward}, visit_costs: {node: koszt wizyty},
    edges: {(a, b): koszt przejścia}, start: id węzła startowego."""
    node_ids = list(rewards)
    index_of = {node_id: index for index, node_id in enumerate(node_ids)}
    nodes = [
        SolverNode(
            index=index_of[node_id],
            poi_id=node_id,
            reward=float(rewards[node_id]),
            visit_cost=CostVector(time_s=round(visit_costs[node_id] * 100)),
        )
        for node_id in node_ids
    ]
    solver_edges = [
        SolverEdge(
            source=index_of[a],
            target=index_of[b],
            cost=CostVector(time_s=round(cost * 100)),
        )
        for (a, b), cost in edges.items()
    ]
    return SolverInput(
        nodes=nodes,
        edges=solver_edges,
        num_routes=1,
        start_index=index_of[start],
        budget_per_route=OptionalCostVector(
            time_s=max(1, round(budget * 100)),
        ),
        weights=CostWeights(),
    )


# ---- akcesory (jak czytać pola z modeli) ---------------------------------- #


def poi_id(p) -> str:
    return p.id


def poi_latlon(p) -> tuple[float, float]:
    return p.location.lat, p.location.lng


def conn_ends(c) -> tuple[str, str]:
    return c.from_poi_id, c.to_poi_id


def conn_metrics(c) -> tuple[float, float, float]:
    """(minuty, koszt_pln, metry)"""
    return c.duration.total_seconds() / 60, c.fuel_cost, c.distance_m


def conn_mode(c):
    return c.mode


def si_nodes(si) -> list:
    return si.nodes


def si_node_id(n) -> str:
    return n.poi_id


def si_node_reward(n) -> float:
    return n.reward


def si_node_visit_cost(n) -> float:
    return n.visit_cost.time_s / 100


def si_edges(si) -> list:
    return si.edges


def si_edge_ends(si, e) -> tuple[str, str]:
    return si.nodes[e.source].poi_id, si.nodes[e.target].poi_id


def si_edge_cost(e) -> float:
    """Skalar kosztu (np. budżet) lub pierwsza składowa CostVector."""
    return e.cost.time_s / 100


def result_route(r: SolverResult, si: SolverInput) -> list[str]:
    """Uporządkowane id węzłów w rozwiązaniu (z startem, jeśli go zawiera)."""
    if not r.routes:
        return []
    return [si.nodes[index].poi_id for index in r.routes[0].node_path]


def result_total_reward(r: SolverResult) -> float:
    return sum(route.reward for route in r.routes)


def plan_stops(plan: Plan) -> list[tuple[str, datetime, datetime]]:
    """[(poi_id, przyjście, wyjście)] w kolejności odwiedzin."""
    return [
        (stop.poi.id, stop.arrival, stop.departure)
        for day in plan.days
        for stop in day.stops
    ]


def plan_total_cost(plan: Plan) -> float:
    return plan.total_cost.money_minor / 100


def payload_markers(payload: PlotterPayload) -> list[str]:
    """Id/nazwy markerów w kolejności."""
    return [point.poi_id for point in payload.points]


def payload_path(payload: PlotterPayload) -> list[tuple[float, float]]:
    """Punkty linii trasy (lat, lon) w kolejności."""
    return [(point.location.lat, point.location.lng) for point in payload.points]


def payload_to_json(payload: PlotterPayload) -> str:
    """Serializacja tak, jak robi to API (np. model_dump_json / json.dumps)."""
    return payload.model_dump_json()


# =========================================================================== #
# Helpery testowe
# =========================================================================== #


def haversine_m(a, b) -> float:
    r = 6_371_000
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = (
        math.sin((la2 - la1) / 2) ** 2
        + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2
    )
    return 2 * r * math.asin(math.sqrt(h))


def sample_pois():
    """5 POI w centrum Krakowa, w tym jedna restauracja."""
    return [
        make_poi("rynek", 50.0617, 19.9373, "historic", 0, 30, 3),
        make_poi("sukiennice", 50.0614, 19.9372, "museum", 25, 90, 4),
        make_poi("wawel", 50.0540, 19.9352, "historic", 20, 120, 5),
        make_poi("planty", 50.0640, 19.9400, "park", 0, 30, 2),
        make_poi("bar", 50.0580, 19.9440, "food", 35, 45, 2),
    ]


def full_connections(pois, mode=None):
    """Pełny graf skierowany z prostym modelem odległości (do testów enkodera)."""
    mode = mode or walking()
    out = []
    for a in pois:
        for b in pois:
            if poi_id(a) == poi_id(b):
                continue
            d = haversine_m(poi_latlon(a), poi_latlon(b))
            out.append(
                make_connection(
                    poi_id(a), poi_id(b), mode, minutes=d / 80, cost=0.0, meters=d
                )
            )
    return out


# =========================================================================== #
# 1. IPOIService
# =========================================================================== #


@pytest.mark.asyncio
async def test_poi_service_returns_list_of_pois(poi_service):
    pois = await poi_service.get_pois("museum", make_coords(*KRAKOW), 3000)
    assert isinstance(pois, list)
    assert len(pois) > 0


@pytest.mark.asyncio
async def test_poi_service_respects_radius(poi_service):
    radius = 2000
    pois = await poi_service.get_pois("museum", make_coords(*KRAKOW), radius)
    for p in pois:
        # 10% tolerancji na różnice w modelu Ziemi / środek obiektu
        assert haversine_m(KRAKOW, poi_latlon(p)) <= radius * 1.1, poi_id(p)


@pytest.mark.asyncio
async def test_poi_service_ids_are_unique(poi_service):
    pois = await poi_service.get_pois("restaurant", make_coords(*KRAKOW), 3000)
    ids = [poi_id(p) for p in pois]
    assert len(ids) == len(set(ids))


@pytest.mark.asyncio
async def test_poi_service_no_results_returns_empty_list(poi_service):
    pois = await poi_service.get_pois("zzzxxyy-nie-istnieje", make_coords(*KRAKOW), 500)
    assert pois == []


@pytest.mark.asyncio
async def test_poi_service_smaller_radius_is_subset(poi_service):
    c = make_coords(*KRAKOW)
    small = {poi_id(p) for p in await poi_service.get_pois("museum", c, 1000)}
    big = {poi_id(p) for p in await poi_service.get_pois("museum", c, 5000)}
    assert small <= big


def test_preferred_category_is_kept_in_limited_candidate_shortlist():
    nearby_garden = make_poi("garden", 50.0618, 19.9373, category="garden")
    farther_museum = make_poi("museum", 50.0710, 19.9373, category="museum")
    request = PlanningRequest(
        start_at=DAY.replace(hour=10),
        end_at=DAY.replace(hour=17),
        start_location=make_coords(*KRAKOW),
        budget_pln=100,
        preferred_categories=["museum"],
        transport_modes=[TravelMode.WALK],
    )

    result = PreferencePOIFilterService(max_results=1).filter_pois(
        [nearby_garden, farther_museum],
        request,
    )

    assert [poi.id for poi in result] == ["museum"]


def test_park_preference_does_not_match_parking():
    nearby_parking = make_poi("parking", 50.0618, 19.9373, category="Parking")
    farther_park = make_poi("park", 50.0710, 19.9373, category="park")
    request = PlanningRequest(
        start_at=DAY.replace(hour=10),
        end_at=DAY.replace(hour=17),
        start_location=make_coords(*KRAKOW),
        budget_pln=100,
        preferred_categories=["park"],
        transport_modes=[TravelMode.WALK],
    )

    result = PreferencePOIFilterService(max_results=1).filter_pois(
        [nearby_parking, farther_park],
        request,
    )

    assert [poi.id for poi in result] == ["park"]


@pytest.mark.parametrize("preference", ["restauracje", "restaurant", "coś zjeść"])
def test_generic_food_request_prioritizes_restaurant(preference):
    nearby_park = make_poi("park", 50.0618, 19.9373, category="Park")
    farther_restaurant = make_poi(
        "restaurant",
        50.0710,
        19.9373,
        category="Restauracja",
    )
    request = PlanningRequest(
        start_at=DAY.replace(hour=10),
        end_at=DAY.replace(hour=17),
        start_location=make_coords(*KRAKOW),
        budget_pln=100,
        food_preferences=[preference],
        transport_modes=[TravelMode.WALK],
    )

    result = PreferencePOIFilterService(max_results=1).filter_pois(
        [nearby_park, farther_restaurant],
        request,
    )

    assert [poi.id for poi in result] == ["restaurant"]


@pytest.mark.parametrize("preference", ["włoska", "italian", "kuchnia włoska"])
def test_italian_food_request_matches_polish_dataset_category(preference):
    nearby_museum = make_poi("museum", 50.0618, 19.9373, category="Muzeum")
    farther_italian = make_poi(
        "italian",
        50.0710,
        19.9373,
        category="Kuchnia włoska",
    )
    request = PlanningRequest(
        start_at=DAY.replace(hour=10),
        end_at=DAY.replace(hour=17),
        start_location=make_coords(*KRAKOW),
        budget_pln=100,
        food_preferences=[preference],
        transport_modes=[TravelMode.WALK],
    )

    result = PreferencePOIFilterService(max_results=1).filter_pois(
        [nearby_museum, farther_italian],
        request,
    )

    assert [poi.id for poi in result] == ["italian"]


# =========================================================================== #
# 2. IPOIConnectionService
# =========================================================================== #


@pytest.mark.asyncio
async def test_connections_reference_only_given_pois(connection_service):
    pois = sample_pois()
    ids = {poi_id(p) for p in pois}
    conns = await connection_service.get_connections(pois, walking())
    assert conns
    for c in conns:
        a, b = conn_ends(c)
        assert a in ids and b in ids


@pytest.mark.asyncio
async def test_connections_have_no_self_loops(connection_service):
    conns = await connection_service.get_connections(sample_pois(), walking())
    assert all(conn_ends(c)[0] != conn_ends(c)[1] for c in conns)


@pytest.mark.asyncio
async def test_connections_have_no_duplicate_pairs(connection_service):
    conns = await connection_service.get_connections(sample_pois(), walking())
    pairs = [conn_ends(c) for c in conns]
    assert len(pairs) == len(set(pairs))


@pytest.mark.asyncio
async def test_connections_metrics_are_non_negative_and_finite(connection_service):
    conns = await connection_service.get_connections(sample_pois(), walking())
    for c in conns:
        for v in conn_metrics(c):
            assert v >= 0 and math.isfinite(v)


@pytest.mark.asyncio
async def test_connections_walking_is_free(connection_service):
    conns = await connection_service.get_connections(sample_pois(), walking())
    assert all(conn_metrics(c)[1] == 0 for c in conns)


@pytest.mark.asyncio
async def test_connections_mode_is_propagated(connection_service):
    conns = await connection_service.get_connections(sample_pois(), transit())
    assert all(conn_mode(c) == transit() for c in conns)


@pytest.mark.asyncio
async def test_connections_empty_and_single_poi(connection_service):
    assert await connection_service.get_connections([], walking()) == []
    assert await connection_service.get_connections(sample_pois()[:1], walking()) == []


@pytest.mark.asyncio
async def test_connections_farther_means_not_faster(connection_service):
    """Sanity: rynek->sukiennice (blisko) nie może trwać dłużej niż rynek->wawel."""
    conns = await connection_service.get_connections(sample_pois(), walking())
    by_pair = {conn_ends(c): conn_metrics(c)[0] for c in conns}
    assert by_pair[("rynek", "sukiennice")] <= by_pair[("rynek", "wawel")]


# =========================================================================== #
# 3. ISolverEncoder
# =========================================================================== #


def test_encoder_one_node_per_poi(encoder):
    pois = sample_pois()
    si = encoder.encode(pois, full_connections(pois), make_constraints())
    node_ids = {si_node_id(n) for n in si_nodes(si)}
    assert {poi_id(p) for p in pois} <= node_ids


def test_encoder_edges_only_between_known_nodes(encoder):
    pois = sample_pois()
    si = encoder.encode(pois, full_connections(pois), make_constraints())
    node_ids = {si_node_id(n) for n in si_nodes(si)}
    for e in si_edges(si):
        a, b = si_edge_ends(si, e)
        assert a in node_ids and b in node_ids


def test_encoder_does_not_invent_edges(encoder):
    pois = sample_pois()
    conns = [c for c in full_connections(pois) if conn_ends(c) != ("rynek", "wawel")]
    si = encoder.encode(pois, conns, make_constraints())
    assert ("rynek", "wawel") not in {si_edge_ends(si, e) for e in si_edges(si)}


def test_encoder_rewards_and_costs_are_non_negative(encoder):
    pois = sample_pois()
    si = encoder.encode(pois, full_connections(pois), make_constraints())
    for n in si_nodes(si):
        assert si_node_reward(n) >= 0
        assert si_node_visit_cost(n) >= 0
    for e in si_edges(si):
        assert si_edge_cost(e) >= 0


def test_encoder_higher_price_means_higher_visit_cost(encoder):
    pois = sample_pois()  # sukiennice 25 zł > rynek 0 zł
    si = encoder.encode(pois, full_connections(pois), make_constraints())
    cost = {si_node_id(n): si_node_visit_cost(n) for n in si_nodes(si)}
    assert cost["sukiennice"] > cost["rynek"]


def test_encoder_is_deterministic(encoder):
    pois = sample_pois()
    conns = full_connections(pois)
    c = make_constraints()
    a, b = encoder.encode(pois, conns, c), encoder.encode(pois, conns, c)
    assert [si_node_id(n) for n in si_nodes(a)] == [si_node_id(n) for n in si_nodes(b)]
    assert [si_edge_ends(a, e) for e in si_edges(a)] == [
        si_edge_ends(b, e) for e in si_edges(b)
    ]


def test_encoder_empty_input_does_not_crash(encoder):
    si = encoder.encode([], [], make_constraints())
    assert si is not None


# =========================================================================== #
# 4. ISolver  (na ręcznie policzonych instancjach)
# =========================================================================== #


def _feasible(result, solver_input, rewards, visit_costs, edges, budget):
    route = result_route(result, solver_input)
    assert len(route) == len(set(route)), "duplikaty w trasie"
    spent = sum(visit_costs[n] for n in route)
    spent += sum(edges[(a, b)] for a, b in zip(route, route[1:]))
    assert spent <= budget + 1e-9, f"przekroczony budżet: {spent} > {budget}"


def test_solver_picks_optimal_subset_under_budget(solver):
    """Budżet 10. A(r=5,k=7), B(r=4,k=4), C(r=4,k=4), koszt przejść 0.
    Optimum = B+C (reward 8, koszt 8), a nie A+B (koszt 11)."""
    rewards = {"s": 0, "A": 5, "B": 4, "C": 4}
    visit = {"s": 0, "A": 7, "B": 4, "C": 4}
    edges = {(a, b): 0 for a in rewards for b in rewards if a != b}
    si = make_solver_input(rewards, visit, edges, budget=10, start="s")
    res = solver.solve(si)
    _feasible(res, si, rewards, visit, edges, 10)
    assert set(result_route(res, si)) - {"s"} == {"B", "C"}
    assert result_total_reward(res) == pytest.approx(8)


def test_solver_accounts_for_travel_cost(solver):
    """Dojście do X kosztuje 9, a budżet to 10 -> X (r=10, k=2) się nie opłaca
    razem z Y (r=3, k=1, dojście 1)."""
    rewards = {"s": 0, "X": 10, "Y": 3}
    visit = {"s": 0, "X": 2, "Y": 1}
    edges = {("s", "X"): 9, ("s", "Y"): 1, ("X", "Y"): 1, ("X", "s"): 9, ("Y", "s"): 1}
    si = make_solver_input(rewards, visit, edges, budget=10, start="s")
    res = solver.solve(si)
    _feasible(res, si, rewards, visit, edges, 10)
    # X nieosiągalne (9+2=11 > 10); jedyna sensowna trasa to s->Y
    assert result_route(res, si)[-1] == "Y"
    assert "X" not in result_route(res, si)


def test_solver_route_starts_at_start_node(solver):
    rewards = {"s": 0, "A": 2, "B": 2}
    visit = {"s": 0, "A": 1, "B": 1}
    edges = {(a, b): 1 for a in rewards for b in rewards if a != b}
    si = make_solver_input(rewards, visit, edges, budget=10, start="s")
    res = solver.solve(si)
    assert result_route(res, si)[0] == "s"


def test_solver_infeasible_returns_empty_route_not_exception(solver):
    """Każdy węzeł droższy niż budżet -> trasa tylko ze startem (lub pusta)."""
    rewards = {"s": 0, "A": 5}
    visit = {"s": 0, "A": 100}
    edges = {("s", "A"): 1, ("A", "s"): 1}
    si = make_solver_input(rewards, visit, edges, budget=10, start="s")
    res = solver.solve(si)
    assert set(result_route(res, si)) <= {"s"}
    assert result_total_reward(res) == 0


def test_solver_zero_budget(solver):
    rewards = {"s": 0, "A": 5}
    visit = {"s": 0, "A": 0.01}
    edges = {("s", "A"): 0.01, ("A", "s"): 0.01}
    si = make_solver_input(rewards, visit, edges, budget=0, start="s")
    res = solver.solve(si)
    assert set(result_route(res, si)) <= {"s"}


def test_solver_is_deterministic(solver):
    rewards = {"s": 0, **{f"n{i}": 1 + (i % 3) for i in range(8)}}
    visit = {n: 1 for n in rewards}
    edges = {(a, b): 1 for a in rewards for b in rewards if a != b}
    si = make_solver_input(rewards, visit, edges, budget=6, start="s")
    assert result_route(solver.solve(si), si) == result_route(solver.solve(si), si)


def test_solver_more_budget_never_gives_less_reward(solver):
    rewards = {"s": 0, "A": 3, "B": 4, "C": 5, "D": 2}
    visit = {"s": 0, "A": 2, "B": 3, "C": 4, "D": 1}
    edges = {(a, b): 1 for a in rewards for b in rewards if a != b}
    low = solver.solve(make_solver_input(rewards, visit, edges, budget=6, start="s"))
    high = solver.solve(make_solver_input(rewards, visit, edges, budget=20, start="s"))
    assert result_total_reward(high) >= result_total_reward(low)


def test_most_places_strategy_prefers_three_short_visits_over_one_high_reward_visit(
    encoder, solver, decoder
):
    start = make_poi("start", *KRAKOW, visit_min=0, reward=0)
    long_visit = make_poi("long", *KRAKOW, visit_min=90, reward=100)
    short_visits = [
        make_poi(f"short-{index}", *KRAKOW, visit_min=30, reward=1)
        for index in range(3)
    ]
    constraints = PlanningConstraints(
        start_poi_id=start.id,
        days=1,
        travel_mode=TravelMode.WALK,
        budget_per_route=OptionalCostVector(time_s=90 * 60),
        weights=CostWeights(),
        day_start=DAY.replace(hour=10).time(),
        plan_date=DAY.replace(hour=10),
    )

    normal_pois = [start, long_visit, *short_visits]
    connections = full_connections(normal_pois)
    normal_input = encoder.encode(normal_pois, connections, constraints)
    normal_result = solver.solve(normal_input)
    assert result_route(normal_result, normal_input) == ["start", "long"]

    optimized_attractions = PlanningService._apply_strategy_rewards(
        [long_visit, *short_visits],
        "most_places",
        preferred_categories=[],
        food_preferences=[],
    )
    optimized_pois = [start, *optimized_attractions]
    optimized_input = encoder.encode(optimized_pois, connections, constraints)
    optimized_result = solver.solve(optimized_input)
    optimized_plan = decoder.decode(
        optimized_result,
        optimized_input,
        optimized_pois,
        connections,
        constraints,
    )
    optimized_ids = [
        stop.poi.id
        for day in optimized_plan.days
        for stop in day.stops
        if stop.poi.id != start.id
    ]

    assert set(optimized_ids) == {"short-0", "short-1", "short-2"}
    assert len(optimized_ids) == 3


def test_most_places_strategy_keeps_category_preference_as_tie_breaker(
    encoder, solver, decoder
):
    start = make_poi("start", *KRAKOW, visit_min=0, reward=0)
    museums = [
        make_poi(f"museum-{index}", *KRAKOW, category="museum", visit_min=30)
        for index in range(2)
    ]
    gardens = [
        make_poi(f"garden-{index}", *KRAKOW, category="garden", visit_min=30)
        for index in range(2)
    ]
    attractions = PlanningService._apply_strategy_rewards(
        [*museums, *gardens],
        "most_places",
        preferred_categories=["museum"],
        food_preferences=[],
    )
    pois = [start, *attractions]
    connections = full_connections(pois)
    constraints = PlanningConstraints(
        start_poi_id=start.id,
        days=1,
        travel_mode=TravelMode.WALK,
        budget_per_route=OptionalCostVector(time_s=60 * 60),
        weights=CostWeights(),
        day_start=DAY.replace(hour=10).time(),
        plan_date=DAY.replace(hour=10),
    )

    solver_input = encoder.encode(pois, connections, constraints)
    result = solver.solve(solver_input)
    plan = decoder.decode(
        result,
        solver_input,
        pois,
        connections,
        constraints,
    )
    attraction_ids = {
        stop.poi.id
        for day in plan.days
        for stop in day.stops
        if stop.poi.id != start.id
    }

    assert attraction_ids == {"museum-0", "museum-1"}


def test_solver_scales_to_realistic_size(solver):
    """Smoke/perf: 300 węzłów musi się policzyć w rozsądnym czasie."""
    import time

    n = 300
    rewards = {"s": 0, **{f"n{i}": 1 + (i % 5) for i in range(n)}}
    visit = {k: 1 for k in rewards}
    edges = {(a, b): 0.5 for a in rewards for b in rewards if a != b}
    si = make_solver_input(rewards, visit, edges, budget=40, start="s")
    t0 = time.perf_counter()
    res = solver.solve(si)
    assert time.perf_counter() - t0 < 10, "solver za wolny na demo"
    _feasible(res, si, rewards, visit, edges, 40)


# =========================================================================== #
# 5. ISolverDecoder
# =========================================================================== #


def _solve_sample(encoder, solver, constraints=None):
    pois = sample_pois()
    conns = full_connections(pois)
    constraints = constraints or make_constraints()
    si = encoder.encode(pois, conns, constraints)
    return pois, conns, constraints, si, solver.solve(si)


def test_decoder_stops_follow_solver_order(encoder, solver, decoder):
    pois, conns, c, si, res = _solve_sample(encoder, solver)
    plan = decoder.decode(res, si, pois, conns, c)
    expected = [n for n in result_route(res, si) if n in {poi_id(p) for p in pois}]
    assert [s[0] for s in plan_stops(plan)] == expected


def test_decoder_times_are_monotonic(encoder, solver, decoder):
    pois, conns, c, si, res = _solve_sample(encoder, solver)
    stops = plan_stops(decoder.decode(res, si, pois, conns, c))
    for _, arrive, depart in stops:
        assert arrive <= depart
    for (_, _, prev_depart), (_, next_arrive, _) in zip(stops, stops[1:]):
        assert prev_depart <= next_arrive


def test_decoder_plan_fits_time_window(encoder, solver, decoder):
    pois, conns, c, si, res = _solve_sample(encoder, solver)
    stops = plan_stops(decoder.decode(res, si, pois, conns, c))
    if stops:
        assert stops[0][1] >= DAY.replace(hour=10)
        assert stops[-1][2] <= DAY.replace(hour=17)


def test_decoder_total_cost_within_budget(encoder, solver, decoder):
    pois, conns, c, si, res = _solve_sample(
        encoder, solver, make_constraints(budget=150)
    )
    plan = decoder.decode(res, si, pois, conns, c)
    assert plan_total_cost(plan) <= 150


def test_decoder_total_cost_matches_sum_of_parts(encoder, solver, decoder):
    pois, conns, c, si, res = _solve_sample(encoder, solver)
    plan = decoder.decode(res, si, pois, conns, c)
    prices = {poi_id(p): getattr(p, "price", None) for p in pois}
    if all(v is not None for v in prices.values()):  # tylko gdy POI ma pole price
        assert (
            plan_total_cost(plan) >= sum(prices[s[0]] for s in plan_stops(plan)) - 1e-6
        )


def test_decoder_unknown_ids_only_come_from_input(encoder, solver, decoder):
    pois, conns, c, si, res = _solve_sample(encoder, solver)
    ids = {poi_id(p) for p in pois}
    assert {s[0] for s in plan_stops(decoder.decode(res, si, pois, conns, c))} <= ids


def test_decoder_empty_result_gives_empty_plan(encoder, solver, decoder):
    pois = sample_pois()
    conns = full_connections(pois)
    c = make_constraints(budget=0)
    si = encoder.encode(pois, conns, c)
    plan = decoder.decode(solver.solve(si), si, pois, conns, c)
    assert plan_stops(plan) == []
    assert plan_total_cost(plan) == 0


# =========================================================================== #
# 6. IPlanningMapper
# =========================================================================== #


def _plan(encoder, solver, decoder):
    pois, conns, c, si, res = _solve_sample(encoder, solver)
    return decoder.decode(res, si, pois, conns, c)


def test_mapper_one_marker_per_stop_in_order(encoder, solver, decoder, mapper):
    plan = _plan(encoder, solver, decoder)
    payload = mapper.to_plotter(plan)
    assert len(payload_markers(payload)) == len(plan_stops(plan))


def test_mapper_path_has_valid_coordinates(encoder, solver, decoder, mapper):
    payload = mapper.to_plotter(_plan(encoder, solver, decoder))
    for lat, lon in payload_path(payload):
        assert -90 <= lat <= 90 and -180 <= lon <= 180
        assert haversine_m(KRAKOW, (lat, lon)) < 30_000  # w okolicy Krakowa


def test_mapper_payload_is_json_serializable(encoder, solver, decoder, mapper):
    payload = mapper.to_plotter(_plan(encoder, solver, decoder))
    json.loads(payload_to_json(payload))


def test_mapper_empty_plan(encoder, solver, decoder, mapper):
    pois = sample_pois()
    conns = full_connections(pois)
    c = make_constraints(budget=0)
    si = encoder.encode(pois, conns, c)
    plan = decoder.decode(solver.solve(si), si, pois, conns, c)
    payload = mapper.to_plotter(plan)
    assert payload_markers(payload) == []
    json.loads(payload_to_json(payload))


# =========================================================================== #
# 7. End-to-end (z fake'ami zewnętrznych serwisów)
# =========================================================================== #


@pytest.mark.asyncio
async def test_pipeline_end_to_end(
    poi_service, connection_service, encoder, solver, decoder, mapper
):
    c = make_constraints(budget=150)
    pois = await poi_service.get_pois("museum", make_coords(*KRAKOW), 3000)
    assert pois, "poi_service nie zwrócił danych do E2E"
    conns = await connection_service.get_connections(pois, walking())
    si = encoder.encode(pois, conns, c)
    res = solver.solve(si)
    plan = decoder.decode(res, si, pois, conns, c)
    payload = mapper.to_plotter(plan)

    stops = plan_stops(plan)
    assert stops, "pusty plan dla standardowego wejścia"
    assert plan_total_cost(plan) <= 150
    assert stops[0][1] >= DAY.replace(hour=10)
    assert stops[-1][2] <= DAY.replace(hour=17)
    assert len({s[0] for s in stops}) == len(stops), "duplikaty w planie"
    assert len(payload_markers(payload)) == len(stops)
    json.loads(payload_to_json(payload))


@pytest.mark.asyncio
async def test_pipeline_does_not_mutate_inputs(
    poi_service, connection_service, encoder, solver, decoder
):
    pois = sample_pois()
    conns = full_connections(pois)
    before = (repr(pois), repr(conns))
    c = make_constraints()
    si = encoder.encode(pois, conns, c)
    decoder.decode(solver.solve(si), si, pois, conns, c)
    assert (repr(pois), repr(conns)) == before


# =========================================================================== #
# 8. Pipeline przez kontroler z różnymi odpowiedziami LLM
# =========================================================================== #


def llm_output_variants() -> list[LLMOutput]:
    common = {
        "start_at": "2026-10-03T10:00:00+02:00",
        "end_at": "2026-10-03T17:00:00+02:00",
        "start_location": {
            "latitude": KRAKOW[0],
            "longitude": KRAKOW[1],
        },
        "end_location": None,
        "food_preferences": [],
        "avoid_crowds": False,
        "weather_sensitive": False,
    }
    return [
        LLMOutput(
            **common,
            preferred_categories=["museum", "historic"],
            transport_modes=["walking"],
            optimization_strategy="cheapest",
            excluded_categories=["shopping", "nightlife"],
        ),
        LLMOutput(
            **common,
            preferred_categories=["museum"],
            transport_modes=["public_transport", "walking"],
            optimization_strategy="fastest",
            excluded_categories=[],
        ),
        LLMOutput(
            **common,
            preferred_categories=["museum", "park", "historic"],
            transport_modes=["walking", "public_transport"],
            optimization_strategy="most_places",
            excluded_categories=["shopping"],
        ),
        LLMOutput(
            **{**common, "avoid_crowds": True},
            preferred_categories=["park", "nature"],
            transport_modes=["walking"],
            optimization_strategy="least_crowded",
            excluded_categories=["nightlife", "entertainment"],
        ),
        LLMOutput(
            **common,
            preferred_categories=["park", "historic"],
            transport_modes=["bicycle", "walking"],
            optimization_strategy="fastest",
            excluded_categories=[],
        ),
    ]


def test_interview_primary_bicycle_mode_is_selected_over_walking_fallback():
    service = PlanningService()
    request = service._to_planning_request(llm_output_variants()[4])

    assert request.transport_modes == [TravelMode.BICYCLE, TravelMode.WALK]
    assert request.prefer_walking is False
    assert service._select_travel_mode(request) == TravelMode.BICYCLE


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    llm_output_variants(),
    ids=["cheapest", "fastest", "most-places", "least-crowded", "bicycle"],
)
async def test_controller_runs_pipeline_for_llm_output(payload):
    plans = await create_plans(payload)

    assert 1 <= len(plans) <= 3
    route_fingerprints = [
        tuple(tuple(stop.poi.id for stop in day.stops) for day in plan.days)
        for plan in plans
    ]
    assert len(set(route_fingerprints)) == len(plans)
    for plan in plans:
        assert plan.status in {"optimal", "feasible"}
        assert plan.total_reward >= 0
        assert plan.total_cost.time_s >= 0
        assert plan.days
        stops = [stop for day in plan.days for stop in day.stops]
        assert len({stop.poi.id for stop in stops}) == len(stops)
        assert all(stop.arrival <= stop.departure for stop in stops)


@pytest.mark.asyncio
async def test_controller_applies_llm_excluded_categories():
    payload = llm_output_variants()[2].model_copy(
        update={"excluded_categories": ["park", "shopping", "nightlife"]}
    )

    plans = await create_plans(payload)
    for plan in plans:
        for day in plan.days:
            for stop in day.stops:
                searchable = " ".join([stop.poi.name, *stop.poi.types]).casefold()
                assert "park" not in searchable


@pytest.mark.asyncio
async def test_planning_result_contains_single_map_ready_route():
    service = PlanningService(candidate_limits=(30,))
    user_id = uuid4()

    await service.create_plans_for_user(user_id, llm_output_variants()[0])
    result = service.get_result(user_id)

    assert result is not None
    assert result.status == "ready"
    assert result.plan is not None
    assert result.plan.strategy == "cheapest"
    assert result.plan.stops
    assert result.plan.stops[0].kind == "start"
    assert result.plan.stops[0].place.name == "Twoja lokalizacja"
    assert result.plan.stops[0].arrival_at == llm_output_variants()[0].start_at
    assert [stop.order for stop in result.plan.stops] == list(
        range(1, len(result.plan.stops) + 1)
    )
    assert len(result.plan.legs) == max(0, len(result.plan.stops) - 1)
    assert all(len(leg.coords) >= 2 for leg in result.plan.legs)
    assert result.plan.legs[0].from_stop_id == result.plan.stops[0].id
    assert result.plan.summary.attractions_count == len(result.plan.stops) - 1
    json.loads(result.model_dump_json())
