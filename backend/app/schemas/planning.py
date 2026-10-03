"""
Schematy (Pydantic v2) i interfejsy domenowe dla backendu planowania tras.

Problem: Orienteering / Prize-Collecting Routing na grafie skierowanym.
    - POI           -> węzeł z nagrodą (reward) i kosztem wizyty
    - POIConnection -> krawędź z kosztami przejazdu (czas, pieniądze/paliwo)
    - cel solvera   -> max  sum(reward odwiedzonych węzłów) - sum(waga_k * koszt_k)
                       przy limitach budżetów (czas, pieniądze) na trasę

Przepływ danych:
    IPOIService            -> list[POI]
    IPOIConnectionService  -> list[POIConnection]
    ISolverEncoder         -> SolverInput (graf)
    ISolver                -> SolverResult (ścieżki po indeksach węzłów)
    ISolverDecoder         -> Plan
    IPlanningMapper        -> PlotterPayload (osobny feature: plotter)
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, time, timedelta
from decimal import Decimal
from enum import Enum
from typing import Sequence

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DomainModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


# --------------------------------------------------------------------------- #
# Wspólne
# --------------------------------------------------------------------------- #
class Coordinates(DomainModel):
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)


class TravelMode(str, Enum):
    WALK = "walk"
    BICYCLE = "bicycle"
    TRANSIT = "transit"
    DRIVE = "drive"


class CostVector(DomainModel):
    """
    Wektor kosztów (zasobów). Wartości całkowite - solvery (OR-Tools, CP-SAT)
    pracują na intach. Dodawalny: koszt trasy = suma kosztów węzłów i krawędzi.
    """
    time_s: int = Field(default=0, ge=0, description="Czas w sekundach")
    money_minor: int = Field(
        default=0, ge=0, description="Pieniądze (paliwo, bilety...) w jednostkach minor, np. grosze"
    )

    def __add__(self, other: CostVector) -> CostVector:
        return CostVector(
            time_s=self.time_s + other.time_s,
            money_minor=self.money_minor + other.money_minor,
        )


class OptionalCostVector(DomainModel):
    """Limity budżetowe; None = brak limitu na dany zasób."""
    time_s: int | None = Field(default=None, gt=0)
    money_minor: int | None = Field(default=None, ge=0)


class CostWeights(DomainModel):
    """
    Przeliczenie kosztów na „jednostki nagrody" w funkcji celu:
        objective = sum(reward) - time_weight * time_s - money_weight * money_minor
    0 = koszt tylko ogranicza (budżet), nie wpływa na cel.
    """
    time_weight: float = Field(default=0.0, ge=0)
    money_weight: float = Field(default=0.0, ge=0)


# --------------------------------------------------------------------------- #
# POI = węzeł (źródło: Google Places)
# --------------------------------------------------------------------------- #
class OpeningPeriod(DomainModel):
    day_of_week: int = Field(ge=0, le=6, description="0 = poniedziałek")
    open: time
    close: time


class POI(DomainModel):
    id: str = Field(description="Google place_id")
    name: str
    location: Coordinates
    address: str | None = None
    types: list[str] = Field(default_factory=list)
    rating: float | None = Field(default=None, ge=0, le=5)
    user_ratings_total: int | None = Field(default=None, ge=0)
    price_level: int | None = Field(default=None, ge=0, le=4)
    opening_hours: list[OpeningPeriod] = Field(default_factory=list)

    # --- pola istotne dla solvera ---
    reward: float | None = Field(
        default=None,
        ge=0,
        description="Nagroda za odwiedzenie. None = wylicza encoder (np. z rating/ratings_total)",
    )
    visit_cost: CostVector = Field(
        default_factory=lambda: CostVector(time_s=3600),
        description="Koszt samej wizyty (czas zwiedzania, bilet wstępu)",
    )


# --------------------------------------------------------------------------- #
# Wejście planowania i filtrowania POI
# --------------------------------------------------------------------------- #
class PlanningRequest(DomainModel):
    """
    Stabilny kontrakt domenowy dla planowania tras.

    Jest celowo niezależny od schematu odpowiedzi LLM. Adapter LLM może
    mapować swoje pola do tego modelu, a późniejsza zmiana kontraktu LLM nie
    wymaga zmiany serwisów domenowych.
    """

    start_at: datetime
    end_at: datetime
    start_location: Coordinates
    end_location: Coordinates | None = None
    budget_pln: Decimal = Field(ge=0)
    preferred_categories: list[str] = Field(default_factory=list)
    food_preferences: list[str] = Field(default_factory=list)
    transport_modes: list[TravelMode] = Field(default_factory=list)
    prefer_walking: bool = False
    avoid_crowds: bool = False
    weather_sensitive: bool = False
    optimization_strategy: str = "most_places"
    excluded_categories: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate_time_range(self) -> PlanningRequest:
        if self.end_at <= self.start_at:
            raise ValueError("end_at musi być późniejsze niż start_at")
        return self


# --------------------------------------------------------------------------- #
# POIConnection = krawędź skierowana (źródło: Google Routes / własne wyliczenia)
# --------------------------------------------------------------------------- #
class POIConnection(DomainModel):
    from_poi_id: str
    to_poi_id: str
    mode: TravelMode
    distance_m: int = Field(ge=0)
    duration: timedelta
    fuel_cost: float = Field(
        default=0.0, ge=0, description="Koszt paliwa/biletu przejazdu w walucie głównej"
    )
    polyline: str | None = Field(default=None, description="Encoded polyline (dla plotera)")

    @model_validator(mode="after")
    def _no_self_loop(self) -> POIConnection:
        if self.from_poi_id == self.to_poi_id:
            raise ValueError("Połączenie nie może łączyć POI samo ze sobą")
        return self


# --------------------------------------------------------------------------- #
# Ograniczenia planowania (wejście użytkownika)
# --------------------------------------------------------------------------- #
class PlanningConstraints(DomainModel):
    start_poi_id: str | None = None
    end_poi_id: str | None = None
    days: int = Field(default=1, ge=1, description="Liczba tras (jedna na dzień)")
    travel_mode: TravelMode = TravelMode.WALK
    budget_per_route: OptionalCostVector = Field(
        default_factory=lambda: OptionalCostVector(time_s=10 * 3600)
    )
    weights: CostWeights = Field(default_factory=CostWeights)
    max_pois: int | None = Field(default=None, ge=1)
    must_visit_ids: list[str] = Field(default_factory=list)
    day_start: time = time(9, 0)
    plan_date: datetime | None = Field(
        default=None, description="Pierwszy dzień planu (do godzin otwarcia)"
    )


# --------------------------------------------------------------------------- #
# Graf dla solvera
# --------------------------------------------------------------------------- #
class SolverNode(DomainModel):
    index: int = Field(ge=0)
    poi_id: str
    reward: float = Field(ge=0)
    visit_cost: CostVector
    mandatory: bool = False
    # okna czasowe (sekundy od początku trasy); puste = brak ograniczeń
    time_windows: list[tuple[int, int]] = Field(default_factory=list)


class SolverEdge(DomainModel):
    source: int = Field(ge=0)
    target: int = Field(ge=0)
    cost: CostVector


class SolverInput(DomainModel):
    nodes: list[SolverNode]
    edges: list[SolverEdge]
    num_routes: int = Field(default=1, ge=1)
    start_index: int | None = None
    end_index: int | None = None
    budget_per_route: OptionalCostVector
    weights: CostWeights
    max_nodes_per_route: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def _validate_graph(self) -> SolverInput:
        n = len(self.nodes)
        if [x.index for x in self.nodes] != list(range(n)):
            raise ValueError("Indeksy węzłów muszą być ciągłe: 0..n-1 w kolejności")
        seen: set[tuple[int, int]] = set()
        for e in self.edges:
            if not (0 <= e.source < n and 0 <= e.target < n):
                raise ValueError(f"Krawędź poza zakresem węzłów: {e.source}->{e.target}")
            if e.source == e.target:
                raise ValueError("Pętle własne są niedozwolone")
            if (e.source, e.target) in seen:
                raise ValueError(f"Zduplikowana krawędź: {e.source}->{e.target}")
            seen.add((e.source, e.target))
        for idx in (self.start_index, self.end_index):
            if idx is not None and not 0 <= idx < n:
                raise ValueError("start/end index poza zakresem")
        return self


# --------------------------------------------------------------------------- #
# Wynik solvera (surowy) i plan
# --------------------------------------------------------------------------- #
class SolverStatus(str, Enum):
    OPTIMAL = "optimal"
    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"
    TIMEOUT = "timeout"
    ERROR = "error"


class SolverRoute(DomainModel):
    node_path: list[int] = Field(description="Uporządkowane indeksy węzłów")
    reward: float
    cost: CostVector


class SolverResult(DomainModel):
    status: SolverStatus
    objective_value: float | None = None
    routes: list[SolverRoute] = Field(default_factory=list)
    solve_time_s: float | None = None


class PlanStop(DomainModel):
    order: int = Field(ge=0)
    poi: POI
    arrival: datetime
    departure: datetime
    reward: float
    connection_from_previous: POIConnection | None = None


class PlanDay(DomainModel):
    day_index: int = Field(ge=0)
    stops: list[PlanStop]
    total_reward: float
    total_cost: CostVector


class Plan(DomainModel):
    status: SolverStatus
    objective_value: float | None = None
    total_reward: float = 0.0
    total_cost: CostVector = Field(default_factory=CostVector)
    days: list[PlanDay] = Field(default_factory=list)
    skipped_poi_ids: list[str] = Field(default_factory=list)


# --------------------------------------------------------------------------- #
# Payload dla plotera (osobny feature)
# --------------------------------------------------------------------------- #
class PlotPoint(DomainModel):
    poi_id: str
    label: str
    order: int
    location: Coordinates
    day_index: int


class PlotSegment(DomainModel):
    from_poi_id: str
    to_poi_id: str
    day_index: int
    mode: TravelMode
    polyline: str | None = None
    path: list[Coordinates] | None = None


class PlotterPayload(DomainModel):
    points: list[PlotPoint]
    segments: list[PlotSegment]
    bounds_sw: Coordinates | None = None
    bounds_ne: Coordinates | None = None


# --------------------------------------------------------------------------- #
# Interfejsy domenowe
# --------------------------------------------------------------------------- #
class IPOIService(ABC):
    @abstractmethod
    async def get_pois(self, query: str, center: Coordinates, radius_m: int) -> list[POI]: ...


class IPOIFilterService(ABC):
    """
    Filtruje wynik IPOIService według domenowych preferencji planowania.

    Pobieranie danych pozostaje odpowiedzialnością IPOIService; ten interfejs
    nie wykonuje zapytań sieciowych i działa na już pobranej kolekcji POI.
    """

    @abstractmethod
    def filter_pois(
        self,
        pois: Sequence[POI],
        request: PlanningRequest,
    ) -> list[POI]: ...


class IPOIConnectionService(ABC):
    @abstractmethod
    async def get_connections(
        self, pois: Sequence[POI], mode: TravelMode
    ) -> list[POIConnection]: ...


class ISolverEncoder(ABC):
    """POI -> węzły (reward, visit_cost), POIConnection -> krawędzie (CostVector)."""

    @abstractmethod
    def encode(
        self,
        pois: Sequence[POI],
        connections: Sequence[POIConnection],
        constraints: PlanningConstraints,
    ) -> SolverInput: ...


class ISolver(ABC):
    @abstractmethod
    def solve(self, solver_input: SolverInput) -> SolverResult: ...


class ISolverDecoder(ABC):
    @abstractmethod
    def decode(
        self,
        result: SolverResult,
        solver_input: SolverInput,
        pois: Sequence[POI],
        connections: Sequence[POIConnection],
        constraints: PlanningConstraints,
    ) -> Plan: ...


class IPlanningMapper(ABC):
    @abstractmethod
    def to_plotter(self, plan: Plan) -> PlotterPayload: ...