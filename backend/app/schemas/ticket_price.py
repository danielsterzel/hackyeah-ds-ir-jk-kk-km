from app.schemas.configured_schema import ConfiguredSchema

from typing import Literal

class TicketInfo(ConfiguredSchema):
    min_price: float | None = None
    max_price: float | None = None
    currency: Literal["PLN"] = "PLN"
    is_free: bool = False
    source_url: str | None = None
    confidence: Literal["high", "medium", "low"] = "low"