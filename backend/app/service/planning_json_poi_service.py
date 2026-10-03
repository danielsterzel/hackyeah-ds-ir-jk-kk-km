"""
Implementacja IPOIService czytająca listę atrakcji z pliku JSON
(format: eksport scrapera Google Maps / Apify) i mapująca ją na POI.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import re
import unicodedata
from datetime import time
from pathlib import Path
from typing import Any

from app.schemas.llm import PlaceCategory
from app.schemas.planning import Coordinates, IPOIService, OpeningPeriod, POI

logger = logging.getLogger(__name__)

EARTH_RADIUS_M = 6_371_000


# --------------------------------------------------------------------------- #
# Helpery
# --------------------------------------------------------------------------- #
def haversine_m(a: Coordinates, b: Coordinates) -> float:
    lat1, lat2 = math.radians(a.lat), math.radians(b.lat)
    dlat = lat2 - lat1
    dlng = math.radians(b.lng - a.lng)
    h = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1) * math.cos(lat2) * math.sin(dlng / 2) ** 2
    )
    return 2 * EARTH_RADIUS_M * math.asin(math.sqrt(h))


def fold(text: str) -> str:
    """lower + usunięcie polskich znaków diakrytycznych (do porównań tekstu)."""
    text = text.lower().replace("ł", "l")
    return "".join(
        c for c in unicodedata.normalize("NFKD", text) if not unicodedata.combining(c)
    )


_DAYS = {
    "poniedzialek": 0,
    "wtorek": 1,
    "sroda": 2,
    "czwartek": 3,
    "piatek": 4,
    "sobota": 5,
    "niedziela": 6,
    "monday": 0,
    "tuesday": 1,
    "wednesday": 2,
    "thursday": 3,
    "friday": 4,
    "saturday": 5,
    "sunday": 6,
}

_TIME = r"\d{1,2}(?::\d{2})?\s*(?:am|pm)?"
_RANGE_RE = re.compile(rf"({_TIME})\s*(?:to|do|–|-|—)\s*({_TIME})", re.IGNORECASE)
_END_OF_DAY = time(23, 59, 59)

_RAW_APIFY_CATEGORY_MAPPING: dict[str, tuple[PlaceCategory, ...]] = {
    "atrakcja turystyczna": ("landmark",),
    "obiekt historyczny": ("historic", "landmark"),
    "miejsce historyczne": ("historic", "landmark"),
    "muzeum historycznego miejsca": ("museum", "historic", "landmark"),
    "budynek zabytkowy": ("historic", "architecture", "landmark"),
    "zamek": ("castle", "historic", "architecture", "landmark"),
    "willa": ("architecture",),
    "galeria sztuki": ("art",),
    "muzeum sztuki": ("museum", "art"),
    "muzeum sztuki nowoczesnej": ("museum", "art"),
    "muzeum rzeźby": ("museum", "art"),
    "promocja sztuki": ("art",),
    "sztuka": ("art",),
    "malarstwo": ("art",),
    "rzeźbiarz": ("art",),
    "rezerwat przyrody": ("nature",),
    "teren spacerowy": ("nature",),
    "park": ("park", "nature"),
    "park miejski": ("park", "nature"),
    "park krajobrazowy": ("park", "nature"),
    "park pamięci": ("park", "nature", "monument"),
    "ogród": ("garden", "nature"),
    "ogród osiedlowy": ("garden", "nature"),
    "ogród botaniczny": ("garden", "nature"),
    "las państwowy": ("forest", "nature"),
    "zoo": ("nature", "entertainment"),
    "centrum rozrywki": ("entertainment",),
    "rozrywka": ("entertainment",),
    "park rozrywki": ("entertainment",),
    "sala zabaw": ("entertainment",),
    "plac zabaw": ("entertainment",),
    "tor gokartowy": ("entertainment", "sport"),
    "klub komediowy": ("entertainment", "nightlife"),
    "sala koncertowa": ("music", "concert"),
    "filharmonia": ("music", "concert"),
    "opera": ("music", "concert", "theater"),
    "klub muzyczny": ("music", "nightlife"),
    "bar z muzyką na żywo": ("music", "nightlife"),
    "amfiteatr": ("music", "concert", "theater"),
    "centrum kultury": ("art", "entertainment"),
    "dom kultury": ("art", "entertainment"),
    "kino": ("cinema", "entertainment"),
    "centrum rekreacyjno-sportowe": ("sport",),
    "centrum sportów ekstremalnych": ("sport",),
    "klub sportowy": ("sport",),
    "siłownia": ("sport",),
    "skatepark": ("sport",),
    "punkt widokowy": ("viewpoint", "landmark"),
    "taras widokowy": ("viewpoint", "landmark"),
    "pomnik": ("monument", "landmark"),
    "rzeźba": ("monument", "art"),
    "posąg": ("monument", "art"),
    "przestrzeń pamięci": ("monument", "historic"),
    "bar": ("nightlife",),
    "lounge bar": ("nightlife",),
    "bar koktajlowy": ("nightlife",),
    "pub": ("nightlife",),
    "gastropub": ("nightlife",),
    "piwiarnia": ("nightlife",),
    "winiarnia": ("nightlife",),
    "ogródek piwny": ("nightlife",),
    "klub": ("nightlife",),
    "supermarket": ("shopping",),
}

_APIFY_CATEGORY_MAPPING = {
    fold(category): tags for category, tags in _RAW_APIFY_CATEGORY_MAPPING.items()
}

_RELIGIOUS_CATEGORY_MARKERS = tuple(
    fold(marker)
    for marker in (
        "kościół",
        "klasztor",
        "kaplica",
        "świątynia",
        "religijn",
        "parafia",
        "bazylika",
        "katedra",
        "pielgrzym",
        "sanktuarium",
        "synagoga",
    )
)


def map_apify_categories(categories: list[str]) -> list[PlaceCategory]:
    """Map localized Apify/Google categories to the planner's stable taxonomy."""
    mapped: list[PlaceCategory] = []

    for category in categories:
        normalized = fold(category).strip()
        tags = list(_APIFY_CATEGORY_MAPPING.get(normalized, ()))

        if "muzeum" in normalized:
            tags.append("museum")
        if normalized.startswith("teatr") or normalized == "grupa teatralna":
            tags.append("theater")
        if any(marker in normalized for marker in _RELIGIOUS_CATEGORY_MARKERS):
            tags.append("religious")
        if normalized.startswith("sklep"):
            tags.append("shopping")

        for tag in tags:
            if tag not in mapped:
                mapped.append(tag)

    return mapped


def _parse_time(raw: str, default_meridiem: str | None = None) -> time:
    m = re.match(r"(\d{1,2})(?::(\d{2}))?\s*(am|pm)?", raw.strip(), re.IGNORECASE)
    assert m
    hour, minute = int(m.group(1)), int(m.group(2) or 0)
    meridiem = (m.group(3) or default_meridiem or "").lower()
    if meridiem == "pm" and hour < 12:
        hour += 12
    elif meridiem == "am" and hour == 12:
        hour = 0
    if hour == 24:
        return _END_OF_DAY
    return time(hour % 24, minute)


def parse_opening_hours(raw_hours: list[dict[str, Any]] | None) -> list[OpeningPeriod]:
    """
    Oczekiwany format wpisu: {"day": "poniedziałek", "hours": "09:00 to 17:00"}.
    Obsługuje: wiele przedziałów, "Open 24 hours"/"Całą dobę", "Closed"/"Nieczynne",
    godziny AM/PM oraz przedziały przechodzące przez północ.
    Nierozpoznane wpisy są pomijane (z logiem), a nie przerywają mapowania.
    """
    periods: list[OpeningPeriod] = []
    for entry in raw_hours or []:
        day = _DAYS.get(fold(str(entry.get("day", ""))).strip())
        hours = str(entry.get("hours", ""))
        if day is None:
            logger.debug("Nierozpoznany dzień w openingHours: %r", entry)
            continue

        folded = fold(hours)
        if "24 hours" in folded or "cala dobe" in folded or "24 godz" in folded:
            periods.append(
                OpeningPeriod(day_of_week=day, open=time(0, 0), close=_END_OF_DAY)
            )
            continue

        for start_raw, end_raw in _RANGE_RE.findall(hours):
            end_mer = re.search(r"am|pm", end_raw, re.IGNORECASE)
            start_mer = re.search(r"am|pm", start_raw, re.IGNORECASE)
            start = _parse_time(start_raw, "am" if end_mer and not start_mer else None)
            end = _parse_time(end_raw)
            if end == time(0, 0):  # "do 00:00" = do końca dnia
                end = _END_OF_DAY
            if end > start:
                periods.append(OpeningPeriod(day_of_week=day, open=start, close=end))
            else:  # przedział przez północ -> dzielimy na dwa dni
                periods.append(
                    OpeningPeriod(day_of_week=day, open=start, close=_END_OF_DAY)
                )
                periods.append(
                    OpeningPeriod(day_of_week=(day + 1) % 7, open=time(0, 0), close=end)
                )
        # brak dopasowań (np. "Closed"/"Nieczynne") => dzień bez okien otwarcia
    return periods


def parse_price_level(price: Any) -> int | None:
    """Scraper zwraca napis typu "$$" lub zakres w walucie; mapujemy tylko "$"."""
    if isinstance(price, str) and price and set(price) <= {"$"}:
        return min(len(price), 4)
    return None


# --------------------------------------------------------------------------- #
# Mapper: surowy JSON -> POI
# --------------------------------------------------------------------------- #
class GoogleMapsPlaceMapper:
    """Zwraca None dla rekordów, których nie powinno się planować."""

    def to_poi(self, raw: dict[str, Any]) -> POI | None:
        place_id = raw.get("placeId")
        loc = raw.get("location") or {}
        if not place_id or loc.get("lat") is None or loc.get("lng") is None:
            return None
        if raw.get("permanentlyClosed") or raw.get("temporarilyClosed"):
            return None
        if raw.get("isAdvertisement"):
            return None

        categories = list(raw.get("categories") or [])
        if raw.get("categoryName") and raw["categoryName"] not in categories:
            categories.insert(0, raw["categoryName"])

        categories.extend(
            category
            for category in map_apify_categories(categories)
            if category not in categories
        )

        return POI(
            id=place_id,
            name=raw.get("title") or place_id,
            location=Coordinates(lat=loc["lat"], lng=loc["lng"]),
            address=raw.get("address"),
            # Oryginalne kategorie Apify oraz dopisane stabilne tagi planera.
            types=categories,
            rating=raw.get("totalScore"),
            user_ratings_total=raw.get("reviewsCount"),
            price_level=parse_price_level(raw.get("price")),
            opening_hours=parse_opening_hours(raw.get("openingHours")),
            # reward=None  -> wylicza encoder; visit_cost -> wartość domyślna z modelu
        )


# --------------------------------------------------------------------------- #
# Serwis
# --------------------------------------------------------------------------- #
class JsonPOIService(IPOIService):
    def __init__(
        self,
        json_path: str | Path,
        mapper: GoogleMapsPlaceMapper | None = None,
    ) -> None:
        self._path = Path(json_path)
        self._mapper = mapper or GoogleMapsPlaceMapper()
        self._cache: list[tuple[POI, str]] | None = None  # (poi, tekst do wyszukiwania)
        self._lock = asyncio.Lock()

    async def get_pois(
        self, query: str, center: Coordinates, radius_m: int
    ) -> list[POI]:
        index = await self._load()
        needle = fold(query).strip()
        result = [
            poi
            for poi, haystack in index
            if haversine_m(center, poi.location) <= radius_m
            and (not needle or needle in haystack)
        ]
        result.sort(key=lambda p: haversine_m(center, p.location))
        return result

    async def _load(self) -> list[tuple[POI, str]]:
        async with self._lock:
            if self._cache is None:
                raw_items = await asyncio.to_thread(self._read_file)
                self._cache = self._map_all(raw_items)
            return self._cache

    def _read_file(self) -> list[dict[str, Any]]:
        with self._path.open(encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, list):
            raise ValueError(f"{self._path}: oczekiwano listy obiektów JSON")
        return data

    def _map_all(self, raw_items: list[dict[str, Any]]) -> list[tuple[POI, str]]:
        seen: set[str] = set()
        out: list[tuple[POI, str]] = []
        for raw in raw_items:
            try:
                poi = self._mapper.to_poi(raw)
            except Exception:  # pojedynczy zepsuty rekord nie powinien wywalić całości
                logger.warning("Pominięto rekord %r", raw.get("placeId"), exc_info=True)
                continue
            if poi is None or poi.id in seen:
                continue
            seen.add(poi.id)
            haystack = fold(
                " ".join([poi.name, *poi.types, str(raw.get("searchString") or "")])
            )
            out.append((poi, haystack))
        logger.info("Załadowano %d POI z %d rekordów", len(out), len(raw_items))
        return out
