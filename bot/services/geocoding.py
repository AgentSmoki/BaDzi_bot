"""City search with Google → Yandex → Nominatim fallback chain.

Google Geocoding + TimeZone gives us fuzzy matching and direct IANA
timezone in one provider. When the Google call fails (auth issue,
billing problem, transient error) we drop down to Yandex Geocoder; its
response doesn't contain an IANA tz, so timezonefinder turns lat/lon
into a zone locally. If both paid providers are misconfigured we fall
back to free Nominatim — strict matching, no fuzzy, but at least the
bot keeps working while keys are sorted."""

import asyncio
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Final

import aiohttp
import structlog
from geopy.exc import GeocoderServiceError, GeocoderTimedOut, GeocoderUnavailable
from geopy.geocoders import Nominatim
from timezonefinder import TimezoneFinder

from bot.config import get_settings

logger = structlog.get_logger(__name__)

TIMEOUT_S: Final = 10
MIN_QUERY_LEN: Final = 2

GOOGLE_GEOCODE_URL: Final = "https://maps.googleapis.com/maps/api/geocode/json"
GOOGLE_TIMEZONE_URL: Final = "https://maps.googleapis.com/maps/api/timezone/json"
YANDEX_GEOCODE_URL: Final = "https://geocode-maps.yandex.ru/1.x/"
NOMINATIM_USER_AGENT: Final = "BaDzi-Bot/1.0"

_tf = TimezoneFinder()
_nominatim = Nominatim(user_agent=NOMINATIM_USER_AGENT, timeout=TIMEOUT_S)


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
        return f"{parts[0]}, {parts[1]}"

    def to_dict(self) -> dict[str, str | float]:
        return asdict(self)


async def search_cities(name: str, limit: int = 3) -> list[CityCandidate]:
    query = name.strip()
    if len(query) < MIN_QUERY_LEN:
        return []

    candidates = await _search_google(query, limit)
    if not candidates:
        logger.info("geocoding.fallback_to_yandex", query=query)
        candidates = await _search_yandex(query, limit)
    if not candidates:
        logger.info("geocoding.fallback_to_nominatim", query=query)
        candidates = await _search_nominatim(query, limit)

    return _dedupe(candidates)[:limit]


def _dedupe(candidates: list[CityCandidate]) -> list[CityCandidate]:
    """Both geocoders sometimes return near-identical hits — collapse by
    coordinates rounded to ~100 metres so the user sees three distinct
    options instead of three identical buttons."""
    seen: set[tuple[float, float]] = set()
    out: list[CityCandidate] = []
    for cand in candidates:
        key = (round(cand.latitude, 3), round(cand.longitude, 3))
        if key in seen:
            continue
        seen.add(key)
        out.append(cand)
    return out


def _resolve_tz(lat: float, lng: float) -> str | None:
    tz = _tf.timezone_at(lat=lat, lng=lng)
    return tz if isinstance(tz, str) else None


# ── Google ───────────────────────────────────────────────────────────────────


async def _search_google(query: str, limit: int) -> list[CityCandidate]:
    settings = get_settings()
    if settings.google_geocoder_api_key is None:
        return []
    api_key = settings.google_geocoder_api_key.get_secret_value()
    if not api_key:
        return []

    timeout = aiohttp.ClientTimeout(total=TIMEOUT_S)
    try:
        async with aiohttp.ClientSession(timeout=timeout) as session:
            data = await _google_geocode_request(session, query, api_key)
            if data is None:
                return []
            results = data.get("results") or []
            candidates: list[CityCandidate] = []
            for result in results[: limit * 2]:  # over-fetch for dedup
                location = result.get("geometry", {}).get("location") or {}
                lat, lng = location.get("lat"), location.get("lng")
                if lat is None or lng is None:
                    continue
                tz = await _google_timezone(session, float(lat), float(lng), api_key)
                if tz is None:
                    tz = _resolve_tz(float(lat), float(lng))
                if tz is None:
                    continue
                candidates.append(
                    CityCandidate(
                        display_name=result.get("formatted_address") or query,
                        latitude=float(lat),
                        longitude=float(lng),
                        timezone=tz,
                    )
                )
            return candidates
    except (aiohttp.ClientError, TimeoutError) as exc:
        logger.warning("geocoding.google_network", query=query, error=str(exc))
        return []


async def _google_geocode_request(
    session: aiohttp.ClientSession, query: str, api_key: str
) -> dict[str, Any] | None:
    params = {"address": query, "language": "ru", "key": api_key}
    async with session.get(GOOGLE_GEOCODE_URL, params=params) as resp:
        data: dict[str, Any] = await resp.json()
    status = data.get("status")
    if status == "OK":
        return data
    if status == "ZERO_RESULTS":
        return data
    logger.warning(
        "geocoding.google_status",
        query=query,
        status=status,
        error_message=data.get("error_message"),
    )
    return None


async def _google_timezone(
    session: aiohttp.ClientSession, lat: float, lng: float, api_key: str
) -> str | None:
    params = {
        "location": f"{lat},{lng}",
        "timestamp": str(int(datetime.now().timestamp())),
        "key": api_key,
    }
    try:
        async with session.get(GOOGLE_TIMEZONE_URL, params=params) as resp:
            data: dict[str, Any] = await resp.json()
        if data.get("status") == "OK":
            tz_id = data.get("timeZoneId")
            if isinstance(tz_id, str):
                return tz_id
        return None
    except (aiohttp.ClientError, TimeoutError) as exc:
        logger.warning("geocoding.google_tz_network", error=str(exc))
        return None


# ── Yandex ───────────────────────────────────────────────────────────────────


async def _search_yandex(query: str, limit: int) -> list[CityCandidate]:
    settings = get_settings()
    if settings.yandex_geocoder_api_key is None:
        return []
    api_key = settings.yandex_geocoder_api_key.get_secret_value()
    if not api_key:
        return []

    timeout = aiohttp.ClientTimeout(total=TIMEOUT_S)
    params = {
        "apikey": api_key,
        "geocode": query,
        "lang": "ru_RU",
        "format": "json",
        "results": str(limit * 2),
    }
    # Yandex's HTTP Geocoder rejects requests without a Referer header —
    # even when the key has no referrer whitelist set in the dashboard.
    # Without this header the API answers `403 Invalid api key`.
    headers = {"Referer": "https://t.me/EdoHa_Badzi_bot"}
    try:
        async with aiohttp.ClientSession(timeout=timeout, headers=headers) as session:
            async with session.get(YANDEX_GEOCODE_URL, params=params) as resp:
                if resp.status != 200:
                    logger.warning("geocoding.yandex_http", query=query, status=resp.status)
                    return []
                data: dict[str, Any] = await resp.json()
    except (aiohttp.ClientError, TimeoutError) as exc:
        logger.warning("geocoding.yandex_network", query=query, error=str(exc))
        return []

    members = data.get("response", {}).get("GeoObjectCollection", {}).get("featureMember", [])
    candidates: list[CityCandidate] = []
    for member in members:
        geo_object = member.get("GeoObject", {})
        pos = geo_object.get("Point", {}).get("pos", "")
        if not pos:
            continue
        try:
            lon_str, lat_str = pos.split()
            lat, lng = float(lat_str), float(lon_str)
        except ValueError:
            continue
        tz = _resolve_tz(lat, lng)
        if tz is None:
            continue
        meta = geo_object.get("metaDataProperty", {}).get("GeocoderMetaData", {})
        display_name = meta.get("text") or geo_object.get("name") or query
        candidates.append(
            CityCandidate(
                display_name=display_name,
                latitude=lat,
                longitude=lng,
                timezone=tz,
            )
        )
    return candidates


# ── Nominatim (last-resort fallback) ─────────────────────────────────────────


async def _search_nominatim(query: str, limit: int) -> list[CityCandidate]:
    try:
        locations = await asyncio.to_thread(
            _nominatim.geocode,
            query,
            exactly_one=False,
            limit=limit * 2,
            language="ru",
        )
    except (GeocoderTimedOut, GeocoderServiceError, GeocoderUnavailable) as exc:
        logger.warning(
            "geocoding.nominatim_error",
            query=query,
            error=str(exc),
            exc_type=type(exc).__name__,
        )
        return []

    if not locations:
        return []

    candidates: list[CityCandidate] = []
    for loc in locations:
        tz = _resolve_tz(loc.latitude, loc.longitude)
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
