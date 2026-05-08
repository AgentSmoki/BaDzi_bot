"""Unit tests for bot.routers.start — the menu/back/pricing/pay handlers
that wire the consultation router into the rest of the UI.

The deeper FSM flow (handle_start, charts_page, etc.) is covered by
integration tests; here we focus on the surface behaviour added to fix
the missing 'Задать вопрос' button.
"""

from __future__ import annotations

import uuid as _uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Message

from bot.keyboards import chart_actions_kb, returning_user_kb
from bot.routers import start as start_module
from bot.routers.start import (
    handle_chart_open,
    handle_menu_back,
    handle_menu_pricing,
    handle_pay_stub,
)

# ── Keyboard composition ─────────────────────────────────────────────────


def _callback_data_set(markup: Any) -> set[str]:
    return {btn.callback_data for row in markup.inline_keyboard for btn in row}


def test_returning_user_kb_includes_ask_pricing_and_calc() -> None:
    """The whole point of this fix: returning users see 'Задать вопрос',
    'Тарифы' and 'Добавить новую карту' before the chart list."""
    kb = returning_user_kb(charts=[])
    cbs = _callback_data_set(kb)
    assert "menu:ask" in cbs
    assert "menu:pricing" in cbs
    assert "menu:calc" in cbs


def test_returning_user_kb_lists_charts_after_actions() -> None:
    chart_id = _uuid.uuid4()
    kb = returning_user_kb(charts=[(chart_id, "Test")])
    cbs = _callback_data_set(kb)
    assert f"chart:open:{chart_id}" in cbs
    # Action buttons render as separate rows above the chart list
    rows = kb.inline_keyboard
    assert rows[0][0].callback_data == "menu:ask"


def test_chart_actions_kb_has_ask_and_back() -> None:
    cbs = _callback_data_set(chart_actions_kb())
    assert cbs == {"menu:ask", "menu:back"}


# ── Fixtures for handler tests ───────────────────────────────────────────


@pytest.fixture
def fake_state() -> MagicMock:
    s = MagicMock()
    data: dict[str, Any] = {}
    s._data = data

    async def _get_data() -> dict[str, Any]:
        return dict(data)

    async def _update_data(**kw: Any) -> None:
        data.update(kw)

    async def _set_state(state: Any) -> None:
        data["__state"] = state

    s.get_data = _get_data
    s.update_data = _update_data
    s.set_state = _set_state
    return s


@pytest.fixture
def fake_user() -> MagicMock:
    u = MagicMock()
    u.id = _uuid.uuid4()
    u.telegram_id = 1234567
    u.first_name = "Богдан"
    return u


@pytest.fixture
def fake_session() -> MagicMock:
    return MagicMock()


@pytest.fixture
def fake_message() -> MagicMock:
    """Spec'd to Message so `isinstance(callback.message, Message)` guards
    pass — aiogram uses that check to filter out InaccessibleMessage in
    inline-mode callbacks."""
    m = MagicMock(spec=Message)
    m.chat = MagicMock()
    m.chat.id = 9999
    m.answer = AsyncMock()
    m.answer_photo = AsyncMock()
    return m


@pytest.fixture
def fake_callback(fake_message: MagicMock) -> MagicMock:
    cb = MagicMock()
    cb.message = fake_message
    cb.answer = AsyncMock()
    cb.data = ""
    return cb


# ── handle_menu_back ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_menu_back_clears_state_and_renders_main_menu(
    monkeypatch: pytest.MonkeyPatch,
    fake_callback: MagicMock,
    fake_state: MagicMock,
    fake_user: MagicMock,
    fake_session: MagicMock,
) -> None:
    """`menu:back` from any context (consultation, pricing, chart photo)
    must drop the user into the returning-user main menu without any
    leftover FSM state."""
    fake_state._data["__state"] = "ConsultationState.waiting_question"
    send_main_menu_mock = AsyncMock()
    monkeypatch.setattr(start_module, "send_main_menu", send_main_menu_mock)

    await handle_menu_back(
        callback=fake_callback,
        state=fake_state,
        user=fake_user,
        session=fake_session,
    )

    # FSM cleared
    state_data = await fake_state.get_data()
    assert state_data.get("__state") is None
    # Main menu rendered with our user
    send_main_menu_mock.assert_awaited_once()
    args, kwargs = send_main_menu_mock.call_args
    assert kwargs.get("state") is fake_state
    fake_callback.answer.assert_awaited()


# ── handle_menu_pricing ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_menu_pricing_renders_stub_with_pricing_kb(
    fake_callback: MagicMock,
) -> None:
    await handle_menu_pricing(callback=fake_callback)
    fake_callback.message.answer.assert_awaited_once()
    text = fake_callback.message.answer.call_args.args[0]
    assert "Тарифы" in text
    # The keyboard passed in `reply_markup` must be the pricing kb (has pay:* buttons)
    kb = fake_callback.message.answer.call_args.kwargs["reply_markup"]
    cbs = _callback_data_set(kb)
    assert "pay:monthly" in cbs
    assert "pay:annual" in cbs
    fake_callback.answer.assert_awaited()


# ── handle_pay_stub ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pay_stub_shows_alert(fake_callback: MagicMock) -> None:
    fake_callback.data = "pay:monthly"
    await handle_pay_stub(callback=fake_callback)
    fake_callback.answer.assert_awaited_once()
    kwargs = fake_callback.answer.call_args.kwargs
    assert kwargs.get("show_alert") is True


# ── handle_chart_open: pins chart_id in FSM ──────────────────────────────


@pytest.mark.asyncio
async def test_chart_open_pins_chart_id_in_fsm(
    monkeypatch: pytest.MonkeyPatch,
    fake_callback: MagicMock,
    fake_state: MagicMock,
    fake_session: MagicMock,
) -> None:
    """Without this pin, pressing 'Задать вопрос' on an old chart silently
    routes the consultation to the latest chart instead. Regression test."""
    chart_id = _uuid.uuid4()
    fake_callback.data = f"chart:open:{chart_id}"
    fake_chart = MagicMock()
    fake_chart.id = chart_id
    fake_chart.chart_data = {"day_master": "丁", "pillars": [], "element_balance": {}}
    fake_chart.has_birth_time = True
    fake_chart.name = None
    monkeypatch.setattr(start_module._chart_repo, "get_by_id", AsyncMock(return_value=fake_chart))
    # Skip actual rendering — fail-path then send_text covers our assertions
    monkeypatch.setattr(
        start_module, "_render_chart", AsyncMock(side_effect=RuntimeError("no playwright"))
    )

    await handle_chart_open(callback=fake_callback, state=fake_state, session=fake_session)

    state_data = await fake_state.get_data()
    assert state_data["chart_id"] == str(chart_id)
    fake_callback.answer.assert_awaited()
