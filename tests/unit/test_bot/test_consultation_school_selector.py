"""Tests for the Wave 7 Phase 2 school-selector flow in consultation router.

Verifies:
- handle_ask_pressed now enters ``choosing_school`` state and shows the
  3-button selector instead of jumping straight to ``waiting_question``.
- handle_school_chosen persists ``chosen_school`` in FSM data and
  advances to ``waiting_question`` with a friendly per-school prompt.
- Invalid school callback values are rejected (defence against stale
  keyboards) and the user stays in selector state.
- chosen_school threads from FSM into ``_continue_consultation_with_skill``
  on the straight-through (no clarifying, no partner) path.

All I/O is mocked; no real LLM, DB, or Telegram bot.
"""

from __future__ import annotations

import uuid as _uuid
from collections.abc import AsyncIterator
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import fakeredis.aioredis
import pytest
import pytest_asyncio
from aiogram.types import CallbackQuery, Message

from ai.context import HistoryStore
from ai.skills.models import SkillSelection
from bot.routers import consultation as consultation_module
from bot.routers.consultation import (
    handle_ask_pressed,
    handle_question,
    handle_school_chosen,
)
from bot.states import ConsultationState
from calculator import calculate_chart
from calculator.models import ChartInput

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
    u.free_questions_used = 0
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
    s._state: Any = None

    async def _get_data() -> dict[str, Any]:
        return dict(s._data)

    async def _update_data(**kw: Any) -> None:
        s._data.update(kw)

    async def _set_state(state: Any) -> None:
        s._state = state

    s.get_data = _get_data
    s.update_data = _update_data
    s.set_state = _set_state
    return s


def _fake_callback(data: str) -> MagicMock:
    cb = MagicMock(spec=CallbackQuery)
    cb.data = data
    cb.message = MagicMock(spec=Message)
    cb.message.answer = AsyncMock()
    cb.message.chat = MagicMock()
    cb.message.chat.id = 9999
    cb.answer = AsyncMock()
    return cb


def _fake_message() -> MagicMock:
    m = MagicMock(spec=Message)
    m.text = "any"
    m.chat = MagicMock()
    m.chat.id = 9999
    m.bot = MagicMock()
    m.bot.send_chat_action = AsyncMock()
    m.answer = AsyncMock()
    return m


# ── handle_ask_pressed → school selector ─────────────────────────────────


@pytest.mark.asyncio
async def test_handle_ask_pressed_enters_choosing_school_state(
    monkeypatch: pytest.MonkeyPatch,
    fake_state: MagicMock,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_chart: MagicMock,
) -> None:
    """After «Задать вопрос» the user must land in choosing_school with
    the 3-button selector — not jump straight to waiting_question."""
    monkeypatch.setattr(
        consultation_module,
        "_resolve_active_chart",
        AsyncMock(return_value=fake_chart),
    )
    cb = _fake_callback("menu:ask")
    await handle_ask_pressed(callback=cb, state=fake_state, session=fake_session, user=fake_user)

    assert fake_state._state == ConsultationState.choosing_school
    assert fake_state._data.get("chart_id") == str(fake_chart.id)
    # One prompt sent with the selector kb attached
    assert cb.message.answer.await_count == 1
    call = cb.message.answer.await_args
    assert "школу" in call.args[0].lower()
    # Selector keyboard has 3 buttons school:classic / edoha / modern
    kb = call.kwargs["reply_markup"]
    flat_callbacks = [btn.callback_data for row in kb.inline_keyboard for btn in row]
    assert set(flat_callbacks) == {"school:classic", "school:edoha", "school:modern"}


# ── handle_school_chosen ─────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("school", ["classic", "edoha", "modern"])
async def test_handle_school_chosen_persists_school_and_advances(
    fake_state: MagicMock, school: str
) -> None:
    """Each valid school callback persists chosen_school in FSM data and
    moves the user to waiting_question with a per-school confirmation."""
    cb = _fake_callback(f"school:{school}")
    await handle_school_chosen(callback=cb, state=fake_state)

    assert fake_state._data.get("chosen_school") == school
    assert fake_state._state == ConsultationState.waiting_question
    # Friendly confirmation sent + callback acknowledged
    assert cb.message.answer.await_count == 1
    assert cb.answer.await_count == 1


@pytest.mark.asyncio
async def test_handle_school_chosen_invalid_value_keeps_selector(
    fake_state: MagicMock,
) -> None:
    """Stale callbacks (renamed/removed buttons) shouldn't crash or
    silently advance the state — we ack with an alert and stay put."""
    fake_state._state = ConsultationState.choosing_school
    cb = _fake_callback("school:bogus")
    await handle_school_chosen(callback=cb, state=fake_state)

    assert "chosen_school" not in fake_state._data
    # State unchanged — still in selector
    assert fake_state._state == ConsultationState.choosing_school
    # Callback was answered (avoids «query timeout») but no new prompt
    assert cb.answer.await_count == 1
    cb.message.answer.assert_not_called()


# ── End-to-end: school threads through handle_question ───────────────────


@pytest.mark.asyncio
async def test_handle_question_threads_chosen_school_to_continue(
    monkeypatch: pytest.MonkeyPatch,
    fake_state: MagicMock,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_chart: MagicMock,
    history_store: HistoryStore,
) -> None:
    """User picked «edoha» → handle_school_chosen → wrote a question.
    handle_question must read chosen_school from FSM data and pass it
    to _continue_consultation_with_skill (which feeds load_base_prompt)."""
    # Simulate FSM after handle_school_chosen
    fake_state._data["chosen_school"] = "edoha"
    fake_state._data["chart_id"] = str(fake_chart.id)
    fake_state._state = ConsultationState.waiting_question

    monkeypatch.setattr(
        consultation_module,
        "_resolve_active_chart",
        AsyncMock(return_value=fake_chart),
    )

    # Router picks a high-confidence skill so we go straight to continue
    async def fake_select(**_kw: Any) -> SkillSelection:
        return SkillSelection(
            skill="work",
            confidence=0.9,
            clarifying_questions=[],
            needs_partner_chart=False,
            concept_hints=["正官"],
            reason="happy path",
        )

    monkeypatch.setattr(consultation_module, "select_skill", fake_select)

    stub_continue = AsyncMock()
    monkeypatch.setattr(consultation_module, "_continue_consultation_with_skill", stub_continue)

    msg = _fake_message()
    msg.text = "Что у меня с карьерой?"

    await handle_question(
        message=msg,
        state=fake_state,
        session=fake_session,
        user=fake_user,
        history_store=history_store,
    )

    assert stub_continue.await_count == 1
    kw = stub_continue.await_args.kwargs
    assert kw["chosen_school"] == "edoha"
    assert kw["skill_spec"] is not None
    assert kw["original_question"] == "Что у меня с карьерой?"
