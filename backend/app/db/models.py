from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Double,
    Enum as SqlEnum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PostgreSQLUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TripStatus(str, Enum):
    DRAFT = "draft"
    PLANNING = "planning"
    PLANNED = "planned"
    FAILED = "failed"


class OptimizationStrategy(str, Enum):
    CHEAPEST = "cheapest"
    FASTEST = "fastest"
    MOST_PLACES = "most_places"
    LEAST_CROWDED = "least_crowded"


class TransportMode(str, Enum):
    WALKING = "walking"
    PUBLIC_TRANSPORT = "public_transport"
    BICYCLE = "bicycle"
    SCOOTER = "scooter"
    CAR = "car"
    TAXI = "taxi"


def _varchar_enum(enum_type: type[Enum], name: str) -> SqlEnum:
    """Persist a Python enum as VARCHAR rather than a PostgreSQL enum type."""

    return SqlEnum(
        enum_type,
        name=name,
        native_enum=False,
        create_constraint=False,
        length=30,
        values_callable=lambda members: [member.value for member in members],
    )


class Place(Base):
    __tablename__ = "places"
    __table_args__ = (
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_places_latitude_range"),
        CheckConstraint(
            "longitude BETWEEN -180 AND 180", name="ck_places_longitude_range"
        ),
        CheckConstraint(
            "average_visit_minutes >= 0",
            name="ck_places_average_visit_minutes_nonnegative",
        ),
        CheckConstraint(
            "estimated_cost_pln >= 0",
            name="ck_places_estimated_cost_pln_nonnegative",
        ),
        UniqueConstraint(
            "external_source",
            "external_id",
            name="uq_places_external_source_external_id",
        ),
        Index("ix_places_district", "district"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    categories: Mapped[list[str]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default=text("'[]'::jsonb"),
    )
    latitude: Mapped[float] = mapped_column(Double, nullable=False)
    longitude: Mapped[float] = mapped_column(Double, nullable=False)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    district: Mapped[str | None] = mapped_column(String(100), nullable=True)
    average_visit_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost_pln: Mapped[Decimal | None] = mapped_column(
        Numeric(10, 2), nullable=True
    )
    opening_hours: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    external_source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # ``metadata`` is reserved by SQLAlchemy's declarative API, so the Python
    # attribute is named ``extra_metadata`` while the database column remains
    # exactly ``metadata`` as required by the schema.
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )

    plan_stops: Mapped[list[PlanStop]] = relationship(
        back_populates="place", passive_deletes=True
    )


class Trip(Base):
    __tablename__ = "trips"
    __table_args__ = (
        CheckConstraint("start_at < end_at", name="ck_trips_start_before_end"),
        CheckConstraint(
            "start_latitude BETWEEN -90 AND 90",
            name="ck_trips_start_latitude_range",
        ),
        CheckConstraint(
            "start_longitude BETWEEN -180 AND 180",
            name="ck_trips_start_longitude_range",
        ),
        CheckConstraint(
            "end_latitude IS NULL OR end_latitude BETWEEN -90 AND 90",
            name="ck_trips_end_latitude_range",
        ),
        CheckConstraint(
            "end_longitude IS NULL OR end_longitude BETWEEN -180 AND 180",
            name="ck_trips_end_longitude_range",
        ),
        CheckConstraint(
            "(end_latitude IS NULL) = (end_longitude IS NULL)",
            name="ck_trips_end_coordinates_together",
        ),
        CheckConstraint("budget_pln >= 0", name="ck_trips_budget_pln_nonnegative"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    start_latitude: Mapped[float] = mapped_column(Double, nullable=False)
    start_longitude: Mapped[float] = mapped_column(Double, nullable=False)
    end_latitude: Mapped[float | None] = mapped_column(Double, nullable=True)
    end_longitude: Mapped[float | None] = mapped_column(Double, nullable=True)
    budget_pln: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    preferences: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    status: Mapped[TripStatus] = mapped_column(
        _varchar_enum(TripStatus, "trip_status"),
        nullable=False,
        default=TripStatus.DRAFT,
        server_default=text("'draft'"),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    plans: Mapped[list[TripPlan]] = relationship(
        back_populates="trip",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )


class TripPlan(Base):
    __tablename__ = "trip_plans"
    __table_args__ = (
        CheckConstraint(
            "total_duration_minutes >= 0",
            name="ck_trip_plans_total_duration_minutes_nonnegative",
        ),
        CheckConstraint(
            "total_distance_meters >= 0",
            name="ck_trip_plans_total_distance_meters_nonnegative",
        ),
        CheckConstraint(
            "estimated_cost_pln >= 0",
            name="ck_trip_plans_estimated_cost_pln_nonnegative",
        ),
        CheckConstraint(
            "walking_minutes >= 0",
            name="ck_trip_plans_walking_minutes_nonnegative",
        ),
        UniqueConstraint("trip_id", "strategy", name="uq_trip_plans_trip_id_strategy"),
        Index("ix_trip_plans_trip_id", "trip_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    trip_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("trips.id", ondelete="CASCADE"),
        nullable=False,
    )
    strategy: Mapped[OptimizationStrategy] = mapped_column(
        _varchar_enum(OptimizationStrategy, "optimization_strategy"),
        nullable=False,
    )
    total_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    total_distance_meters: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_cost_pln: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    walking_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    score: Mapped[float | None] = mapped_column(Double, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    trip: Mapped[Trip] = relationship(back_populates="plans")
    stops: Mapped[list[PlanStop]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="PlanStop.position",
    )
    route_legs: Mapped[list[RouteLeg]] = relationship(
        back_populates="plan",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="RouteLeg.position",
    )


class PlanStop(Base):
    __tablename__ = "plan_stops"
    __table_args__ = (
        CheckConstraint("position >= 0", name="ck_plan_stops_position_nonnegative"),
        CheckConstraint(
            "arrival_at < departure_at",
            name="ck_plan_stops_arrival_before_departure",
        ),
        CheckConstraint(
            "planned_visit_minutes > 0",
            name="ck_plan_stops_planned_visit_minutes_positive",
        ),
        CheckConstraint(
            "estimated_cost_pln >= 0",
            name="ck_plan_stops_estimated_cost_pln_nonnegative",
        ),
        UniqueConstraint("plan_id", "position", name="uq_plan_stops_plan_id_position"),
        Index("ix_plan_stops_plan_id", "plan_id"),
        Index("ix_plan_stops_place_id", "place_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    plan_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("trip_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    place_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("places.id", ondelete="RESTRICT"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    arrival_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    departure_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    planned_visit_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_cost_pln: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0"), server_default=text("0")
    )

    plan: Mapped[TripPlan] = relationship(back_populates="stops")
    place: Mapped[Place] = relationship(back_populates="plan_stops")
    outgoing_route_legs: Mapped[list[RouteLeg]] = relationship(
        back_populates="from_stop",
        foreign_keys="RouteLeg.from_stop_id",
    )
    incoming_route_legs: Mapped[list[RouteLeg]] = relationship(
        back_populates="to_stop",
        foreign_keys="RouteLeg.to_stop_id",
    )


class RouteLeg(Base):
    __tablename__ = "route_legs"
    __table_args__ = (
        CheckConstraint(
            "duration_minutes >= 0",
            name="ck_route_legs_duration_minutes_nonnegative",
        ),
        CheckConstraint(
            "distance_meters >= 0",
            name="ck_route_legs_distance_meters_nonnegative",
        ),
        CheckConstraint(
            "estimated_cost_pln >= 0",
            name="ck_route_legs_estimated_cost_pln_nonnegative",
        ),
        CheckConstraint(
            "estimated_co2_grams >= 0",
            name="ck_route_legs_estimated_co2_grams_nonnegative",
        ),
        CheckConstraint(
            "from_stop_id IS NULL OR to_stop_id IS NULL "
            "OR from_stop_id <> to_stop_id",
            name="ck_route_legs_different_stops",
        ),
        UniqueConstraint("plan_id", "position", name="uq_route_legs_plan_id_position"),
        Index("ix_route_legs_plan_id", "plan_id"),
    )

    id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    plan_id: Mapped[UUID] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("trip_plans.id", ondelete="CASCADE"),
        nullable=False,
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    from_stop_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("plan_stops.id"),
        nullable=True,
    )
    to_stop_id: Mapped[UUID | None] = mapped_column(
        PostgreSQLUUID(as_uuid=True),
        ForeignKey("plan_stops.id"),
        nullable=True,
    )
    transport_mode: Mapped[TransportMode] = mapped_column(
        _varchar_enum(TransportMode, "transport_mode"), nullable=False
    )
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    distance_meters: Mapped[int] = mapped_column(Integer, nullable=False)
    estimated_cost_pln: Mapped[Decimal] = mapped_column(
        Numeric(10, 2), nullable=False, default=Decimal("0"), server_default=text("0")
    )
    estimated_co2_grams: Mapped[int | None] = mapped_column(Integer, nullable=True)
    route_geometry: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    external_data: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)

    plan: Mapped[TripPlan] = relationship(back_populates="route_legs")
    from_stop: Mapped[PlanStop | None] = relationship(
        back_populates="outgoing_route_legs",
        foreign_keys=[from_stop_id],
    )
    to_stop: Mapped[PlanStop | None] = relationship(
        back_populates="incoming_route_legs",
        foreign_keys=[to_stop_id],
    )
