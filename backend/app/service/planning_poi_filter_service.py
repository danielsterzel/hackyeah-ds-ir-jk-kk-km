"""Filtrowanie i ranking POI na podstawie żądania planowania."""

from __future__ import annotations

import math
import unicodedata
from datetime import date, datetime, time, timedelta
from typing import Sequence

from app.schemas.planning import IPOIFilterService, POI, PlanningRequest

EARTH_RADIUS_M = 6_371_000.0

GENERIC_FOOD_REQUEST_MARKERS = (
    "restaurac",
    "restaurant",
    "jedzen",
    "zjesc",
    "posilek",
    "obiad",
    "kolac",
    "lunch",
    "dinner",
    "food",
)
FOOD_VENUE_MARKERS = (
    "restaurac",
    "kuchnia ",
    "bistro",
    "kawiar",
    "cafe",
    "pizzer",
    "pizza",
    "pierogar",
    "pierog",
    "sushi",
    "ramen",
    "burger",
    "jadlodaj",
    "cukiern",
    "gastropub",
    "fast food",
)
CUISINE_ALIASES = {
    "italian": ("italian", "wlosk"),
    "wlosk": ("italian", "wlosk"),
    "polish": ("polish", "polsk"),
    "polsk": ("polish", "polsk"),
    "greek": ("greek", "greck"),
    "greck": ("greek", "greck"),
    "japanese": ("japanese", "japonsk"),
    "japonsk": ("japanese", "japonsk"),
    "chinese": ("chinese", "chinsk"),
    "chinsk": ("chinese", "chinsk"),
    "indian": ("indian", "indyjsk"),
    "indyjsk": ("indian", "indyjsk"),
    "mexican": ("mexican", "meksykansk"),
    "meksykansk": ("mexican", "meksykansk"),
}


def _fold(text: str) -> str:
    text = text.casefold().replace("ł", "l")
    return "".join(
        character
        for character in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(character)
    )


def food_preference_matches(poi: POI, preferences: Sequence[str]) -> bool:
    """Matches generic restaurant requests and common cuisine aliases."""
    searchable = _fold(" ".join([poi.name, *poi.types]))
    is_food_venue = any(marker in searchable for marker in FOOD_VENUE_MARKERS)

    for preference in preferences:
        normalized = _fold(preference).strip()
        if not normalized:
            continue
        if any(marker in normalized for marker in GENERIC_FOOD_REQUEST_MARKERS):
            if is_food_venue:
                return True
            continue
        if normalized in searchable:
            return True
        for alias, variants in CUISINE_ALIASES.items():
            if alias in normalized and any(
                variant in searchable for variant in variants
            ):
                return True
    return False


def haversine_m(a_lat: float, a_lng: float, b_lat: float, b_lng: float) -> float:
    """Zwraca odległość po powierzchni Ziemi w metrach."""
    lat1, lat2 = math.radians(a_lat), math.radians(b_lat)
    dlat = lat2 - lat1
    dlng = math.radians(b_lng - a_lng)
    h = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


class PreferencePOIFilterService(IPOIFilterService):
    """
    Wybiera i szereguje POI dla konkretnego żądania planowania.

    `max_results` i `max_distance_m` są ograniczeniami technicznymi serwisu,
    a nie częścią kontraktu LLM. Dzięki temu można je zmienić bez zmiany
    `PlanningRequest`.
    """

    def __init__(
        self,
        max_results: int | None = None,
        max_distance_m: float | None = None,
        preferred_reward_multiplier: float = 1.5,
        food_reward_multiplier: float = 1.25,
    ) -> None:
        if max_results is not None and max_results < 1:
            raise ValueError("max_results musi być dodatnie")
        if max_distance_m is not None and max_distance_m < 0:
            raise ValueError("max_distance_m nie może być ujemne")
        if preferred_reward_multiplier < 1 or food_reward_multiplier < 1:
            raise ValueError("mnożniki nagrody muszą być >= 1")

        self._max_results = max_results
        self._max_distance_m = max_distance_m
        self._preferred_reward_multiplier = preferred_reward_multiplier
        self._food_reward_multiplier = food_reward_multiplier

    def filter_pois(
        self,
        pois: Sequence[POI],
        request: PlanningRequest,
    ) -> list[POI]:
        candidates: list[tuple[int, float, POI]] = []
        for poi in pois:
            distance = self._distance_from_request(poi, request)
            if self._max_distance_m is not None and distance > self._max_distance_m:
                continue
            if self._matches_category(poi, request.excluded_categories):
                continue
            if not self._is_visitable_in_range(poi, request.start_at, request.end_at):
                continue

            preferred, food_match = self._preference_matches(poi, request)
            filtered_poi = self._with_adjusted_reward(
                poi,
                preferred=preferred,
                food_match=food_match,
                avoid_crowds=request.avoid_crowds,
            )
            candidates.append(
                (
                    0 if preferred or food_match else 1,
                    self._ranking_score(distance, filtered_poi, request),
                    filtered_poi,
                )
            )

        candidates.sort(key=lambda item: (item[0], item[1], item[2].id))
        result = [poi for _, _, poi in candidates]
        if self._max_results is not None:
            return result[: self._max_results]
        return result

    @staticmethod
    def _distance_from_request(poi: POI, request: PlanningRequest) -> float:
        start = request.start_location
        start_distance = haversine_m(
            start.lat, start.lng, poi.location.lat, poi.location.lng
        )
        if request.end_location is None:
            return start_distance

        end = request.end_location
        end_distance = haversine_m(end.lat, end.lng, poi.location.lat, poi.location.lng)
        return start_distance + end_distance

    @staticmethod
    def _preference_matches(
        poi: POI,
        request: PlanningRequest,
    ) -> tuple[bool, bool]:
        type_tags = {item.casefold() for item in poi.types}
        preferred = any(
            category.casefold() in type_tags
            for category in request.preferred_categories
        )
        food_match = food_preference_matches(poi, request.food_preferences)
        return preferred, food_match

    @staticmethod
    def _matches_category(poi: POI, categories: Sequence[str]) -> bool:
        type_tags = {item.casefold() for item in poi.types}
        return any(category.casefold() in type_tags for category in categories)

    def _with_adjusted_reward(
        self,
        poi: POI,
        *,
        preferred: bool,
        food_match: bool,
        avoid_crowds: bool,
    ) -> POI:
        reward = poi.reward
        if reward is None:
            rating = poi.rating if poi.rating is not None else 3.0
            reviews = poi.user_ratings_total or 0
            reward = rating * (1 + math.log10(1 + reviews))

        if preferred:
            reward *= self._preferred_reward_multiplier
        if food_match:
            reward *= self._food_reward_multiplier
        if avoid_crowds and poi.user_ratings_total:
            reward /= 1 + math.log10(1 + poi.user_ratings_total) / 10

        return poi.model_copy(update={"reward": reward})

    @staticmethod
    def _ranking_score(
        distance: float,
        poi: POI,
        request: PlanningRequest,
    ) -> float:
        distance_weight = 2.0 if request.prefer_walking else 1.0
        return distance * distance_weight / max(poi.reward or 0.0, 1e-9)

    @staticmethod
    def _is_visitable_in_range(
        poi: POI,
        start_at: datetime,
        end_at: datetime,
    ) -> bool:
        if not poi.opening_hours:
            return True

        # OpeningPeriod stores local wall-clock times without timezone
        # information. Compare them with the request's local wall-clock range.
        start_at = start_at.replace(tzinfo=None)
        end_at = end_at.replace(tzinfo=None)
        current_date = start_at.date()
        last_date = end_at.date()
        while current_date <= last_date:
            day_start = max(
                (
                    start_at
                    if current_date == start_at.date()
                    else datetime.combine(current_date, time.min)
                ),
                datetime.combine(current_date, time.min),
            )
            day_end = min(
                (
                    end_at
                    if current_date == end_at.date()
                    else datetime.combine(current_date, time.max)
                ),
                datetime.combine(current_date, time.max),
            )
            if PreferencePOIFilterService._has_opening_overlap(
                poi, current_date, day_start, day_end
            ):
                return True
            current_date += timedelta(days=1)
        return False

    @staticmethod
    def _has_opening_overlap(
        poi: POI,
        current_date: date,
        requested_start: datetime,
        requested_end: datetime,
    ) -> bool:
        visit_duration = timedelta(seconds=poi.visit_cost.time_s)
        for period in poi.opening_hours:
            if period.day_of_week != current_date.weekday():
                continue
            opening = datetime.combine(current_date, period.open)
            closing = datetime.combine(current_date, period.close)
            if closing <= opening:
                closing += timedelta(days=1)

            visit_start = max(opening, requested_start)
            visit_end = visit_start + visit_duration
            if visit_end <= closing and visit_start <= requested_end:
                return True
        return False
