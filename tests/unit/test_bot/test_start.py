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

from ai.base_interpretation import BaseInterpretation
from bot.keyboards import chart_actions_kb, returning_user_kb
from bot.routers import start as start_module
from bot.routers.start import (
    handle_chart_interpret,
    handle_chart_open,
    handle_menu_back,
    handle_menu_pricing,
    handle_pay_stub,
)

# ── Keyboard composition ─────────────────────────────────────────────────


def _callback_data_set(markup: Any) -> set[str]:
    return {btn.callback_data for row in markup.inline_keyboard for btn in row}


def test_returning_user_kb_has_calc_only_no_pricing() -> None:
    """Main menu = «Добавить новую» + chart list. Тарифы НЕ должны
    появляться в главном меню — они только при upsell-моменте (после
    free-limit). Per-chart actions живут на самой карте."""
    kb = returning_user_kb(charts=[])
    cbs = _callback_data_set(kb)
    assert "menu:calc" in cbs
    assert "menu:pricing" not in cbs
    assert "menu:ask" not in cbs


def test_returning_user_kb_chart_list_after_calc() -> None:
    chart_id = _uuid.uuid4()
    kb = returning_user_kb(charts=[(chart_id, "Test")])
    cbs = _callback_data_set(kb)
    assert f"chart:open:{chart_id}" in cbs
    rows = kb.inline_keyboard
    assert rows[0][0].callback_data == "menu:calc"


def test_chart_actions_kb_has_interpret_ask_back_no_pricing() -> None:
    """Кнопки на карте: «Получить разбор», «Задать вопрос по карте»,
    «В меню». Тарифы намеренно скрыты — появятся при free-limit."""
    cbs = _callback_data_set(chart_actions_kb())
    assert cbs == {"chart:interpret", "menu:ask", "menu:back"}


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
    # The keyboard passed in `reply_markup` must be the pricing kb.
    # Wave 7 UX rework (2026-05-24): тарифы теперь pay:disabled:* (alert
    # «оплата подключается»). При запуске ЮКассы — заменить на pay:* активные.
    kb = fake_callback.message.answer.call_args.kwargs["reply_markup"]
    cbs = _callback_data_set(kb)
    assert "pay:disabled:monthly" in cbs
    assert "pay:disabled:annual" in cbs
    assert "pricing:skip" in cbs  # «Продолжить бесплатно» доступна всем
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


# ── handle_chart_interpret ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_chart_interpret_returns_cached_without_llm(
    monkeypatch: pytest.MonkeyPatch,
    fake_callback: MagicMock,
    fake_state: MagicMock,
    fake_user: MagicMock,
    fake_session: MagicMock,
) -> None:
    """Second click on «Получить разбор» must hit the Consultation cache,
    not the LLM. The free-tier guarantee: «1 раз бесплатно» effectively
    means «generate once, replay forever from DB»."""
    chart_id = _uuid.uuid4()
    await fake_state.update_data(chart_id=str(chart_id))
    fake_chart = MagicMock()
    fake_chart.id = chart_id
    fake_chart.chart_data = {"day_master": "丁"}
    fake_chart.name = "Богдан"
    monkeypatch.setattr(start_module._chart_repo, "get_by_id", AsyncMock(return_value=fake_chart))
    cached_consultation = MagicMock()
    cached_consultation.ai_response = "<b>1. Баланс</b>\nкэш"
    monkeypatch.setattr(
        start_module._consultation_repo,
        "get_by_chart_and_topic",
        AsyncMock(return_value=cached_consultation),
    )
    llm_mock = AsyncMock()
    monkeypatch.setattr(start_module, "generate_base_interpretation", llm_mock)

    await handle_chart_interpret(
        callback=fake_callback,
        state=fake_state,
        user=fake_user,
        session=fake_session,
    )

    # LLM never called on cache hit
    llm_mock.assert_not_awaited()
    fake_callback.message.answer.assert_awaited()
    body = fake_callback.message.answer.call_args.args[0]
    assert "кэш" in body
    fake_callback.answer.assert_awaited()


@pytest.mark.asyncio
async def test_chart_interpret_generates_and_persists_on_cache_miss(
    monkeypatch: pytest.MonkeyPatch,
    fake_callback: MagicMock,
    fake_state: MagicMock,
    fake_user: MagicMock,
    fake_session: MagicMock,
) -> None:
    """First click on «Получить разбор» → LLM call → save to Consultation
    with topic='base_interpretation' so the next click is cached."""
    chart_id = _uuid.uuid4()
    await fake_state.update_data(chart_id=str(chart_id))
    fake_chart = MagicMock()
    fake_chart.id = chart_id
    # Minimal valid ChartOutput payload — model_validate is called on it
    from datetime import datetime

    from calculator import calculate_chart
    from calculator.models import ChartInput

    real_chart = calculate_chart(
        ChartInput(
            birth_datetime=datetime(1999, 9, 12, 23, 55),
            latitude=48.78,
            longitude=44.77,
            tz_offset=4.0,
            gender="female",
        )
    )
    fake_chart.chart_data = real_chart.model_dump(mode="json")
    fake_chart.name = None
    fake_chart.birth_datetime_original = datetime(1999, 9, 12, 23, 55)
    monkeypatch.setattr(start_module._chart_repo, "get_by_id", AsyncMock(return_value=fake_chart))
    monkeypatch.setattr(
        start_module._consultation_repo,
        "get_by_chart_and_topic",
        AsyncMock(return_value=None),
    )

    fake_result = MagicMock()
    fake_result.interpretation = BaseInterpretation(
        block_1_balance="Баланс стихий",
        block_2_day_master="ДМ",
        block_3_realization="Реализация",
        block_4_partner="Партнёр",
        block_5_strengths="Сильные стороны",
        block_6_current_year="Текущий год",
    )
    fake_result.model = "moonshotai/kimi-k2.6"
    fake_result.prompt_tokens = 18000
    fake_result.completion_tokens = 1500
    fake_result.cost_usd = 0.05
    fake_result.latency_ms = 45_000
    fake_result.trace_id = "t-interpret"
    monkeypatch.setattr(
        start_module, "generate_base_interpretation", AsyncMock(return_value=fake_result)
    )
    create_mock = AsyncMock()
    monkeypatch.setattr(start_module._consultation_repo, "create", create_mock)

    await handle_chart_interpret(
        callback=fake_callback,
        state=fake_state,
        user=fake_user,
        session=fake_session,
    )

    create_mock.assert_awaited_once()
    persist_kwargs = create_mock.call_args.kwargs
    assert persist_kwargs["topic"] == "base_interpretation"
    assert persist_kwargs["chart_id"] == chart_id
    assert persist_kwargs["model_used"] == "moonshotai/kimi-k2.6"
    fake_callback.message.answer.assert_awaited()
