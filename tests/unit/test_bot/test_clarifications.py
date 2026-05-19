"""Tests for the clarifying-questions FSM loop (Wave 6 / Phase 4).

The loop accumulates 1-3 answers in FSM data, asking the next question
after each. Once all answers are collected, control passes downstream
(Phase 6 will hook it into the consultation LLM call; Phase 4 just
posts a placeholder + clears state).

aiogram message/state are mocked — these tests cover only the FSM
mechanics (which question is asked, when state clears).
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

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


# ── Mechanics ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_first_answer_triggers_second_question(fake_state: MagicMock) -> None:
    """When 2 questions are pending and the user answers the first one,
    the handler must send the second question and keep the FSM alive."""
    await fake_state.update_data(
        clarifying_questions=["Какая сфера?", "На какой период?"],
        answers=[],
        skill="time",
        concept_hints=["大運"],
        original_question="Что меня ждёт?",
    )
    msg = _fake_message("карьера")

    await handle_clarification_answer(msg, fake_state)

    msg.answer.assert_awaited_once_with("На какой период?")
    data = await fake_state.get_data()
    assert data["answers"] == ["карьера"]
    # state remains in clarifications — no __state write
    assert data.get("__state") is None


@pytest.mark.asyncio
async def test_last_answer_clears_state_and_posts_placeholder(fake_state: MagicMock) -> None:
    """After the final answer, the handler exits clarifications by
    setting state to None and posting the placeholder message (Phase 6
    will swap this for the real continuation)."""
    await fake_state.update_data(
        clarifying_questions=["Какая сфера?", "На какой период?"],
        answers=["карьера"],
        skill="time",
        concept_hints=[],
        original_question="Что меня ждёт?",
    )
    msg = _fake_message("этот год")

    await handle_clarification_answer(msg, fake_state)

    msg.answer.assert_awaited_once()
    final_data = await fake_state.get_data()
    assert final_data["answers"] == ["карьера", "этот год"]
    assert final_data["__state"] is None  # state.set_state(None) called


@pytest.mark.asyncio
async def test_single_question_completes_in_one_turn(fake_state: MagicMock) -> None:
    """When the router gives 1 question, the very next answer finishes
    the loop — no intermediate prompt."""
    await fake_state.update_data(
        clarifying_questions=["Это острая или хроническая?"],
        answers=[],
        skill="health",
        concept_hints=[],
        original_question="Голова болит",
    )
    msg = _fake_message("хроническая")

    await handle_clarification_answer(msg, fake_state)

    msg.answer.assert_awaited_once()
    data = await fake_state.get_data()
    assert data["answers"] == ["хроническая"]
    assert data["__state"] is None


# ── Defensive edge cases ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_empty_message_text_is_ignored(fake_state: MagicMock) -> None:
    """Empty / whitespace-only text shouldn't advance the loop."""
    await fake_state.update_data(
        clarifying_questions=["Q1", "Q2"],
        answers=[],
    )
    msg = _fake_message("   ")

    await handle_clarification_answer(msg, fake_state)

    msg.answer.assert_not_awaited()
    data = await fake_state.get_data()
    assert data.get("answers") == []


@pytest.mark.asyncio
async def test_slash_command_skipped(fake_state: MagicMock) -> None:
    """``/reset`` etc. fall through to their own handlers — clarifications
    handler must not swallow them."""
    await fake_state.update_data(
        clarifying_questions=["Q1"],
        answers=[],
    )
    msg = _fake_message("/reset")

    await handle_clarification_answer(msg, fake_state)

    msg.answer.assert_not_awaited()
    data = await fake_state.get_data()
    assert data.get("answers") == []


@pytest.mark.asyncio
async def test_lost_state_exits_gracefully(fake_state: MagicMock) -> None:
    """If clarifying_questions is missing from FSM data (race / restart),
    the handler clears state instead of crashing."""
    # No clarifying_questions in data — simulating lost FSM
    msg = _fake_message("some answer")

    await handle_clarification_answer(msg, fake_state)

    msg.answer.assert_not_awaited()
    data = await fake_state.get_data()
    assert data["__state"] is None
