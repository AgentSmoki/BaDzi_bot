"""Tests for the smart-entry FSM flow in bot.routers.birth_data (Wave 2).

handle_calc → waiting_full_text → either route to stepwise FSM (button)
or LLM-extract + route to first missing field.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Message

from ai.text_extract import ExtractedBirthData
from bot.routers import birth_data as birth_data_module
from bot.routers.birth_data import (
    handle_calc,
    handle_calc_stepwise,
    handle_full_text,
)
from bot.states import BirthDataForm


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
def fake_bot() -> MagicMock:
    bot = MagicMock()
    bot.send_message = AsyncMock(return_value=MagicMock(message_id=42))
    bot.edit_message_text = AsyncMock(side_effect=Exception("no anchor"))
    return bot


def _fake_callback() -> MagicMock:
    cb = MagicMock()
    cb.message = MagicMock(spec=Message)
    cb.message.chat = MagicMock()
    cb.message.chat.id = 9999
    cb.message.answer = AsyncMock()
    cb.answer = AsyncMock()
    return cb


def _fake_message(text: str) -> MagicMock:
    m = MagicMock()
    m.text = text
    m.chat = MagicMock()
    m.chat.id = 9999
    m.bot = MagicMock()
    m.delete = AsyncMock()
    m.answer = AsyncMock()
    return m


# ── handle_calc — smart entry ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_handle_calc_enters_waiting_full_text(
    fake_state: MagicMock, fake_bot: MagicMock
) -> None:
    cb = _fake_callback()
    await handle_calc(cb, fake_state, fake_bot)

    data = await fake_state.get_data()
    assert data["__state"] == BirthDataForm.waiting_full_text
    fake_bot.send_message.assert_awaited_once()
    cb.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_handle_calc_stepwise_drops_into_classic_fsm(
    fake_state: MagicMock, fake_bot: MagicMock
) -> None:
    """«Пошагово» button — go directly to waiting_date."""
    cb = _fake_callback()
    await handle_calc_stepwise(cb, fake_state, fake_bot)

    data = await fake_state.get_data()
    assert data["__state"] == BirthDataForm.waiting_date


# ── handle_full_text — LLM extract → route ───────────────────────────────


async def _patched_extract(monkeypatch: pytest.MonkeyPatch, ext: ExtractedBirthData) -> None:
    async def fake(_text: str) -> ExtractedBirthData:
        return ext

    monkeypatch.setattr(birth_data_module, "extract_birth_data", fake)


@pytest.mark.asyncio
async def test_complete_extract_routes_to_confirm(
    monkeypatch: pytest.MonkeyPatch, fake_state: MagicMock, fake_bot: MagicMock
) -> None:
    """All four fields filled + city already geocoded → confirm summary."""
    ext = ExtractedBirthData(
        date_iso="1988-04-27",
        time_iso="07:03",
        city="Севастополь",
        gender="male",
        has_birth_time=True,
        confidence=0.95,
        raw_text="27.04.88 Севастополь 07:03 утра мужчина",
    )
    # Pre-fill city in FSM as if a previous step had geocoded it.
    await fake_state.update_data(
        city_name="Севастополь",
        latitude=44.6166,
        longitude=33.5254,
        timezone="Europe/Simferopol",
    )
    await _patched_extract(monkeypatch, ext)

    msg = _fake_message("27.04.88 Севастополь 07:03 утра мужчина")
    await handle_full_text(msg, fake_state, fake_bot)

    data = await fake_state.get_data()
    assert data["birth_date"] == "1988-04-27"
    assert data["birth_time"] == "07:03"
    assert data["has_birth_time"] is True
    assert data["gender"] == "male"
    assert data["__state"] == BirthDataForm.confirm


@pytest.mark.asyncio
async def test_missing_city_routes_to_waiting_city(
    monkeypatch: pytest.MonkeyPatch, fake_state: MagicMock, fake_bot: MagicMock
) -> None:
    """All fields except city → ask for city; LLM-extracted name is
    surfaced as a suggestion in the prompt."""
    ext = ExtractedBirthData(
        date_iso="1988-04-27",
        time_iso="07:03",
        city="Севастополь",
        gender="male",
        has_birth_time=True,
        confidence=0.9,
        raw_text="x",
    )
    await _patched_extract(monkeypatch, ext)

    msg = _fake_message("x")
    await handle_full_text(msg, fake_state, fake_bot)

    data = await fake_state.get_data()
    assert data["__state"] == BirthDataForm.waiting_city
    sent_text = fake_bot.send_message.call_args.kwargs.get("text", "") or (
        fake_bot.send_message.call_args.args[0] if fake_bot.send_message.call_args.args else ""
    )
    # The «smart» path surfaces what the LLM read so the user can correct.
    # Implementation passes via _step with text kwarg.
    assert "Севастополь" in sent_text


@pytest.mark.asyncio
async def test_missing_gender_routes_to_waiting_gender(
    monkeypatch: pytest.MonkeyPatch, fake_state: MagicMock, fake_bot: MagicMock
) -> None:
    ext = ExtractedBirthData(
        date_iso="1988-04-27",
        time_iso="07:03",
        city="Севастополь",
        gender=None,
        has_birth_time=True,
        confidence=0.9,
        raw_text="x",
    )
    # Pretend city was already accepted upstream.
    await fake_state.update_data(
        city_name="Севастополь",
        latitude=44.6166,
        longitude=33.5254,
        timezone="Europe/Simferopol",
    )
    await _patched_extract(monkeypatch, ext)

    msg = _fake_message("x")
    await handle_full_text(msg, fake_state, fake_bot)
    data = await fake_state.get_data()
    assert data["__state"] == BirthDataForm.waiting_gender


@pytest.mark.asyncio
async def test_low_confidence_falls_back_to_date_prompt(
    monkeypatch: pytest.MonkeyPatch, fake_state: MagicMock, fake_bot: MagicMock
) -> None:
    """confidence<0.4 + nothing parseable → ask for date with the
    «не разобрала» preamble."""
    ext = ExtractedBirthData(
        date_iso=None,
        time_iso=None,
        city=None,
        gender=None,
        has_birth_time=False,
        confidence=0.0,
        raw_text="ыыыыыыы",
    )
    await _patched_extract(monkeypatch, ext)

    msg = _fake_message("ыыыыыыы")
    await handle_full_text(msg, fake_state, fake_bot)

    data = await fake_state.get_data()
    assert data["__state"] == BirthDataForm.waiting_date


@pytest.mark.asyncio
async def test_empty_text_is_noop(
    monkeypatch: pytest.MonkeyPatch, fake_state: MagicMock, fake_bot: MagicMock
) -> None:
    """Whitespace-only message → no LLM call, no state change."""
    extract_mock = AsyncMock()
    monkeypatch.setattr(birth_data_module, "extract_birth_data", extract_mock)

    msg = _fake_message("   ")
    await handle_full_text(msg, fake_state, fake_bot)

    extract_mock.assert_not_awaited()
    assert fake_state._data == {}


@pytest.mark.asyncio
async def test_explicit_no_time_skips_time_step(
    monkeypatch: pytest.MonkeyPatch, fake_state: MagicMock, fake_bot: MagicMock
) -> None:
    """High-confidence «без времени» → has_birth_time=False is staged,
    bot doesn't ask for time."""
    ext = ExtractedBirthData(
        date_iso="1990-07-15",
        time_iso=None,
        city="Москва",
        gender="female",
        has_birth_time=False,
        confidence=0.9,
        raw_text="x",
    )
    # Pretend city was geocoded.
    await fake_state.update_data(
        city_name="Москва",
        latitude=55.7558,
        longitude=37.6173,
        timezone="Europe/Moscow",
    )
    await _patched_extract(monkeypatch, ext)

    msg = _fake_message("x")
    await handle_full_text(msg, fake_state, fake_bot)

    data = await fake_state.get_data()
    assert data["has_birth_time"] is False
    # All fields satisfied → confirm
    assert data["__state"] == BirthDataForm.confirm
