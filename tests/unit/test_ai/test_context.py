"""Tests for ai.context (Redis-backed dialogue history).

Backed by fakeredis so no real Redis is required and tests stay
fast and parallel-safe. fakeredis implements the subset we use
(LPUSH / LTRIM / LRANGE / EXPIRE / DELETE / pipeline) faithfully.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

import fakeredis.aioredis
import pytest
import pytest_asyncio

from ai.context import HISTORY_MAX_MESSAGES, HistoryStore, _key
from ai.orchestrator import ChatMessage


@pytest_asyncio.fixture
async def store() -> AsyncIterator[HistoryStore]:
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    s = HistoryStore(client)
    try:
        yield s
    finally:
        await client.aclose()


@pytest.mark.asyncio
async def test_empty_history_returns_empty_list(store: HistoryStore) -> None:
    assert await store.get(user_id=42) == []


@pytest.mark.asyncio
async def test_append_then_get_round_trips_in_chronological_order(
    store: HistoryStore,
) -> None:
    await store.append(42, ChatMessage(role="user", content="привет"))
    await store.append(42, ChatMessage(role="assistant", content="здравствуйте"))
    await store.append(42, ChatMessage(role="user", content="как дела?"))

    history = await store.get(user_id=42)
    assert [m.content for m in history] == ["привет", "здравствуйте", "как дела?"]
    assert [m.role for m in history] == ["user", "assistant", "user"]


@pytest.mark.asyncio
async def test_history_is_isolated_per_user(store: HistoryStore) -> None:
    await store.append(1, ChatMessage(role="user", content="i am user 1"))
    await store.append(2, ChatMessage(role="user", content="i am user 2"))

    one = await store.get(user_id=1)
    two = await store.get(user_id=2)
    assert one[0].content == "i am user 1"
    assert two[0].content == "i am user 2"


@pytest.mark.asyncio
async def test_history_truncates_to_max_messages(store: HistoryStore) -> None:
    """Bounded history protects Redis memory and keeps prompt cost
    predictable. Anything past HISTORY_MAX_MESSAGES rolls off."""
    overflow = HISTORY_MAX_MESSAGES + 5
    for i in range(overflow):
        await store.append(7, ChatMessage(role="user", content=f"msg {i}"))

    history = await store.get(user_id=7)
    assert len(history) == HISTORY_MAX_MESSAGES
    # Newest 20 kept (msgs 5..24); oldest dropped
    assert history[0].content == f"msg {overflow - HISTORY_MAX_MESSAGES}"
    assert history[-1].content == f"msg {overflow - 1}"


@pytest.mark.asyncio
async def test_clear_drops_history(store: HistoryStore) -> None:
    await store.append(99, ChatMessage(role="user", content="bye"))
    assert len(await store.get(user_id=99)) == 1
    await store.clear(99)
    assert await store.get(user_id=99) == []


@pytest.mark.asyncio
async def test_get_with_explicit_limit_returns_at_most_n(store: HistoryStore) -> None:
    for i in range(10):
        await store.append(3, ChatMessage(role="user", content=f"m{i}"))
    history = await store.get(user_id=3, limit=4)
    assert len(history) == 4
    # Most-recent 4: m6, m7, m8, m9 in chronological order
    assert [m.content for m in history] == ["m6", "m7", "m8", "m9"]


@pytest.mark.asyncio
async def test_corrupt_entry_is_skipped_not_raised(store: HistoryStore) -> None:
    """A single bad JSON shouldn't break the rest of the conversation —
    a Redis nuke or schema change must degrade gracefully."""
    # Manually inject a bad entry between two good ones
    await store.append(8, ChatMessage(role="user", content="good 1"))
    await store._r.lpush(_key(8), "not valid json {")  # type: ignore[union-attr]
    await store.append(8, ChatMessage(role="user", content="good 2"))

    history = await store.get(user_id=8)
    assert [m.content for m in history] == ["good 1", "good 2"]


@pytest.mark.asyncio
async def test_ttl_is_set_on_write(store: HistoryStore) -> None:
    await store.append(11, ChatMessage(role="user", content="x"))
    ttl = await store._r.ttl(_key(11))  # type: ignore[union-attr]
    # fakeredis returns the live TTL in seconds — should be just below 24h
    assert 0 < ttl <= 24 * 60 * 60
