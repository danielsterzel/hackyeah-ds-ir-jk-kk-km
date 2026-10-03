from decimal import Decimal
from typing import Literal

from app.schemas.configured_schema import ConfiguredSchema

from datetime import datetime

class Coordinates(ConfiguredSchema):
    latitude: float
    longitude: float

class LLMOutput(ConfiguredSchema):

    start_at: datetime
    end_at: datetime

    start_location: Coordinates
    end_location: Coordinates | None = None
    budget_pln: Decimal | None = None
    preferred_categories: list[str]
    food_preferences: list[str]
    transport_modes: list[str]
    prefer_walking: bool
    avoid_crowds: bool
    weather_sensitive: bool
    optimization_strategy: Literal["cheapest", "fastest", "most_places", "least_crowded"]

    """
    {
  "start_at": "2026-10-03T10:00:00+02:00",
  "end_at": "2026-10-03T17:00:00+02:00",

  "start_location": {
    "latitude": 50.067,
    "longitude": 19.912
  },

  "end_location": null,

  "budget_pln": 150,

  "preferred_categories": [
    "museum",
    "historic",
    "food"
  ],

  "food_preferences": [
    "polish"
  ],

  "transport_modes": [
    "walking",
    "public_transport"
  ],

  "prefer_walking": true,
  "avoid_crowds": false,
  "weather_sensitive": true,

  "optimization_strategy": "cheapest"
}
    """