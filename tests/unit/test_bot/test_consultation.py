"""Unit tests for bot.routers.consultation.

Aiogram handlers are tested by calling them as plain async functions
with hand-rolled fakes for Message / CallbackQuery / FSMContext / DB
session / repos. This avoids spinning up a real Telegram bot or
sqlalchemy engine for every test."""

from __future__ import annotations

import uuid as _uuid
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import fakeredis.aioredis
import pytest
import pytest_asyncio
from aiogram.types import Message

from ai.context import HistoryStore
from ai.fallback import FallbackResult
from ai.orchestrator import ChatMessage, ChatResult, ChatUsage, UpstreamError
from ai.skills.models import SkillSelection
from bot.routers import consultation as consultation_module
from bot.routers.consultation import (
    handle_ask_pressed,
    handle_question,
    handle_reset,
)
from calculator import calculate_chart
from calculator.models import ChartInput


@pytest.fixture(autouse=True)
def _stub_master_meeting_summaries(monkeypatch: pytest.MonkeyPatch) -> None:
    """W5e-MVP (2026-05-21) — `_continue_consultation_with_skill` now
    pulls master-meeting summaries via SQLAlchemy. The MagicMock
    `fake_session` here can't execute the real query, so short-
    circuit the loader. Tests that care about the inject path test
    `_load_master_meeting_summaries` directly elsewhere."""
    stub = AsyncMock(return_value=[])
    monkeypatch.setattr(
        consultation_module,
        "_load_master_meeting_summaries",
        stub,
    )


@pytest.fixture(autouse=True)
def stub_skill_router(monkeypatch: pytest.MonkeyPatch) -> None:
    """Replace the fast LLM skill-router with a deterministic stub
    that returns `skill="default"` and no clarifying/partner side-
    effects. The existing tests focus on the post-routing flow
    (compose → chat → persist); skill-router-specific behavior is
    covered by test_consultation_skill_router.py."""

    async def fake_select_skill(**_kw: Any) -> SkillSelection:
        return SkillSelection(
            skill="default",
            confidence=0.9,
            clarifying_questions=[],
            needs_partner_chart=False,
            concept_hints=[],
            reason="autouse stub",
        )

    monkeypatch.setattr(consultation_module, "select_skill", fake_select_skill)


@pytest.fixture(autouse=True)
def stub_llm_extract(monkeypatch: pytest.MonkeyPatch) -> None:
    """Phase 3.5 (2026-05-23) — `_continue_consultation_with_skill` now
    calls `extract_concepts_llm` which talks to Redis + Qwen3.6. Stub
    it out to keep these tests focused on the compose→chat→persist
    flow without hitting either service. Tests that exercise the
    extractor live in test_llm_extract.py."""

    async def fake_llm_extract(_question: str, **_kw: Any) -> list[str]:
        return []

    monkeypatch.setattr(consultation_module, "extract_concepts_llm", fake_llm_extract)


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest_asyncio.fixture
async def history_store() -> AsyncIterator[HistoryStore]:
    client = fakeredis.aioredis.FakeRedis(decode_responses=True)
    s = HistoryStore(client)
    try:
        yield s
    finally:
        await client.aclose()


@pytest.fixture
def reference_chart_data() -> dict[str, Any]:
    """ChartOutput serialized for the JSONB column. The router calls
    ChartOutput.model_validate(chart.chart_data) — so we need the
    right shape, easiest path is to compute it for real."""
    chart = calculate_chart(
        ChartInput(
            birth_datetime=datetime(1999, 9, 12, 23, 55),
            latitude=48.7894,
            longitude=44.7783,
            tz_offset=4.0,
            early_rat=False,
            gender="female",
        )
    )
    return chart.model_dump(mode="json")


@pytest.fixture
def fake_user() -> MagicMock:
    u = MagicMock()
    u.id = _uuid.uuid4()
    u.telegram_id = 1234567
    # New users haven't used their one free question yet; tests that
    # exercise the guard override this to True.
    u.free_question_used = False
    return u


@pytest.fixture
def fake_chart(reference_chart_data: dict[str, Any]) -> MagicMock:
    c = MagicMock()
    c.id = _uuid.uuid4()
    c.chart_data = reference_chart_data
    # Wave 6 — handle_question reads chart.partner_chart_id to decide
    # whether to ask for a partner chart; default to None so the stub
    # select_skill never needs it.
    c.partner_chart_id = None
    return c


@pytest.fixture
def fake_session() -> MagicMock:
    return MagicMock()


@pytest.fixture
def fake_state() -> MagicMock:
    """FSMContext with get_data/update_data/set_state stubbed."""
    s = MagicMock()
    s._data: dict[str, Any] = {}

    async def _get_data() -> dict[str, Any]:
        return dict(s._data)

    async def _update_data(**kw: Any) -> None:
        s._data.update(kw)

    async def _set_state(state: Any) -> None:
        s._data["__state"] = state

    s.get_data = _get_data
    s.update_data = _update_data
    s.set_state = _set_state
    return s


@pytest.fixture
def fake_message() -> MagicMock:
    """Spec'd to Message so `isinstance(callback.message, Message)` holds —
    handle_ask_pressed now calls message.answer (photos can't be edited
    as text), so the isinstance guard must pass."""
    m = MagicMock(spec=Message)
    m.text = ""
    m.chat = MagicMock()
    m.chat.id = 9999
    m.bot = MagicMock()
    m.bot.send_chat_action = AsyncMock()
    m.answer = AsyncMock()
    return m


@pytest.fixture
def fake_callback(fake_message: MagicMock) -> MagicMock:
    cb = MagicMock()
    cb.message = fake_message
    cb.answer = AsyncMock()
    cb.data = "menu:ask"
    return cb


# ── handle_ask_pressed ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ask_pressed_with_no_chart_shows_calc_button(
    monkeypatch: pytest.MonkeyPatch,
    fake_callback: MagicMock,
    fake_state: MagicMock,
    fake_session: MagicMock,
    fake_user: MagicMock,
) -> None:
    """User who hasn't built a chart yet should be sent to /menu:calc."""
    monkeypatch.setattr(
        consultation_module._chart_repo, "get_latest_by_user", AsyncMock(return_value=None)
    )
    await handle_ask_pressed(
        callback=fake_callback, state=fake_state, session=fake_session, user=fake_user
    )
    fake_callback.message.answer.assert_awaited()
    args, _ = fake_callback.message.answer.call_args
    assert "постройте карту" in args[0].lower()


@pytest.mark.asyncio
async def test_ask_pressed_with_chart_sets_waiting_state(
    monkeypatch: pytest.MonkeyPatch,
    fake_callback: MagicMock,
    fake_state: MagicMock,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_chart: MagicMock,
) -> None:
    monkeypatch.setattr(
        consultation_module._chart_repo,
        "get_latest_by_user",
        AsyncMock(return_value=fake_chart),
    )
    await handle_ask_pressed(
        callback=fake_callback, state=fake_state, session=fake_session, user=fake_user
    )
    state_data = await fake_state.get_data()
    assert state_data["chart_id"] == str(fake_chart.id)
    # FSMContext.set_state stores the state under "__state" in our fake
    assert "__state" in state_data
    fake_callback.message.answer.assert_awaited()


# ── handle_reset ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_reset_clears_history_and_state(
    fake_message: MagicMock,
    fake_user: MagicMock,
    history_store: HistoryStore,
    fake_state: MagicMock,
) -> None:
    await history_store.append(
        fake_user.telegram_id, ChatMessage(role="user", content="старый вопрос")
    )
    assert len(await history_store.get(fake_user.telegram_id)) == 1

    await handle_reset(
        message=fake_message,
        user=fake_user,
        history_store=history_store,
        state=fake_state,
    )

    assert await history_store.get(fake_user.telegram_id) == []
    fake_message.answer.assert_awaited_once()
    state_data = await fake_state.get_data()
    assert state_data.get("__state") is None


# ── handle_question (the heavy one) ──────────────────────────────────────


def _patched_chat(
    monkeypatch: pytest.MonkeyPatch, *, text: str = "Вы — Огонь."
) -> list[dict[str, Any]]:
    """Replace ai.fallback.chat_with_fallback inside the consultation
    module with a stub. Return the kwargs of every call so tests can
    assert on routing decisions etc."""
    seen: list[dict[str, Any]] = []

    async def stub(**kwargs: Any) -> FallbackResult:
        seen.append(kwargs)
        return FallbackResult(
            result=ChatResult(
                text=text,
                model="gpt://test-folder/qwen3.6-35b-a3b/latest",
                usage=ChatUsage(
                    prompt_tokens=18000, completion_tokens=900, total_tokens=18900, cost_usd=0.025
                ),
                latency_ms=42_000,
                trace_id="t-test",
                provider="yc",
            ),
            tier=1,
            provider="yc",
            used_fallback=False,
        )

    monkeypatch.setattr(consultation_module, "chat_with_fallback", stub)
    return seen


@pytest.mark.asyncio
async def test_question_happy_path_persists_consultation_and_history(
    monkeypatch: pytest.MonkeyPatch,
    fake_message: MagicMock,
    fake_state: MagicMock,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_chart: MagicMock,
    history_store: HistoryStore,
) -> None:
    fake_message.text = "Расскажи про мою карту"
    monkeypatch.setattr(
        consultation_module._chart_repo,
        "get_latest_by_user",
        AsyncMock(return_value=fake_chart),
    )
    create_mock = AsyncMock()
    monkeypatch.setattr(consultation_module._consultation_repo, "create", create_mock)
    mark_free_mock = AsyncMock()
    monkeypatch.setattr(consultation_module._user_repo, "mark_free_question_used", mark_free_mock)
    seen_calls = _patched_chat(monkeypatch, text="Вы — Огонь Инь.")

    await handle_question(
        message=fake_message,
        state=fake_state,
        session=fake_session,
        user=fake_user,
        history_store=history_store,
    )

    # Reply sent to the user with the bot's answer
    fake_message.answer.assert_awaited()
    answer_text = fake_message.answer.call_args.args[0]
    assert "Вы — Огонь" in answer_text

    # Consultation row written
    create_mock.assert_awaited_once()
    persist_kwargs = create_mock.call_args.kwargs
    assert persist_kwargs["user_id"] == fake_user.id
    assert persist_kwargs["chart_id"] == fake_chart.id
    assert persist_kwargs["model_used"] == "gpt://test-folder/qwen3.6-35b-a3b/latest"
    assert persist_kwargs["completion_tokens"] == 900
    assert persist_kwargs["trace_id"] == "t-test"

    # Free-question flag flipped after a successful answer (1.12.0).
    mark_free_mock.assert_awaited_once_with(fake_session, fake_user.id)

    # History contains both turns in chronological order
    history = await history_store.get(fake_user.telegram_id)
    assert [m.role for m in history] == ["user", "assistant"]
    assert history[0].content == "Расскажи про мою карту"
    assert "Вы — Огонь" in history[1].content

    # The chat call was made — and exactly once (no retries on success)
    assert len(seen_calls) == 1


@pytest.mark.asyncio
async def test_question_blocked_when_free_question_already_used(
    monkeypatch: pytest.MonkeyPatch,
    fake_message: MagicMock,
    fake_state: MagicMock,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_chart: MagicMock,
    history_store: HistoryStore,
) -> None:
    """1.12.0 guard: second question goes to pricing_kb instead of
    burning OpenRouter/YC tokens. The LLM is never called."""
    fake_user.free_question_used = True
    fake_message.text = "Второй вопрос подряд"
    monkeypatch.setattr(
        consultation_module._chart_repo,
        "get_latest_by_user",
        AsyncMock(return_value=fake_chart),
    )
    create_mock = AsyncMock()
    monkeypatch.setattr(consultation_module._consultation_repo, "create", create_mock)
    mark_free_mock = AsyncMock()
    monkeypatch.setattr(consultation_module._user_repo, "mark_free_question_used", mark_free_mock)
    seen_calls = _patched_chat(monkeypatch)

    await handle_question(
        message=fake_message,
        state=fake_state,
        session=fake_session,
        user=fake_user,
        history_store=history_store,
    )

    # User received the upsell message
    fake_message.answer.assert_awaited()
    answer_text = fake_message.answer.call_args.args[0]
    assert "тариф" in answer_text.lower()
    # Reply markup is the pricing keyboard, not the regular after-answer
    assert fake_message.answer.call_args.kwargs.get("reply_markup") is not None

    # No LLM call, no consultation row, no flag flip (already True)
    assert len(seen_calls) == 0
    create_mock.assert_not_awaited()
    mark_free_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_question_does_not_flip_flag_on_llm_failure(
    monkeypatch: pytest.MonkeyPatch,
    fake_message: MagicMock,
    fake_state: MagicMock,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_chart: MagicMock,
    history_store: HistoryStore,
) -> None:
    """If the LLM tier chain fails the user gets an apology — but their
    one free question is NOT consumed, so a retry is possible."""
    fake_message.text = "Покажи карту"
    monkeypatch.setattr(
        consultation_module._chart_repo,
        "get_latest_by_user",
        AsyncMock(return_value=fake_chart),
    )
    mark_free_mock = AsyncMock()
    monkeypatch.setattr(consultation_module._user_repo, "mark_free_question_used", mark_free_mock)

    async def boom(**_kw: Any) -> Any:
        raise UpstreamError("both tiers down")

    monkeypatch.setattr(consultation_module, "chat_with_fallback", boom)

    await handle_question(
        message=fake_message,
        state=fake_state,
        session=fake_session,
        user=fake_user,
        history_store=history_store,
    )

    # User saw the apology
    fake_message.answer.assert_awaited()
    # …but the free-question flag is untouched
    mark_free_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_question_with_temporal_keyword_includes_now_block(
    monkeypatch: pytest.MonkeyPatch,
    fake_message: MagicMock,
    fake_state: MagicMock,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_chart: MagicMock,
    history_store: HistoryStore,
) -> None:
    """Router should detect 'сейчас' → temporal context attached."""
    fake_message.text = "Что меня ждёт сейчас?"
    monkeypatch.setattr(
        consultation_module._chart_repo,
        "get_latest_by_user",
        AsyncMock(return_value=fake_chart),
    )
    monkeypatch.setattr(consultation_module._consultation_repo, "create", AsyncMock())
    monkeypatch.setattr(consultation_module._user_repo, "mark_free_question_used", AsyncMock())
    seen = _patched_chat(monkeypatch)

    await handle_question(
        message=fake_message,
        state=fake_state,
        session=fake_session,
        user=fake_user,
        history_store=history_store,
    )
    # The user message that landed in `messages` should reference the
    # current Bazi block — the orchestrator only sees text, so we check
    # the assembled messages
    messages = seen[0]["messages"]
    user_payload = messages[-1].content
    assert "Текущий момент" in user_payload


@pytest.mark.asyncio
async def test_question_llm_failure_replies_apology_and_keeps_state(
    monkeypatch: pytest.MonkeyPatch,
    fake_message: MagicMock,
    fake_state: MagicMock,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_chart: MagicMock,
    history_store: HistoryStore,
) -> None:
    """When chat_with_fallback raises, the user gets a polite Russian
    error and history is NOT polluted with a half-turn."""
    fake_message.text = "Расскажи"
    monkeypatch.setattr(
        consultation_module._chart_repo,
        "get_latest_by_user",
        AsyncMock(return_value=fake_chart),
    )
    create_mock = AsyncMock()
    monkeypatch.setattr(consultation_module._consultation_repo, "create", create_mock)

    async def boom(**_kw: Any) -> FallbackResult:
        raise UpstreamError("both providers down")

    monkeypatch.setattr(consultation_module, "chat_with_fallback", boom)

    await handle_question(
        message=fake_message,
        state=fake_state,
        session=fake_session,
        user=fake_user,
        history_store=history_store,
    )
    fake_message.answer.assert_awaited()
    answer_text = fake_message.answer.call_args.args[0]
    assert "не смогла ответить" in answer_text.lower()
    # Nothing persisted, nothing in history
    create_mock.assert_not_awaited()
    assert await history_store.get(fake_user.telegram_id) == []


@pytest.mark.asyncio
async def test_question_with_no_chart_falls_back_to_calc_prompt(
    monkeypatch: pytest.MonkeyPatch,
    fake_message: MagicMock,
    fake_state: MagicMock,
    fake_session: MagicMock,
    fake_user: MagicMock,
    history_store: HistoryStore,
) -> None:
    fake_message.text = "Расскажи"
    monkeypatch.setattr(
        consultation_module._chart_repo,
        "get_latest_by_user",
        AsyncMock(return_value=None),
    )

    await handle_question(
        message=fake_message,
        state=fake_state,
        session=fake_session,
        user=fake_user,
        history_store=history_store,
    )
    fake_message.answer.assert_awaited()
    # No history written
    assert await history_store.get(fake_user.telegram_id) == []
