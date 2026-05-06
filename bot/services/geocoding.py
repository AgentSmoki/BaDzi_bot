import asyncio
from dataclasses import asdict, dataclass
from typing import Final

import structlog
from geopy.exc import GeocoderServiceError, GeocoderTimedOut
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
        return f"{parts[0]}, {parts[-1]}"

    def to_dict(self) -> dict[str, str | float]:
        return asdict(self)


async def search_cities(name: str, limit: int = 3) -> list[CityCandidate]:
    if len(name.strip()) < MIN_QUERY_LEN:
        return []

    try:
        locations = await asyncio.to_thread(
            _geocoder.geocode,
            name,
            exactly_one=False,
            limit=limit,
            language="ru",
        )
    except (GeocoderTimedOut, GeocoderServiceError) as exc:
        logger.warning("geocoding.error", query=name, error=str(exc))
        return []

    if not locations:
        logger.info("geocoding.no_results", query=name)
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
