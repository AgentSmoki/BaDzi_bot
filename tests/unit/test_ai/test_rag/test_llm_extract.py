"""Tests for ai.rag.llm_extract (Phase 3.5 — LLM concept extraction).

LLM is mocked — no real Qwen3.6 calls. Redis is faked via
``fakeredis.aioredis`` so cache semantics (hit / miss / set) can be
asserted without spinning up a real Redis.

Coverage:
- happy path: LLM returns clean JSON array → concepts parsed, cached
- malformed JSON: fenced / preambled output still extracted via regex
- empty / non-list output: returns []
- LLM error: returns [], doesn't poison cache
- cache hit: no second LLM call
- empty / whitespace question: returns [] immediately, no LLM call
- max-concepts cap: list truncated to 15
"""

from __future__ import annotations

from typing import Any

import fakeredis.aioredis
import pytest

from ai.orchestrator import ChatResult, ChatUsage, OrchestratorError
from ai.rag.llm_extract import (
    ConceptCache,
    _parse_concepts,
    extract_concepts_llm,
)


@pytest.fixture
def cache() -> ConceptCache:
    return ConceptCache(fakeredis.aioredis.FakeRedis(decode_responses=True))


def _ok_chat_result(text: str) -> ChatResult:
    return ChatResult(
        text=text,
        model="qwen3.6-35b-a3b",
        usage=ChatUsage(prompt_tokens=400, completion_tokens=80, total_tokens=480),
        latency_ms=900,
        trace_id="test-trace",
        provider="yc",
    )


# ── _parse_concepts ──────────────────────────────────────────────────────


def test_parse_plain_json_array() -> None:
    assert _parse_concepts('["七殺", "正官"]') == ["七殺", "正官"]


def test_parse_fenced_json() -> None:
    raw = 'Конечно, вот концепты:\n```json\n["桃花", "六合"]\n```'
    assert _parse_concepts(raw) == ["桃花", "六合"]


def test_parse_preambled_array() -> None:
    raw = 'Вот результат: ["六冲", "三刑"] — больше ничего не извлеклось.'
    assert _parse_concepts(raw) == ["六冲", "三刑"]


def test_parse_empty_array() -> None:
    assert _parse_concepts("[]") == []


def test_parse_strips_whitespace_and_drops_empty() -> None:
    assert _parse_concepts('["  正官  ", "", "  ", "七殺"]') == ["正官", "七殺"]


def test_parse_non_string_items_dropped() -> None:
    assert _parse_concepts('["正官", 42, null, "七殺"]') == ["正官", "七殺"]


def test_parse_garbage_returns_empty() -> None:
    assert _parse_concepts("Я не могу извлечь концепты") == []


def test_parse_object_wrapper_still_extracts_inner_array() -> None:
    """If the LLM disobeys and wraps the array in an object, the regex
    still rescues the inner array — better than dropping the answer."""
    assert _parse_concepts('{"concepts": ["七殺"]}') == ["七殺"]


def test_parse_scalar_returns_empty() -> None:
    """Plain string / number with no array anywhere — empty list."""
    assert _parse_concepts('"七殺"') == []
    assert _parse_concepts("42") == []


# ── extract_concepts_llm — LLM mocked ────────────────────────────────────


@pytest.mark.asyncio
async def test_extract_happy_path_caches_result(
    monkeypatch: pytest.MonkeyPatch, cache: ConceptCache
) -> None:
    """First call hits LLM and stores in cache; second call uses cache,
    so the LLM is invoked exactly once."""
    calls: list[dict[str, Any]] = []

    async def fake_chat(**kwargs: Any) -> ChatResult:
        calls.append(kwargs)
        return _ok_chat_result('["七殺", "正官", "桃花"]')

    monkeypatch.setattr("ai.rag.llm_extract.chat", fake_chat)

    a = await extract_concepts_llm("Когда мне сменить работу?", cache=cache)
    b = await extract_concepts_llm("Когда мне сменить работу?", cache=cache)

    assert a == ["七殺", "正官", "桃花"]
    assert a == b
    assert len(calls) == 1  # second call served from cache


@pytest.mark.asyncio
async def test_extract_empty_question_returns_empty_no_llm_call(
    monkeypatch: pytest.MonkeyPatch, cache: ConceptCache
) -> None:
    called = {"n": 0}

    async def fake_chat(**_kw: Any) -> ChatResult:
        called["n"] += 1
        return _ok_chat_result("[]")

    monkeypatch.setattr("ai.rag.llm_extract.chat", fake_chat)
    assert await extract_concepts_llm("", cache=cache) == []
    assert await extract_concepts_llm("   \t\n  ", cache=cache) == []
    assert called["n"] == 0  # short-circuited, never hit the LLM


@pytest.mark.asyncio
async def test_extract_upstream_error_returns_empty_no_cache_write(
    monkeypatch: pytest.MonkeyPatch, cache: ConceptCache
) -> None:
    """An OrchestratorError must not crash the caller; cache stays
    pristine so the next retry can succeed once the upstream recovers."""

    async def fake_chat(**_kw: Any) -> ChatResult:
        raise OrchestratorError("fake 5xx")

    monkeypatch.setattr("ai.rag.llm_extract.chat", fake_chat)
    result = await extract_concepts_llm("Что у меня с карьерой?", cache=cache)
    assert result == []
    # Cache must still be empty — the next call would still try the LLM.
    assert await cache.get("Что у меня с карьерой?") is None


@pytest.mark.asyncio
async def test_extract_caps_at_15_concepts(
    monkeypatch: pytest.MonkeyPatch, cache: ConceptCache
) -> None:
    """Even if the LLM dumps a huge array, the cap protects Cypher join
    from going quadratic on the related_concepts UNWIND."""
    huge = "[" + ", ".join(f'"concept_{i}"' for i in range(50)) + "]"

    async def fake_chat(**_kw: Any) -> ChatResult:
        return _ok_chat_result(huge)

    monkeypatch.setattr("ai.rag.llm_extract.chat", fake_chat)
    result = await extract_concepts_llm("x", cache=cache)
    assert len(result) == 15
    assert result[0] == "concept_0"
    assert result[14] == "concept_14"


@pytest.mark.asyncio
async def test_extract_question_normalised_for_cache_key(
    monkeypatch: pytest.MonkeyPatch, cache: ConceptCache
) -> None:
    """The cache key derives from sha256(lower(trim(question))), so
    different whitespace/casing of the same question share the entry."""
    calls = {"n": 0}

    async def fake_chat(**_kw: Any) -> ChatResult:
        calls["n"] += 1
        return _ok_chat_result('["六冲"]')

    monkeypatch.setattr("ai.rag.llm_extract.chat", fake_chat)
    await extract_concepts_llm("Опасный месяц 2026?", cache=cache)
    await extract_concepts_llm("  опасный МЕСЯЦ 2026?  ", cache=cache)
    assert calls["n"] == 1


@pytest.mark.asyncio
async def test_extract_garbage_llm_output_returns_empty_but_caches(
    monkeypatch: pytest.MonkeyPatch, cache: ConceptCache
) -> None:
    """If the LLM returns prose instead of JSON, we return [] AND cache
    [] — so the next identical question doesn't burn another LLM call
    chasing an unparseable answer."""
    calls = {"n": 0}

    async def fake_chat(**_kw: Any) -> ChatResult:
        calls["n"] += 1
        return _ok_chat_result("Не могу извлечь, простите.")

    monkeypatch.setattr("ai.rag.llm_extract.chat", fake_chat)
    result = await extract_concepts_llm("x", cache=cache)
    assert result == []
    again = await extract_concepts_llm("x", cache=cache)
    assert again == []
    assert calls["n"] == 1  # second call served from cache (empty list)
