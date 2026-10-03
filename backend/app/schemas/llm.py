from typing import Literal
from app.schemas.configured_schema import ConfiguredSchema
from pydantic import Field
from datetime import datetime
from uuid import UUID

PlaceCategory = Literal[
    "historic",
    "castle",
    "museum",
    "park",
    "nature",
    "architecture",
    "art",
    "entertainment",
    "music",
    "concert",
    "theater",
    "cinema",
    "sport",
    "forest",
    "landmark",
    "religious",
    "viewpoint",
    "monument",
    "garden",
    "nightlife",
    "shopping",
]
TransportMode = Literal[
    "walking",
    "bicycle",
    "tram",
    "public_transport",
    "scooter",
    "taxi",
    "car",
]

class Coordinates(ConfiguredSchema):

    latitude: float = Field(
        ...,
        ge=-90.0,
        le=90.0,
        description="Szerokość geograficzna w zakresie od -90 do 90",
    )
    longitude: float = Field(
        ...,
        ge=-180.0,
        le=180.0,
        description="Długość geograficzna w zakresie od -180 do 180",
    )


class LLMOutput(ConfiguredSchema):

    start_at: datetime
    end_at: datetime

    start_location: Coordinates
    end_location: Coordinates | None = None
    preferred_categories: list[PlaceCategory]
    food_preferences: list[str]  # potencjalnei rowniez literal
    transport_modes: list[TransportMode]
    avoid_crowds: bool
    weather_sensitive: bool
    optimization_strategy: Literal[
        "cheapest", "fastest", "most_places", "least_crowded"
    ]
    excluded_categories: list[PlaceCategory] = Field(default_factory=list)


class LLMQuestion(ConfiguredSchema):
    question: str


class UserAnswer(ConfiguredSchema):
    id: UUID
    answer: str


class UserInitQuestionnaire(ConfiguredSchema):
    id: UUID
    latitude: float
    longitude: float
    optimization_strategy: Literal[
        "cheapest", "fastest", "most_places", "least_crowded"
    ]
