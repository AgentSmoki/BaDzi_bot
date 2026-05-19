"""Tests for the «Add partner chart» FSM flow (Wave 6 / Phase 3).

Covers:
- ``handle_add_partner_chart`` callback: clears FSM, stamps mode/owner/
  pending_question into state, sets BirthDataForm.waiting_date.
- ``_calculate_and_persist`` with ``mode="partner"``: invokes
  ``ChartRepository.set_partner`` after creating the partner chart.
- Default (non-partner) ``_calculate_and_persist`` keeps existing
  behavior (no partner-linking call).

aiogram bot/session/repo are all mocked. The calculator runs for real
because it's stateless and deterministic; mocking it would just
duplicate its logic in the test.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Message

from bot.routers.birth_data import (
    _calculate_and_persist,
    handle_add_partner_chart,
)
from bot.states import BirthDataForm
from db.models import Chart, User


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

    async def _clear() -> None:
        data.clear()

    state.get_data = _get_data
    state.update_data = _update_data
    state.set_state = _set_state
    state.clear = _clear
    return state


def _fake_callback() -> MagicMock:
    callback = MagicMock()
    # spec=Message so isinstance(callback.message, Message) passes — the
    # handler short-circuits to callback.answer() otherwise.
    callback.message = MagicMock(spec=Message)
    callback.message.chat = MagicMock()
    callback.message.chat.id = 42
    callback.answer = AsyncMock()
    return callback


# ── handle_add_partner_chart ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_handle_add_partner_chart_stashes_owner_and_question(
    fake_state: MagicMock,
) -> None:
    """Pressing «Add partner chart» preserves owner_chart_id and
    pending_question across the FSM reset."""
    owner_id = uuid.uuid4()
    await fake_state.update_data(
        chart_id=str(owner_id),
        pending_question="Подходит ли мне мой парень?",
    )
    callback = _fake_callback()
    bot = MagicMock()
    bot.send_message = AsyncMock(return_value=MagicMock(message_id=999))
    bot.edit_message_text = AsyncMock(side_effect=Exception("no anchor yet"))

    await handle_add_partner_chart(callback, fake_state, bot)

    data = await fake_state.get_data()
    assert data["mode"] == "partner"
    assert data["owner_chart_id"] == str(owner_id)
    assert data["pending_question"] == "Подходит ли мне мой парень?"
    assert data["__state"] == BirthDataForm.waiting_date
    callback.answer.assert_awaited_once()
    # _step sent the PARTNER prompt as a fresh message.
    assert bot.send_message.await_count == 1


@pytest.mark.asyncio
async def test_handle_add_partner_chart_no_message_no_op(fake_state: MagicMock) -> None:
    """Callback without a Message (impossible in TG but defensive) must
    not blow up — just call .answer() and exit."""
    callback = MagicMock()
    callback.message = None
    callback.answer = AsyncMock()
    bot = MagicMock()

    await handle_add_partner_chart(callback, fake_state, bot)

    callback.answer.assert_awaited_once()
    data = await fake_state.get_data()
    assert "mode" not in data  # state untouched


# ── _calculate_and_persist with mode="partner" ───────────────────────────


def _make_user() -> User:
    user = User(
        id=uuid.uuid4(),
        telegram_id=545371253,
        first_name="Bogdan",
    )
    return user


def _fsm_data(*, mode: str | None, owner_chart_id: str | None) -> dict[str, Any]:
    return {
        "birth_date": "1990-05-15",
        "birth_time": "14:30",
        "has_birth_time": True,
        "timezone": "Europe/Moscow",
        "latitude": 55.7558,
        "longitude": 37.6173,
        "gender": "female",
        "city_name": "Москва",
        "mode": mode,
        "owner_chart_id": owner_chart_id,
    }


@pytest.mark.asyncio
async def test_calculate_and_persist_partner_links_to_owner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When mode="partner", set_partner gets called with the new chart.id
    and the FSM-stashed owner_chart_id."""
    owner_id = uuid.uuid4()
    new_chart_id = uuid.uuid4()
    user = _make_user()

    fake_session = MagicMock()
    fake_session.flush = AsyncMock()
    fake_session.add = MagicMock()

    async def fake_create(*_args: Any, **kwargs: Any) -> Chart:
        chart = Chart(
            id=new_chart_id,
            user_id=user.id,
            name=kwargs.get("name"),
            birth_datetime_utc=kwargs["birth_datetime_utc"],
            birth_datetime_original=kwargs["birth_datetime_original"],
            latitude=kwargs["latitude"],
            longitude=kwargs["longitude"],
            tz_offset=kwargs["tz_offset"],
            chart_data=kwargs["chart_data"],
            has_birth_time=kwargs["has_birth_time"],
        )
        return chart

    set_partner_mock = AsyncMock()
    monkeypatch.setattr("bot.routers.birth_data._chart_repo.create", fake_create)
    monkeypatch.setattr("bot.routers.birth_data._chart_repo.set_partner", set_partner_mock)

    result = await _calculate_and_persist(
        _fsm_data(mode="partner", owner_chart_id=str(owner_id)),
        user=user,
        session=fake_session,
    )

    assert result["chart_id"] == new_chart_id
    assert result["mode"] == "partner"
    set_partner_mock.assert_awaited_once()
    kwargs = set_partner_mock.await_args.kwargs
    assert kwargs["owner_chart_id"] == owner_id
    assert kwargs["partner_chart_id"] == new_chart_id


@pytest.mark.asyncio
async def test_calculate_and_persist_normal_does_not_link_partner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Default (non-partner) flow must not touch set_partner."""
    new_chart_id = uuid.uuid4()
    user = _make_user()
    fake_session = MagicMock()

    async def fake_create(*_args: Any, **kwargs: Any) -> Chart:
        return Chart(
            id=new_chart_id,
            user_id=user.id,
            name=kwargs.get("name"),
            birth_datetime_utc=kwargs["birth_datetime_utc"],
            birth_datetime_original=kwargs["birth_datetime_original"],
            latitude=kwargs["latitude"],
            longitude=kwargs["longitude"],
            tz_offset=kwargs["tz_offset"],
            chart_data=kwargs["chart_data"],
            has_birth_time=kwargs["has_birth_time"],
        )

    set_partner_mock = AsyncMock()
    monkeypatch.setattr("bot.routers.birth_data._chart_repo.create", fake_create)
    monkeypatch.setattr("bot.routers.birth_data._chart_repo.set_partner", set_partner_mock)

    result = await _calculate_and_persist(
        _fsm_data(mode=None, owner_chart_id=None),
        user=user,
        session=fake_session,
    )

    assert result["mode"] is None
    set_partner_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_calculate_and_persist_partner_with_invalid_owner_id_is_safe(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If FSM data is corrupted (owner_chart_id is not a UUID), don't
    crash — just skip the set_partner call."""
    new_chart_id = uuid.uuid4()
    user = _make_user()
    fake_session = MagicMock()

    async def fake_create(*_args: Any, **kwargs: Any) -> Chart:
        return Chart(
            id=new_chart_id,
            user_id=user.id,
            name=kwargs.get("name"),
            birth_datetime_utc=kwargs["birth_datetime_utc"],
            birth_datetime_original=kwargs["birth_datetime_original"],
            latitude=kwargs["latitude"],
            longitude=kwargs["longitude"],
            tz_offset=kwargs["tz_offset"],
            chart_data=kwargs["chart_data"],
            has_birth_time=kwargs["has_birth_time"],
        )

    set_partner_mock = AsyncMock()
    monkeypatch.setattr("bot.routers.birth_data._chart_repo.create", fake_create)
    monkeypatch.setattr("bot.routers.birth_data._chart_repo.set_partner", set_partner_mock)

    result = await _calculate_and_persist(
        _fsm_data(mode="partner", owner_chart_id="not-a-uuid"),
        user=user,
        session=fake_session,
    )

    assert result["mode"] == "partner"
    set_partner_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_calculate_and_persist_partner_names_chart_as_partner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Partner charts get a default name «Партнёр» so they show up
    distinctly in the user's chart list."""
    captured: dict[str, Any] = {}
    user = _make_user()
    fake_session = MagicMock()

    async def fake_create(*_args: Any, **kwargs: Any) -> Chart:
        captured.update(kwargs)
        return Chart(
            id=uuid.uuid4(),
            user_id=user.id,
            name=kwargs.get("name"),
            birth_datetime_utc=kwargs["birth_datetime_utc"],
            birth_datetime_original=kwargs["birth_datetime_original"],
            latitude=kwargs["latitude"],
            longitude=kwargs["longitude"],
            tz_offset=kwargs["tz_offset"],
            chart_data=kwargs["chart_data"],
            has_birth_time=kwargs["has_birth_time"],
        )

    monkeypatch.setattr("bot.routers.birth_data._chart_repo.create", fake_create)
    monkeypatch.setattr(
        "bot.routers.birth_data._chart_repo.set_partner",
        AsyncMock(),
    )

    await _calculate_and_persist(
        _fsm_data(mode="partner", owner_chart_id=str(uuid.uuid4())),
        user=user,
        session=fake_session,
    )

    assert captured["name"] == "Партнёр"
