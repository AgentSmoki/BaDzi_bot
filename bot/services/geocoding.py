import asyncio
from dataclasses import asdict, dataclass
from typing import Final

import structlog
from geopy.exc import GeocoderServiceError, GeocoderTimedOut, GeocoderUnavailable
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder

logger = structlog.get_logger(__name__)

USER_AGENT: Final = "BaDzi-Bot/1.0"
TIMEOUT_S: Final = 10
MIN_QUERY_LEN: Final = 2

_geocoder = Nominatim(user_agent=USER_AGENT, timeout=TIMEOUT_S)
_tf = TimezoneFinder()


@dataclass(frozen=True)
class CityCandidate:
    display_name: str
    latitude: float
    longitude: float
    timezone: str

    def short_label(self) -> str:
        parts = [p.strip() for p in self.display_name.split(",")]
        if len(parts) <= 2:
            return self.display_name
        # First two parts give "city, region" — much better than "city, country"
        # for differentiating multiple matches with the same city name.
        return f"{parts[0]}, {parts[1]}"

    def to_dict(self) -> dict[str, str | float]:
        return asdict(self)


async def search_cities(name: str, limit: int = 3) -> list[CityCandidate]:
    query = name.strip()
    if len(query) < MIN_QUERY_LEN:
        return []

    # Over-fetch so dedup-by-coords still leaves us with `limit` distinct cities.
    candidates = await _search_once(query, limit * 3)
    if not candidates and len(query) > 4:
        # Typo fallback: drop last 2 chars. Helps with cases like "Волхограт"
        # → "Волхогра" → still doesn't match → "Волхогр..." progressively.
        # One retry only: more retries hammer Nominatim and rarely find the city.
        truncated = query[:-2]
        logger.info("geocoding.typo_retry", original=query, truncated=truncated)
        candidates = await _search_once(truncated, limit * 3)

    return _dedupe(candidates)[:limit]


async def _search_once(query: str, limit: int) -> list[CityCandidate]:
    try:
        locations = await asyncio.to_thread(
            _geocoder.geocode,
            query,
            exactly_one=False,
            limit=limit,
            language="ru",
        )
    except (GeocoderTimedOut, GeocoderServiceError, GeocoderUnavailable) as exc:
        logger.warning("geocoding.error", query=query, error=str(exc), exc_type=type(exc).__name__)
        return []

    if not locations:
        logger.info("geocoding.no_results", query=query)
        return []

    candidates: list[CityCandidate] = []
    for loc in locations:
        tz = _tf.timezone_at(lat=loc.latitude, lng=loc.longitude)
        if tz is None:
            continue
        candidates.append(
            CityCandidate(
                display_name=loc.address,
                latitude=loc.latitude,
                longitude=loc.longitude,
                timezone=tz,
            )
        )
    return candidates


def _dedupe(candidates: list[CityCandidate]) -> list[CityCandidate]:
    """Nominatim sometimes returns the same place twice (different OSM tags).
    Collapse by coordinates rounded to ~100 metres so the user sees three
    visually distinct options instead of three identical buttons."""
    seen: set[tuple[float, float]] = set()
    out: list[CityCandidate] = []
    for cand in candidates:
        key = (round(cand.latitude, 3), round(cand.longitude, 3))
        if key in seen:
            continue
        seen.add(key)
        out.append(cand)
    return out
