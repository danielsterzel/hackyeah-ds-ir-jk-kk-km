"""Uzupełnianie kosztu wizyty POI na podstawie informacji z LLM."""

from __future__ import annotations

import asyncio
from typing import ClassVar

from ollama import chat
from pydantic import BaseModel, ConfigDict, Field

from app.schemas.planning import CostVector, IPOICostService, POI


class POICostEstimate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visit_duration_min: int | None = Field(default=None, ge=0)
    price_pln: float | None = Field(default=None, ge=0)


class OllamaPOICostService(IPOICostService):
    """Szacuje koszt wizyty tylko dla POI wybranych przez solver."""

    MODEL: ClassVar[str] = "qwen3:30b"

    async def enrich_poi_cost(self, poi: POI) -> POI:
        response = await asyncio.to_thread(
            chat,
            model=self.MODEL,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Ustal koszt wizyty w podanym punkcie zainteresowania. "
                        "Korzystaj wyłącznie z wiarygodnych, znanych informacji. "
                        "Jeżeli nie znasz ceny biletu lub czasu zwiedzania, zwróć "
                        "null dla odpowiedniego pola. Zwróć wyłącznie JSON."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "POI:\n"
                        f"name: {poi.name}\n"
                        f"address: {poi.address or 'brak'}\n"
                        f"types: {', '.join(poi.types) or 'brak'}\n\n"
                        "Pola odpowiedzi:\n"
                        "- visit_duration_min: czas wizyty w minutach albo null\n"
                        "- price_pln: cena biletu w PLN albo null"
                    ),
                },
            ],
            format=POICostEstimate.model_json_schema(),
            think=False,
            keep_alive="1m",
            options={"temperature": 0},
        )
        estimate = POICostEstimate.model_validate_json(response.message.content)
        current = poi.visit_cost
        return poi.model_copy(
            update={
                "visit_cost": CostVector(
                    time_s=(
                        estimate.visit_duration_min * 60
                        if estimate.visit_duration_min is not None
                        else current.time_s
                    ),
                    money_minor=(
                        round(estimate.price_pln * 100)
                        if estimate.price_pln is not None
                        else current.money_minor
                    ),
                )
            }
        )
