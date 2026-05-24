"""Wave 7 Phase E — Unsplash «hero image» для дневного прогноза.

Берёт столп дня (например ``丙午`` — Бин-Лошадь, Огонь Ян), просит
Qwen3.6 fast tier придумать 2-4 английских слова описывающих природный
образ соответствующих энергий, отправляет запрос в Unsplash Search API,
возвращает URL первой landscape-фотографии.

Двойной safety net:

1. **Redis cache** по ``stem+branch`` (60 вариантов столпа) TTL 24h.
   Один и тот же столп = один и тот же образ для всех юзеров за день;
   60 столбов × 1 LLM-вызов × 1 Unsplash-вызов = максимум 60 запросов
   к каждому upstream в сутки даже на большой клиентской базе.
2. **Graceful None** на любой ошибке (Unsplash 429/down, LLM failure,
   missing access_key) — caller (scheduler) пропускает картинку и
   отправляет только текст прогноза. Картинка — украшение, не контракт.

Settings:
- ``settings.unsplash_access_key`` (опц.) — если не задан, функция
  возвращает ``None`` без вызовов вообще.
- ``settings.yc_fast_model`` + ``yc_fast_max_tokens`` — тот же tier
  что skill_router и concept extractor.
"""

from __future__ import annotations

import json
import re
from typing import Final

import httpx
import redis.asyncio as redis_async
import structlog

from ai.orchestrator import ChatMessage, OrchestratorError, chat
from bot.config import get_settings
from calculator.models import Pillar
from calculator.structures_tables import (
    BRANCH_ELEMENT,
    STEM_ELEMENT,
    STEM_POLARITY,
)

logger = structlog.get_logger(__name__)


_CACHE_KEY_PREFIX: Final = "day_image:"
_CACHE_TTL_SECONDS: Final = 24 * 60 * 60
_UNSPLASH_SEARCH_URL: Final = "https://api.unsplash.com/search/photos"
_UNSPLASH_TIMEOUT_SECONDS: Final = 8.0

_ELEMENT_RU: Final[dict[str, str]] = {
    "木": "Wood",
    "火": "Fire",
    "土": "Earth",
    "金": "Metal",
    "水": "Water",
}

_QUERY_RE: Final = re.compile(r"[a-z][a-z\s]*[a-z]", re.IGNORECASE)


_SYSTEM_PROMPT: Final = (
    "Ты подбираешь природный образ для дня по китайскому столпу Ба Цзы.\n"
    "Получаешь стихии столпа дня (ствол + ветвь, Ян/Инь).\n"
    "Возвращаешь СТРОГО 2-4 английских слова — search query для Unsplash,\n"
    "описывающий природный пейзаж или природное явление этих энергий.\n\n"
    "Правила:\n"
    "- Только английские слова, без китайских иероглифов и цифр.\n"
    "- Только природные образы: пейзаж, погода, элементы, флора, фауна.\n"
    "- НЕ люди, НЕ городские сцены, НЕ символы, НЕ абстракция.\n"
    "- Стиль: спокойный, медитативный.\n\n"
    "Примеры:\n"
    "Stem Wood Yang + Branch Wood Yin → forest morning mist\n"
    "Stem Fire Yang + Branch Fire Yin → sun over mountain\n"
    "Stem Earth Yang + Branch Water Yang → misty mountain dawn\n"
    "Stem Metal Yin + Branch Metal Yin → silver birch winter\n"
    "Stem Water Yin + Branch Water Yin → gentle rain leaves"
)


class DayImageCache:
    """Redis wrapper: ``stem+branch`` → image URL. Connection pool
    shared with the rest of the bot via ``redis_url`` from settings."""

    def __init__(self, client: redis_async.Redis) -> None:
        self._r = client

    @classmethod
    def from_settings(cls) -> DayImageCache:
        settings = get_settings()
        client: redis_async.Redis = redis_async.from_url(  # type: ignore[no-untyped-call]
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        return cls(client)

    @staticmethod
    def _key(pillar_id: str) -> str:
        return f"{_CACHE_KEY_PREFIX}{pillar_id}"

    async def get(self, pillar_id: str) -> str | None:
        try:
            raw = await self._r.get(self._key(pillar_id))
        except Exception as exc:
            logger.warning("day_image.cache_get_failed", error=str(exc))
            return None
        if not raw:
            return None
        # Store JSON to tolerate future shape extension (e.g. {url, alt}).
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, dict) and isinstance(value.get("url"), str):
            return str(value["url"])
        return None

    async def set(self, pillar_id: str, url: str) -> None:
        try:
            await self._r.set(
                self._key(pillar_id),
                json.dumps(url, ensure_ascii=False),
                ex=_CACHE_TTL_SECONDS,
            )
        except Exception as exc:
            logger.warning("day_image.cache_set_failed", error=str(exc))

    async def aclose(self) -> None:
        await self._r.aclose()


_global_cache: DayImageCache | None = None


def _get_global_cache() -> DayImageCache:
    global _global_cache
    if _global_cache is None:
        _global_cache = DayImageCache.from_settings()
    return _global_cache


async def close_day_image_cache() -> None:
    """Shutdown hook for ``bot.main._shutdown``."""
    global _global_cache
    if _global_cache is not None:
        await _global_cache.aclose()
        _global_cache = None


def _pillar_to_prompt(pillar: Pillar) -> str:
    """Render a pillar as a deterministic English description for the
    LLM — keeps the cached LLM queries stable per (stem, branch)."""
    stem_element = _ELEMENT_RU[STEM_ELEMENT[pillar.stem]]
    stem_polarity = STEM_POLARITY[pillar.stem].capitalize()
    branch_element = _ELEMENT_RU[BRANCH_ELEMENT[pillar.branch]]
    return (
        f"Stem {stem_element} {stem_polarity} ({pillar.stem}) + "
        f"Branch {branch_element} ({pillar.branch})"
    )


def _sanitize_query(raw: str) -> str:
    """Pull a clean 2-4 word English phrase out of the LLM response.
    Strips quotes, fences, trailing punctuation, extra prose."""
    # Take the longest contiguous lowercase letters+spaces run.
    candidates = _QUERY_RE.findall(raw.lower())
    if not candidates:
        return ""
    best = max(candidates, key=len).strip()
    # Trim to ≤6 words so we don't ship a sentence to Unsplash.
    words = best.split()
    return " ".join(words[:6]) if words else ""


async def _llm_query_for_pillar(pillar: Pillar) -> str:
    """Ask the fast LLM for a search query. ``""`` on any failure.

    YC ``/v1/chat/completions`` requires the full
    ``gpt://<folder>/<short>/latest`` URI — short model names give
    400 «Failed to parse model URI» (Wave 6 Phase 7 regression,
    same fix as ai.skill_router uses)."""
    settings = get_settings()
    user_msg = _pillar_to_prompt(pillar)
    model_uri = f"gpt://{settings.yc_ai_folder_id}/{settings.yc_fast_model}/latest"
    try:
        result = await chat(
            provider="yc",
            model=model_uri,
            messages=[
                ChatMessage(role="system", content=_SYSTEM_PROMPT),
                ChatMessage(role="user", content=user_msg),
            ],
            temperature=0.4,
            max_tokens=settings.yc_fast_max_tokens,
        )
    except OrchestratorError as exc:
        logger.warning("day_image.llm_failed", error=str(exc))
        return ""
    return _sanitize_query(result.text)


async def _unsplash_search(query: str, access_key: str) -> str | None:
    """Hit Unsplash /search/photos and return the first landscape URL.

    ``orientation=landscape`` matches Telegram's preferred preview aspect.
    On any HTTP error or empty results — returns ``None``.
    """
    try:
        async with httpx.AsyncClient(timeout=_UNSPLASH_TIMEOUT_SECONDS) as client:
            response = await client.get(
                _UNSPLASH_SEARCH_URL,
                params={
                    "query": query,
                    "orientation": "landscape",
                    "per_page": 1,
                    "content_filter": "high",
                },
                headers={"Authorization": f"Client-ID {access_key}"},
            )
    except httpx.HTTPError as exc:
        logger.warning("day_image.unsplash_network_failed", query=query, error=str(exc))
        return None
    if response.status_code != 200:
        logger.warning(
            "day_image.unsplash_http_error",
            query=query,
            status=response.status_code,
        )
        return None
    try:
        data = response.json()
    except ValueError:
        return None
    results = data.get("results") if isinstance(data, dict) else None
    if not isinstance(results, list) or not results:
        return None
    first = results[0]
    if not isinstance(first, dict):
        return None
    urls = first.get("urls")
    if not isinstance(urls, dict):
        return None
    # Prefer ``regular`` (1080px) — Telegram resamples down to 1280 max.
    url = urls.get("regular") or urls.get("small") or urls.get("full")
    return str(url) if isinstance(url, str) else None


async def fetch_day_energy_image(
    pillar: Pillar,
    *,
    cache: DayImageCache | None = None,
) -> str | None:
    """Возвращает URL природной фотографии под энергию столпа дня
    или ``None`` если что-то не сработало.

    Pipeline:
    1. Если ``settings.unsplash_access_key`` пуст → ``None`` без вызовов.
    2. Cache lookup по ``stem+branch``.
    3. LLM генерирует search query (Qwen3.6 fast, ~0.5-1s).
    4. Unsplash /search/photos с этим query.
    5. Cache write (TTL 24h) + return URL.

    Caller (scheduler.send_daily_forecast_job) использует:
    - ``url is not None`` → ``bot.send_photo(photo=url)`` + ``bot.send_message(text)``
    - ``url is None``     → только ``bot.send_message(text)`` как раньше
    """
    settings = get_settings()
    if settings.unsplash_access_key is None:
        return None
    access_key = settings.unsplash_access_key.get_secret_value()
    if not access_key:
        return None

    pillar_id = f"{pillar.stem}{pillar.branch}"
    cache = cache or _get_global_cache()
    cached = await cache.get(pillar_id)
    if cached is not None:
        return cached

    query = await _llm_query_for_pillar(pillar)
    if not query:
        return None

    url = await _unsplash_search(query, access_key)
    if url is None:
        return None

    await cache.set(pillar_id, url)
    logger.info(
        "day_image.fetched",
        pillar=pillar_id,
        query=query,
    )
    return url
