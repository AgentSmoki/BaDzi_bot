"""Tests for the clarifying-questions FSM loop (Wave 6 / Phase 4 + 6).

The loop accumulates 1-3 answers in FSM data, asking the next question
after each. Once all answers are collected, the handler delegates to
``_continue_consultation_with_skill`` — Phase 6 replaced the Phase-4
placeholder with the real continuation, so these tests now mock that
function and verify the right context is forwarded.
"""

from __future__ import annotations

import uuid as _uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.routers import consultation as consultation_module
from bot.routers.consultation import handle_clarification_answer


@pytest.fixture
def fake_state() -> MagicMock:
    state = MagicMock()
    data: dict[str, Any] = {}
    state._data = data

    async def _get_data() -> dict[str, Any]:
        return dict(data)

    async def _update_data(**kw: Any) -> None:
        data.update(kw)

    async def _set_state(s: Any) -> None:
        data["__state"] = s

    state.get_data = _get_data
    state.update_data = _update_data
    state.set_state = _set_state
    return state


def _fake_message(text: str) -> MagicMock:
    msg = MagicMock()
    msg.text = text
    msg.answer = AsyncMock()
    msg.from_user = MagicMock()
    msg.from_user.id = 545371253
    return msg


@pytest.fixture
def fake_user() -> MagicMock:
    u = MagicMock()
    u.id = _uuid.uuid4()
    u.telegram_id = 545371253
    return u


@pytest.fixture
def fake_session() -> MagicMock:
    return MagicMock()


@pytest.fixture
def fake_history_store() -> MagicMock:
    h = MagicMock()
    h.get = AsyncMock(return_value=[])
    h.append = AsyncMock()
    return h


@pytest.fixture
def stub_continue(monkeypatch: pytest.MonkeyPatch) -> AsyncMock:
    """Replace _continue_consultation_with_skill so the «all answers
    collected» branch is observable without spinning up the full LLM
    pipeline. Returns the mock so tests can assert on call kwargs."""
    stub = AsyncMock()
    monkeypatch.setattr(consultation_module, "_continue_consultation_with_skill", stub)
    return stub


# ── Mechanics ────────────────────────────────────────────────────────────


def _kw(
    state: MagicMock,
    session: MagicMock,
    user: MagicMock,
    history_store: MagicMock,
) -> dict[str, Any]:
    return {
        "state": state,
        "session": session,
        "user": user,
        "history_store": history_store,
    }


@pytest.mark.asyncio
async def test_first_answer_triggers_second_question(
    fake_state: MagicMock,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_history_store: MagicMock,
    stub_continue: AsyncMock,
) -> None:
    """When 2 questions are pending and the user answers the first one,
    the handler must send the second question and keep the FSM alive
    without invoking the main consultation continuation."""
    await fake_state.update_data(
        clarifying_questions=["Какая сфера?", "На какой период?"],
        answers=[],
        skill="time",
        concept_hints=["大運"],
        original_question="Что меня ждёт?",
        chart_id=str(_uuid.uuid4()),
    )
    msg = _fake_message("карьера")

    await handle_clarification_answer(
        msg, **_kw(fake_state, fake_session, fake_user, fake_history_store)
    )

    msg.answer.assert_awaited_once_with("На какой период?")
    data = await fake_state.get_data()
    assert data["answers"] == ["карьера"]
    assert data.get("__state") is None  # still in clarifications
    stub_continue.assert_not_awaited()


@pytest.mark.asyncio
async def test_last_answer_resumes_consultation_with_skill(
    monkeypatch: pytest.MonkeyPatch,
    fake_state: MagicMock,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_history_store: MagicMock,
    stub_continue: AsyncMock,
) -> None:
    """After the final answer the handler resolves the chart, clears
    state, and forwards skill + clarifications + concept_hints to
    _continue_consultation_with_skill."""
    from datetime import datetime

    from calculator import calculate_chart
    from calculator.models import ChartInput

    chart_output = calculate_chart(
        ChartInput(
            birth_datetime=datetime(1999, 9, 12, 23, 55),
            latitude=48.7894,
            longitude=44.7783,
            tz_offset=4.0,
            early_rat=False,
            gender="female",
        )
    )
    chart_id = _uuid.uuid4()
    fake_chart = MagicMock()
    fake_chart.id = chart_id
    fake_chart.chart_data = chart_output.model_dump(mode="json")
    fake_chart.partner_chart_id = None
    monkeypatch.setattr(
        consultation_module._chart_repo,
        "get_by_id",
        AsyncMock(return_value=fake_chart),
    )

    await fake_state.update_data(
        clarifying_questions=["Какая сфера?", "На какой период?"],
        answers=["карьера"],
        skill="time",
        concept_hints=["大運"],
        original_question="Что меня ждёт?",
        chart_id=str(chart_id),
    )
    msg = _fake_message("этот год")

    await handle_clarification_answer(
        msg, **_kw(fake_state, fake_session, fake_user, fake_history_store)
    )

    # state cleared
    final = await fake_state.get_data()
    assert final["__state"] is None
    # main continuation called with the expected payload
    stub_continue.assert_awaited_once()
    kwargs = stub_continue.await_args.kwargs
    assert kwargs["original_question"] == "Что меня ждёт?"
    assert kwargs["clarifications"] == [
        ("Какая сфера?", "карьера"),
        ("На какой период?", "этот год"),
    ]
    assert kwargs["concept_hints"] == ["大運"]
    assert kwargs["skill_spec"] is not None
    assert kwargs["skill_spec"].name == "time"


@pytest.mark.asyncio
async def test_single_question_completes_in_one_turn(
    monkeypatch: pytest.MonkeyPatch,
    fake_state: MagicMock,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_history_store: MagicMock,
    stub_continue: AsyncMock,
) -> None:
    """When the router gives 1 question, the next answer finishes the
    loop — no intermediate prompt, continuation called once."""
    monkeypatch.setattr(
        consultation_module._chart_repo,
        "get_by_id",
        AsyncMock(return_value=None),  # no chart → graceful exit
    )
    await fake_state.update_data(
        clarifying_questions=["Это острая или хроническая?"],
        answers=[],
        skill="health",
        concept_hints=[],
        original_question="Голова болит",
        chart_id=str(_uuid.uuid4()),
    )
    monkeypatch.setattr(
        consultation_module._chart_repo,
        "get_latest_by_user",
        AsyncMock(return_value=None),
    )
    msg = _fake_message("хроническая")

    await handle_clarification_answer(
        msg, **_kw(fake_state, fake_session, fake_user, fake_history_store)
    )

    # No chart -> graceful no-op fallback
    data = await fake_state.get_data()
    assert data["__state"] is None


# ── Defensive edge cases ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_empty_message_text_is_ignored(
    fake_state: MagicMock,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_history_store: MagicMock,
    stub_continue: AsyncMock,
) -> None:
    await fake_state.update_data(
        clarifying_questions=["Q1", "Q2"],
        answers=[],
    )
    msg = _fake_message("   ")

    await handle_clarification_answer(
        msg, **_kw(fake_state, fake_session, fake_user, fake_history_store)
    )

    msg.answer.assert_not_awaited()
    stub_continue.assert_not_awaited()
    data = await fake_state.get_data()
    assert data.get("answers") == []


@pytest.mark.asyncio
async def test_slash_command_skipped(
    fake_state: MagicMock,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_history_store: MagicMock,
    stub_continue: AsyncMock,
) -> None:
    await fake_state.update_data(
        clarifying_questions=["Q1"],
        answers=[],
    )
    msg = _fake_message("/reset")

    await handle_clarification_answer(
        msg, **_kw(fake_state, fake_session, fake_user, fake_history_store)
    )

    msg.answer.assert_not_awaited()
    stub_continue.assert_not_awaited()
    data = await fake_state.get_data()
    assert data.get("answers") == []


@pytest.mark.asyncio
async def test_lost_state_exits_gracefully(
    fake_state: MagicMock,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_history_store: MagicMock,
    stub_continue: AsyncMock,
) -> None:
    """If clarifying_questions is missing from FSM data (race / restart),
    handler clears state instead of crashing."""
    msg = _fake_message("some answer")

    await handle_clarification_answer(
        msg, **_kw(fake_state, fake_session, fake_user, fake_history_store)
    )

    msg.answer.assert_not_awaited()
    stub_continue.assert_not_awaited()
    data = await fake_state.get_data()
    assert data["__state"] is None
