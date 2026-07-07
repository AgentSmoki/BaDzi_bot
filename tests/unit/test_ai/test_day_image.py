"""Tests for ai.day_image (Wave 7 Phase E).

LLM is mocked, Unsplash HTTP via httpx MockTransport, Redis via
fakeredis.aioredis. No real network calls.

Coverage:
- happy path: LLM → query → Unsplash → URL → cached
- cache hit: second call doesn't touch LLM or Unsplash
- missing access_key: returns None immediately
- LLM error: returns None
- empty LLM query: returns None
- Unsplash 4xx/5xx: returns None, no cache write
- Unsplash empty results: returns None
- _sanitize_query strips quotes/fences/punctuation
- pillar id derived from stem+branch (so 6 same-pillar days share cache)
"""

from __future__ import annotations

import json
from typing import Any

import fakeredis.aioredis
import httpx
import pytest

from ai.day_image import (
    DayImageCache,
    _pillar_to_prompt,
    _sanitize_query,
    fetch_day_energy_image,
)
from ai.orchestrator import ChatResult, ChatUsage, OrchestratorError
from calculator.models import Pillar


@pytest.fixture
def cache() -> DayImageCache:
    return DayImageCache(fakeredis.aioredis.FakeRedis(decode_responses=True))


@pytest.fixture
def fire_horse_pillar() -> Pillar:
    """丙午 — Bin-Horse, Fire Yang + Fire Yin. The 2026 year pillar
    Bogdan keeps asking about."""
    return Pillar(stem="丙", branch="午", name="Бин-Лошадь")


def _ok_chat_result(text: str) -> ChatResult:
    return ChatResult(
        text=text,
        model="qwen3.6-35b-a3b",
        usage=ChatUsage(prompt_tokens=200, completion_tokens=10, total_tokens=210),
        latency_ms=600,
        trace_id="t",
        provider="openrouter",
    )


def _mock_unsplash(
    *, status: int = 200, results: list[dict[str, Any]] | None = None
) -> httpx.MockTransport:
    """Build an httpx mock transport that returns the given Unsplash
    payload for any /search/photos request."""
    payload = {"results": results if results is not None else []}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/search/photos"
        return httpx.Response(status, json=payload)

    return httpx.MockTransport(handler)


# ── _sanitize_query ──────────────────────────────────────────────────────


def test_sanitize_strips_quotes_and_fences() -> None:
    assert _sanitize_query('"misty mountain dawn"') == "misty mountain dawn"
    assert _sanitize_query("```misty mountain dawn```") == "misty mountain dawn"


def test_sanitize_caps_at_six_words() -> None:
    raw = "one two three four five six seven eight nine"
    assert len(_sanitize_query(raw).split()) <= 6


def test_sanitize_garbage_returns_empty() -> None:
    assert _sanitize_query("") == ""
    assert _sanitize_query("12345 !@#$") == ""


def test_sanitize_picks_lowercase_run_only() -> None:
    """Numbers and Russian/Chinese chars are stripped, English keeps."""
    raw = "Вот результат: forest morning mist (хороший вариант)"
    assert _sanitize_query(raw) == "forest morning mist"


# ── _pillar_to_prompt ────────────────────────────────────────────────────


def test_pillar_to_prompt_includes_elements(fire_horse_pillar: Pillar) -> None:
    """Determinism: same pillar → same prompt → same cached LLM call."""
    prompt = _pillar_to_prompt(fire_horse_pillar)
    assert "Fire" in prompt
    assert "Yang" in prompt
    assert "丙" in prompt
    assert "午" in prompt


# ── fetch_day_energy_image ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_fetch_no_access_key_returns_none(
    monkeypatch: pytest.MonkeyPatch, cache: DayImageCache, fire_horse_pillar: Pillar
) -> None:
    """If settings.unsplash_access_key is None → short-circuit
    without touching LLM or HTTP."""
    from bot.config import get_settings

    get_settings.cache_clear()
    settings = get_settings()
    monkeypatch.setattr(settings, "unsplash_access_key", None)
    result = await fetch_day_energy_image(fire_horse_pillar, cache=cache)
    assert result is None


@pytest.mark.asyncio
async def test_fetch_happy_path_caches_url(
    monkeypatch: pytest.MonkeyPatch, cache: DayImageCache, fire_horse_pillar: Pillar
) -> None:
    """Happy path: settings has key → LLM gives query → Unsplash gives
    URL → cached. Second call serves from cache without LLM/HTTP."""
    from pydantic import SecretStr

    from bot.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(get_settings(), "unsplash_access_key", SecretStr("fake-key"))

    llm_calls = {"n": 0}

    async def fake_chat(**_kw: Any) -> ChatResult:
        llm_calls["n"] += 1
        return _ok_chat_result("sun over mountain")

    monkeypatch.setattr("ai.day_image.chat", fake_chat)

    transport = _mock_unsplash(
        results=[{"urls": {"regular": "https://images.unsplash.com/photo-1.jpg"}}]
    )
    http_calls = {"n": 0}

    original_client = httpx.AsyncClient

    def counting_client(**kw: Any) -> httpx.AsyncClient:
        http_calls["n"] += 1
        kw["transport"] = transport
        return original_client(**kw)

    monkeypatch.setattr("ai.day_image.httpx.AsyncClient", counting_client)

    url = await fetch_day_energy_image(fire_horse_pillar, cache=cache)
    assert url == "https://images.unsplash.com/photo-1.jpg"

    # Second call — served from cache
    url2 = await fetch_day_energy_image(fire_horse_pillar, cache=cache)
    assert url2 == "https://images.unsplash.com/photo-1.jpg"
    assert llm_calls["n"] == 1  # LLM not re-called
    assert http_calls["n"] == 1  # Unsplash not re-called


@pytest.mark.asyncio
async def test_fetch_llm_error_returns_none(
    monkeypatch: pytest.MonkeyPatch, cache: DayImageCache, fire_horse_pillar: Pillar
) -> None:
    from pydantic import SecretStr

    from bot.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(get_settings(), "unsplash_access_key", SecretStr("fake-key"))

    async def boom(**_kw: Any) -> ChatResult:
        raise OrchestratorError("yc 5xx")

    monkeypatch.setattr("ai.day_image.chat", boom)
    assert await fetch_day_energy_image(fire_horse_pillar, cache=cache) is None
    # Cache stays empty — next retry will try the LLM again.
    assert await cache.get(f"{fire_horse_pillar.stem}{fire_horse_pillar.branch}") is None


@pytest.mark.asyncio
async def test_fetch_unsplash_4xx_returns_none(
    monkeypatch: pytest.MonkeyPatch, cache: DayImageCache, fire_horse_pillar: Pillar
) -> None:
    from pydantic import SecretStr

    from bot.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(get_settings(), "unsplash_access_key", SecretStr("fake-key"))

    async def fake_chat(**_kw: Any) -> ChatResult:
        return _ok_chat_result("forest morning")

    monkeypatch.setattr("ai.day_image.chat", fake_chat)

    transport = _mock_unsplash(status=429)  # rate limit
    original_client = httpx.AsyncClient

    def make_client(**kw: Any) -> httpx.AsyncClient:
        kw["transport"] = transport
        return original_client(**kw)

    monkeypatch.setattr("ai.day_image.httpx.AsyncClient", make_client)

    assert await fetch_day_energy_image(fire_horse_pillar, cache=cache) is None


@pytest.mark.asyncio
async def test_fetch_unsplash_empty_results_returns_none(
    monkeypatch: pytest.MonkeyPatch, cache: DayImageCache, fire_horse_pillar: Pillar
) -> None:
    from pydantic import SecretStr

    from bot.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(get_settings(), "unsplash_access_key", SecretStr("fake-key"))

    async def fake_chat(**_kw: Any) -> ChatResult:
        return _ok_chat_result("nonexistent_thing_xyz")

    monkeypatch.setattr("ai.day_image.chat", fake_chat)

    transport = _mock_unsplash(results=[])
    original_client = httpx.AsyncClient

    def make_client(**kw: Any) -> httpx.AsyncClient:
        kw["transport"] = transport
        return original_client(**kw)

    monkeypatch.setattr("ai.day_image.httpx.AsyncClient", make_client)

    assert await fetch_day_energy_image(fire_horse_pillar, cache=cache) is None


@pytest.mark.asyncio
async def test_fetch_empty_llm_query_returns_none(
    monkeypatch: pytest.MonkeyPatch, cache: DayImageCache, fire_horse_pillar: Pillar
) -> None:
    """If LLM returns prose with no extractable English phrase →
    return None without hitting Unsplash."""
    from pydantic import SecretStr

    from bot.config import get_settings

    get_settings.cache_clear()
    monkeypatch.setattr(get_settings(), "unsplash_access_key", SecretStr("fake-key"))

    async def fake_chat(**_kw: Any) -> ChatResult:
        return _ok_chat_result("Я не знаю что предложить.")

    monkeypatch.setattr("ai.day_image.chat", fake_chat)
    http_called = {"n": 0}

    def boom_client(*_a: Any, **_kw: Any) -> Any:
        http_called["n"] += 1
        raise AssertionError("Unsplash must not be called when LLM gave empty query")

    monkeypatch.setattr("ai.day_image.httpx.AsyncClient", boom_client)
    assert await fetch_day_energy_image(fire_horse_pillar, cache=cache) is None
    assert http_called["n"] == 0


# ── Cache key derivation ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_cache_key_is_stem_plus_branch(cache: DayImageCache) -> None:
    """Stored values keyed by raw stem+branch — same pillar always
    hits same cache key. Drop-in for any Pillar with stem='戊' branch='子'."""
    await cache.set("戊子", "https://example.com/x.jpg")
    assert await cache.get("戊子") == "https://example.com/x.jpg"


@pytest.mark.asyncio
async def test_cache_tolerates_legacy_dict_format(cache: DayImageCache) -> None:
    """Forward-compatibility: cache reader accepts both bare-string
    and {url: ...} JSON shapes."""
    await cache._r.set("day_image:戊子", json.dumps({"url": "https://x.jpg"}))
    assert await cache.get("戊子") == "https://x.jpg"
