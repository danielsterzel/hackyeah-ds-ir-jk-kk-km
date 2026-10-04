from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.schemas.planning import (
    Coordinates,
    CostVector,
    Plan,
    PlanDay,
    PlanStop,
    POI,
    SolverStatus,
)
from app.service.planning_service import PlanningService
from app.service.ticket_price.ticket_price import TicketService


def test_ticket_mock_returns_price_for_known_dataset_attraction():
    ticket = TicketService.get_fallback_ticket_info(
        "Zamek Królewski na Wawelu – Państwowe Zbiory Sztuki"
    )

    assert ticket.min_price == 45.0
    assert ticket.max_price == 45.0
    assert ticket.currency == "PLN"
    assert ticket.confidence == "low"


def test_ticket_mock_does_not_invent_price_for_unknown_place():
    ticket = TicketService.get_fallback_ticket_info("Nieznana atrakcja")

    assert ticket.min_price is None
    assert ticket.max_price is None


@pytest.mark.asyncio
async def test_ticket_service_uses_mock_when_web_search_is_unavailable():
    service = TicketService()
    service._web_search_unavailable = True

    ticket = await service.get_ticket_info("Rynek Podziemny")

    assert ticket.min_price == 42.0
    assert ticket.max_price == 42.0


@pytest.mark.asyncio
async def test_mock_ticket_price_is_added_to_plan_total():
    arrival = datetime(2026, 10, 4, 10, 0)
    poi = POI(
        id="wawel",
        name="Zamek Królewski na Wawelu – Państwowe Zbiory Sztuki",
        location=Coordinates(lat=50.0540, lng=19.9352),
        visit_cost=CostVector(time_s=60 * 60),
    )
    plan = Plan(
        status=SolverStatus.FEASIBLE,
        total_cost=CostVector(time_s=60 * 60),
        days=[
            PlanDay(
                day_index=0,
                total_reward=1,
                total_cost=CostVector(time_s=60 * 60),
                stops=[
                    PlanStop(
                        order=0,
                        poi=poi,
                        arrival=arrival,
                        departure=arrival + timedelta(hours=1),
                        reward=1,
                    )
                ],
            )
        ],
    )
    service = PlanningService()
    service._ticket_service._web_search_unavailable = True

    updated = await service._add_ticket_prices_to_plan(plan)

    assert updated.total_cost.money_minor == 4_500
    assert updated.days[0].stops[0].poi.visit_cost.money_minor == 4_500
    assert updated.days[0].stops[0].poi.ticket_price_known is True
