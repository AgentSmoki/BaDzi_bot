"""Integration-flavored tests for the Wave 6 skill-router wiring in
``handle_question``.

These complement ``test_consultation.py`` (which stubs select_skill to
return ``default``). Here we explicitly drive the router with each
branch (clarifying / partner-request / low-confidence / legacy-path)
and verify the handler's reaction.

Like the rest of the test_bot suite, all I/O is mocked (no real LLM,
no real DB session, no Telegram bot)."""

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
from ai.skills.models import SkillSelection
from bot.routers import consultation as consultation_module
from bot.routers.consultation import handle_partner_skip, handle_question
from bot.states import ConsultationState
from calculator import calculate_chart
from calculator.models import ChartInput

# ── Fixtures (parallel to test_consultation.py but no autouse stub) ──────


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
    u.telegram_id = 545371253
    u.free_question_used = False
    return u


@pytest.fixture
def fake_chart(reference_chart_data: dict[str, Any]) -> MagicMock:
    c = MagicMock()
    c.id = _uuid.uuid4()
    c.chart_data = reference_chart_data
    c.partner_chart_id = None
    return c


@pytest.fixture
def fake_session() -> MagicMock:
    return MagicMock()


@pytest.fixture
def fake_state() -> MagicMock:
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
    m = MagicMock(spec=Message)
    m.text = "any"
    m.chat = MagicMock()
    m.chat.id = 9999
    m.bot = MagicMock()
    m.bot.send_chat_action = AsyncMock()
    m.answer = AsyncMock()
    return m


def _stub_router(monkeypatch: pytest.MonkeyPatch, selection: SkillSelection) -> None:
    async def fake(**_kw: Any) -> SkillSelection:
        return selection

    monkeypatch.setattr(consultation_module, "select_skill", fake)


def _stub_continue(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    stub = AsyncMock()
    monkeypatch.setattr(consultation_module, "_continue_consultation_with_skill", stub)
    return stub


# ── Branch 1: clarifying questions ───────────────────────────────────────


@pytest.mark.asyncio
async def test_clarifying_questions_enter_collecting_state(
    monkeypatch: pytest.MonkeyPatch,
    fake_message: MagicMock,
    fake_state: MagicMock,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_chart: MagicMock,
    history_store: HistoryStore,
) -> None:
    """Router returns clarifying_questions → handler sets state to
    collecting_clarifications, stashes them in FSM data, asks first one,
    and does NOT proceed to the main LLM."""
    fake_message.text = "Голова болит"
    monkeypatch.setattr(
        consultation_module._chart_repo,
        "get_latest_by_user",
        AsyncMock(return_value=fake_chart),
    )
    _stub_router(
        monkeypatch,
        SkillSelection(
            skill="health",
            confidence=0.85,
            clarifying_questions=["Острая или хроническая?", "Чаще днём или ночью?"],
            needs_partner_chart=False,
            concept_hints=["Огонь"],
            reason="symptom needs clarification",
        ),
    )
    stub_continue = _stub_continue(monkeypatch)

    await handle_question(
        message=fake_message,
        state=fake_state,
        session=fake_session,
        user=fake_user,
        history_store=history_store,
    )

    # First clarifying question sent
    fake_message.answer.assert_awaited_once_with("Острая или хроническая?")
    # FSM state stamped
    data = await fake_state.get_data()
    assert data["__state"] == ConsultationState.collecting_clarifications
    assert data["skill"] == "health"
    assert data["clarifying_questions"] == ["Острая или хроническая?", "Чаще днём или ночью?"]
    assert data["answers"] == []
    assert data["original_question"] == "Голова болит"
    assert data["concept_hints"] == ["Огонь"]
    # Main continuation NOT called yet
    stub_continue.assert_not_awaited()


# ── Branch 2: needs_partner_chart with no partner linked ─────────────────


@pytest.mark.asyncio
async def test_needs_partner_chart_shows_button(
    monkeypatch: pytest.MonkeyPatch,
    fake_message: MagicMock,
    fake_state: MagicMock,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_chart: MagicMock,
    history_store: HistoryStore,
) -> None:
    """relationships skill flags needs_partner_chart, main chart has no
    partner linked → handler responds with the «Add partner chart»
    keyboard and stashes pending_question."""
    fake_message.text = "Подходит ли мне мой парень?"
    monkeypatch.setattr(
        consultation_module._chart_repo,
        "get_latest_by_user",
        AsyncMock(return_value=fake_chart),
    )
    # 1.17.11 — `_partner_kb_for_user` lists user's other charts to offer
    # them as candidates. With no others, kb falls back to add/skip.
    monkeypatch.setattr(
        consultation_module._chart_repo,
        "list_unique_by_user",
        AsyncMock(return_value=[fake_chart]),
    )
    _stub_router(
        monkeypatch,
        SkillSelection(
            skill="relationships",
            confidence=0.93,
            clarifying_questions=[],
            needs_partner_chart=True,
            concept_hints=["夫妻宫"],
            reason="specific partner mentioned",
        ),
    )
    stub_continue = _stub_continue(monkeypatch)

    await handle_question(
        message=fake_message,
        state=fake_state,
        session=fake_session,
        user=fake_user,
        history_store=history_store,
    )

    # Message sent with the partner-button keyboard
    fake_message.answer.assert_awaited_once()
    kwargs = fake_message.answer.call_args.kwargs
    kb = kwargs.get("reply_markup")
    assert kb is not None
    # Walk inline_keyboard for a partner:add callback
    callbacks = {btn.callback_data for row in kb.inline_keyboard for btn in row}
    assert "partner:add" in callbacks
    assert "partner:skip" in callbacks

    # FSM data carries the pending question + skill + hints
    data = await fake_state.get_data()
    assert data["pending_question"] == "Подходит ли мне мой парень?"
    assert data["pending_skill"] == "relationships"
    assert data["pending_concept_hints"] == ["夫妻宫"]

    # Main LLM call not invoked
    stub_continue.assert_not_awaited()


# ── Branch 3: low-confidence downgrades to default ───────────────────────


@pytest.mark.asyncio
async def test_low_confidence_downgrades_to_default(
    monkeypatch: pytest.MonkeyPatch,
    fake_message: MagicMock,
    fake_state: MagicMock,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_chart: MagicMock,
    history_store: HistoryStore,
) -> None:
    """confidence=0.2 < _SKILL_ROUTER_CONFIDENCE_FLOOR (0.4) → skill
    forced to 'default' regardless of what the router suggested."""
    fake_message.text = "Что мне делать?"
    monkeypatch.setattr(
        consultation_module._chart_repo,
        "get_latest_by_user",
        AsyncMock(return_value=fake_chart),
    )
    _stub_router(
        monkeypatch,
        SkillSelection(
            skill="work",
            confidence=0.2,  # below floor
            clarifying_questions=[],
            needs_partner_chart=False,
            concept_hints=[],
            reason="weak guess",
        ),
    )
    stub_continue = _stub_continue(monkeypatch)

    await handle_question(
        message=fake_message,
        state=fake_state,
        session=fake_session,
        user=fake_user,
        history_store=history_store,
    )

    # Continuation called with skill_spec.name == "default", not "work"
    stub_continue.assert_awaited_once()
    skill_spec = stub_continue.await_args.kwargs["skill_spec"]
    assert skill_spec is not None
    assert skill_spec.name == "default"


# ── Branch 4: feature-flag off → legacy path (no select_skill) ───────────


@pytest.mark.asyncio
async def test_feature_flag_off_uses_legacy_path(
    monkeypatch: pytest.MonkeyPatch,
    fake_message: MagicMock,
    fake_state: MagicMock,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_chart: MagicMock,
    history_store: HistoryStore,
) -> None:
    """skill_router_enabled=False → select_skill is never called; the
    handler goes straight to _continue with skill_spec=None."""
    fake_message.text = "Расскажи"
    monkeypatch.setattr(
        consultation_module._chart_repo,
        "get_latest_by_user",
        AsyncMock(return_value=fake_chart),
    )

    settings_obj = consultation_module.get_settings()
    monkeypatch.setattr(settings_obj, "skill_router_enabled", False)

    select_skill_mock = AsyncMock()
    monkeypatch.setattr(consultation_module, "select_skill", select_skill_mock)
    stub_continue = _stub_continue(monkeypatch)

    await handle_question(
        message=fake_message,
        state=fake_state,
        session=fake_session,
        user=fake_user,
        history_store=history_store,
    )

    select_skill_mock.assert_not_awaited()
    stub_continue.assert_awaited_once()
    assert stub_continue.await_args.kwargs["skill_spec"] is None


# ── handle_partner_skip resumes consultation without partner ─────────────


@pytest.mark.asyncio
async def test_partner_skip_resumes_without_partner_chart(
    monkeypatch: pytest.MonkeyPatch,
    fake_message: MagicMock,
    fake_state: MagicMock,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_chart: MagicMock,
    history_store: HistoryStore,
) -> None:
    """«Без неё» button → handler resumes the pending consultation with
    partner_chart=None but skill_spec still applied (so the relationships
    skill answers in generic mode)."""
    monkeypatch.setattr(
        consultation_module._chart_repo,
        "get_by_id",
        AsyncMock(return_value=fake_chart),
    )
    monkeypatch.setattr(
        consultation_module._chart_repo,
        "get_latest_by_user",
        AsyncMock(return_value=fake_chart),
    )
    await fake_state.update_data(
        pending_question="Подходит ли мне мой парень?",
        pending_skill="relationships",
        pending_concept_hints=["夫妻宫"],
        chart_id=str(fake_chart.id),
    )
    stub_continue = _stub_continue(monkeypatch)

    callback = MagicMock()
    callback.message = fake_message
    callback.answer = AsyncMock()

    await handle_partner_skip(
        callback=callback,
        state=fake_state,
        session=fake_session,
        user=fake_user,
        history_store=history_store,
    )

    stub_continue.assert_awaited_once()
    kwargs = stub_continue.await_args.kwargs
    assert kwargs["original_question"] == "Подходит ли мне мой парень?"
    assert kwargs["partner_chart"] is None
    assert kwargs["skill_spec"] is not None
    assert kwargs["skill_spec"].name == "relationships"
    callback.answer.assert_awaited_once()
