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
from datetime import datetime, timedelta

import pytest

# =========================================================================== #
# ADAPTER  -- jedyne miejsce, które trzeba dopasować do Waszych modeli
# =========================================================================== #

# TODO: zamień na prawdziwe importy, np.
# from app.domain.models import POI, Coordinates, POIConnection, TravelMode, \
#     PlanningConstraints, SolverInput, SolverResult, Plan, PlotterPayload
# from app.services import ...


def _wire(name: str):
    pytest.skip(f"Podepnij implementację: {name} (sekcja ADAPTER)")


# ---- fixture'y implementacji ---------------------------------------------- #
# Serwisy zewnętrzne (POI, połączenia) podawaj z podmienionym HTTP/fake'iem,
# żeby testy nie szły do sieci.

@pytest.fixture
def poi_service():          # IPOIService
    return _wire("IPOIService")


@pytest.fixture
def connection_service():   # IPOIConnectionService
    return _wire("IPOIConnectionService")


@pytest.fixture
def encoder():              # ISolverEncoder
    return _wire("ISolverEncoder")


@pytest.fixture
def solver():               # ISolver
    return _wire("ISolver")


@pytest.fixture
def decoder():              # ISolverDecoder
    return _wire("ISolverDecoder")


@pytest.fixture
def mapper():               # IPlanningMapper
    return _wire("IPlanningMapper")


# ---- fabryki modeli -------------------------------------------------------- #

KRAKOW = (50.0617, 19.9373)  # Rynek Główny (lat, lon)
DAY = datetime(2026, 10, 3)  # sobota


def make_coords(lat: float, lon: float):
    raise NotImplementedError


def make_poi(id: str, lat: float, lon: float, category: str = "museum",
             price: float = 0.0, visit_min: int = 60, reward: float = 1.0):
    raise NotImplementedError


def make_connection(a_id: str, b_id: str, mode, minutes: float,
                    cost: float = 0.0, meters: float = 0.0):
    raise NotImplementedError


def walking():
    """Zwróć TravelMode.WALKING."""
    raise NotImplementedError


def transit():
    """Zwróć TravelMode.PUBLIC_TRANSPORT."""
    raise NotImplementedError


def make_constraints(budget: float = 150.0, start=KRAKOW,
                     start_at=DAY.replace(hour=10), end_at=DAY.replace(hour=17),
                     **extra):
    raise NotImplementedError


def make_solver_input(rewards: dict, visit_costs: dict, edges: dict,
                      budget: float, start: str):
    """Ręcznie zbuduj SolverInput.
    rewards: {node: reward}, visit_costs: {node: koszt wizyty},
    edges: {(a, b): koszt przejścia}, start: id węzła startowego."""
    raise NotImplementedError


# ---- akcesory (jak czytać pola z modeli) ---------------------------------- #

def poi_id(p) -> str: raise NotImplementedError
def poi_latlon(p) -> tuple[float, float]: raise NotImplementedError

def conn_ends(c) -> tuple[str, str]: raise NotImplementedError
def conn_metrics(c) -> tuple[float, float, float]:
    """(minuty, koszt_pln, metry)"""
    raise NotImplementedError
def conn_mode(c): raise NotImplementedError

def si_nodes(si) -> list: raise NotImplementedError          # lista węzłów
def si_node_id(n) -> str: raise NotImplementedError
def si_node_reward(n) -> float: raise NotImplementedError
def si_node_visit_cost(n) -> float: raise NotImplementedError
def si_edges(si) -> list: raise NotImplementedError          # lista krawędzi
def si_edge_ends(e) -> tuple[str, str]: raise NotImplementedError
def si_edge_cost(e) -> float:
    """Skalar kosztu (np. budżet) lub pierwsza składowa CostVector."""
    raise NotImplementedError

def result_route(r) -> list[str]:
    """Uporządkowane id węzłów w rozwiązaniu (z startem, jeśli go zawiera)."""
    raise NotImplementedError
def result_total_reward(r) -> float: raise NotImplementedError

def plan_stops(plan) -> list[tuple[str, datetime, datetime]]:
    """[(poi_id, przyjście, wyjście)] w kolejności odwiedzin."""
    raise NotImplementedError
def plan_total_cost(plan) -> float: raise NotImplementedError

def payload_markers(payload) -> list[str]:
    """Id/nazwy markerów w kolejności."""
    raise NotImplementedError
def payload_path(payload) -> list[tuple[float, float]]:
    """Punkty linii trasy (lat, lon) w kolejności."""
    raise NotImplementedError
def payload_to_json(payload) -> str:
    """Serializacja tak, jak robi to API (np. model_dump_json / json.dumps)."""
    raise NotImplementedError


# =========================================================================== #
# Helpery testowe
# =========================================================================== #

def haversine_m(a, b) -> float:
    r = 6_371_000
    la1, lo1, la2, lo2 = map(math.radians, (*a, *b))
    h = (math.sin((la2 - la1) / 2) ** 2
         + math.cos(la1) * math.cos(la2) * math.sin((lo2 - lo1) / 2) ** 2)
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
            out.append(make_connection(poi_id(a), poi_id(b), mode,
                                       minutes=d / 80, cost=0.0, meters=d))
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
        a, b = si_edge_ends(e)
        assert a in node_ids and b in node_ids


def test_encoder_does_not_invent_edges(encoder):
    pois = sample_pois()
    conns = [c for c in full_connections(pois) if conn_ends(c) != ("rynek", "wawel")]
    si = encoder.encode(pois, conns, make_constraints())
    assert ("rynek", "wawel") not in {si_edge_ends(e) for e in si_edges(si)}


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
    assert [si_edge_ends(e) for e in si_edges(a)] == [si_edge_ends(e) for e in si_edges(b)]


def test_encoder_empty_input_does_not_crash(encoder):
    si = encoder.encode([], [], make_constraints())
    assert si is not None


# =========================================================================== #
# 4. ISolver  (na ręcznie policzonych instancjach)
# =========================================================================== #

def _feasible(result, rewards, visit_costs, edges, budget):
    route = result_route(result)
    assert len(route) == len(set(route)), "duplikaty w trasie"
    spent = sum(visit_costs[n] for n in route)
    spent += sum(edges[(a, b)] for a, b in zip(route, route[1:]))
    assert spent <= budget + 1e-9, f"przekroczony budżet: {spent} > {budget}"


def test_solver_picks_optimal_subset_under_budget(solver):
    """Budżet 10. A(r=5,k=6), B(r=4,k=4), C(r=4,k=4), koszt przejść 0.
    Optimum = B+C (reward 8, koszt 8), a NIE A (reward 5)."""
    rewards = {"s": 0, "A": 5, "B": 4, "C": 4}
    visit = {"s": 0, "A": 6, "B": 4, "C": 4}
    edges = {(a, b): 0 for a in rewards for b in rewards if a != b}
    si = make_solver_input(rewards, visit, edges, budget=10, start="s")
    res = solver.solve(si)
    _feasible(res, rewards, visit, edges, 10)
    assert set(result_route(res)) - {"s"} == {"B", "C"}
    assert result_total_reward(res) == pytest.approx(8)


def test_solver_accounts_for_travel_cost(solver):
    """Dojście do X kosztuje 9, a budżet to 10 -> X (r=10, k=2) się nie opłaca
    razem z Y (r=3, k=1, dojście 1)."""
    rewards = {"s": 0, "X": 10, "Y": 3}
    visit = {"s": 0, "X": 2, "Y": 1}
    edges = {("s", "X"): 9, ("s", "Y"): 1, ("X", "Y"): 1, ("Y", "X"): 1,
             ("X", "s"): 9, ("Y", "s"): 1}
    si = make_solver_input(rewards, visit, edges, budget=10, start="s")
    res = solver.solve(si)
    _feasible(res, rewards, visit, edges, 10)
    # X nieosiągalne (9+2=11 > 10); jedyna sensowna trasa to s->Y
    assert result_route(res)[-1] == "Y"
    assert "X" not in result_route(res)


def test_solver_route_starts_at_start_node(solver):
    rewards = {"s": 0, "A": 2, "B": 2}
    visit = {"s": 0, "A": 1, "B": 1}
    edges = {(a, b): 1 for a in rewards for b in rewards if a != b}
    res = solver.solve(make_solver_input(rewards, visit, edges, budget=10, start="s"))
    assert result_route(res)[0] == "s"


def test_solver_infeasible_returns_empty_route_not_exception(solver):
    """Każdy węzeł droższy niż budżet -> trasa tylko ze startem (lub pusta)."""
    rewards = {"s": 0, "A": 5}
    visit = {"s": 0, "A": 100}
    edges = {("s", "A"): 1, ("A", "s"): 1}
    res = solver.solve(make_solver_input(rewards, visit, edges, budget=10, start="s"))
    assert set(result_route(res)) <= {"s"}
    assert result_total_reward(res) == 0


def test_solver_zero_budget(solver):
    rewards = {"s": 0, "A": 5}
    visit = {"s": 0, "A": 0.01}
    edges = {("s", "A"): 0.01, ("A", "s"): 0.01}
    res = solver.solve(make_solver_input(rewards, visit, edges, budget=0, start="s"))
    assert set(result_route(res)) <= {"s"}


def test_solver_is_deterministic(solver):
    rewards = {"s": 0, **{f"n{i}": 1 + (i % 3) for i in range(8)}}
    visit = {n: 1 for n in rewards}
    edges = {(a, b): 1 for a in rewards for b in rewards if a != b}
    si = make_solver_input(rewards, visit, edges, budget=6, start="s")
    assert result_route(solver.solve(si)) == result_route(solver.solve(si))


def test_solver_more_budget_never_gives_less_reward(solver):
    rewards = {"s": 0, "A": 3, "B": 4, "C": 5, "D": 2}
    visit = {"s": 0, "A": 2, "B": 3, "C": 4, "D": 1}
    edges = {(a, b): 1 for a in rewards for b in rewards if a != b}
    low = solver.solve(make_solver_input(rewards, visit, edges, budget=6, start="s"))
    high = solver.solve(make_solver_input(rewards, visit, edges, budget=20, start="s"))
    assert result_total_reward(high) >= result_total_reward(low)


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
    _feasible(res, rewards, visit, edges, 40)


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
    expected = [n for n in result_route(res) if n in {poi_id(p) for p in pois}]
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
    pois, conns, c, si, res = _solve_sample(encoder, solver, make_constraints(budget=150))
    plan = decoder.decode(res, si, pois, conns, c)
    assert plan_total_cost(plan) <= 150


def test_decoder_total_cost_matches_sum_of_parts(encoder, solver, decoder):
    pois, conns, c, si, res = _solve_sample(encoder, solver)
    plan = decoder.decode(res, si, pois, conns, c)
    prices = {poi_id(p): getattr(p, "price", None) for p in pois}
    if all(v is not None for v in prices.values()):  # tylko gdy POI ma pole price
        assert plan_total_cost(plan) >= sum(prices[s[0]] for s in plan_stops(plan)) - 1e-6


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
async def test_pipeline_end_to_end(poi_service, connection_service, encoder,
                                   solver, decoder, mapper):
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
async def test_pipeline_does_not_mutate_inputs(poi_service, connection_service,
                                               encoder, solver, decoder):
    pois = sample_pois()
    conns = full_connections(pois)
    before = (repr(pois), repr(conns))
    c = make_constraints()
    si = encoder.encode(pois, conns, c)
    decoder.decode(solver.solve(si), si, pois, conns, c)
    assert (repr(pois), repr(conns)) == before 