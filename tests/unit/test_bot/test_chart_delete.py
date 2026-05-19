"""Tests for the chart-delete flow in bot.routers.start (Wave 1b).

Three handlers + one repository method:
- handle_chart_delete_request → confirm dialog
- handle_chart_delete_confirm → repo.delete + main menu
- handle_chart_delete_cancel → drop confirm message
"""

from __future__ import annotations

import uuid as _uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Message

from bot.routers import start as start_module
from bot.routers.start import (
    handle_chart_delete_cancel,
    handle_chart_delete_confirm,
    handle_chart_delete_request,
)

# ── Fixtures ─────────────────────────────────────────────────────────────


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

    async def _clear() -> None:
        s._data.clear()

    s.get_data = _get_data
    s.update_data = _update_data
    s.set_state = _set_state
    s.clear = _clear
    return s


@pytest.fixture
def fake_user() -> MagicMock:
    u = MagicMock()
    u.id = _uuid.uuid4()
    u.telegram_id = 545371253
    u.first_name = "Bogdan"
    return u


@pytest.fixture
def fake_session() -> MagicMock:
    return MagicMock()


def _fake_chart(*, user_id: _uuid.UUID, chart_id: _uuid.UUID | None = None) -> MagicMock:
    c = MagicMock()
    c.id = chart_id or _uuid.uuid4()
    c.user_id = user_id
    c.name = "Моя карта"
    c.birth_datetime_original = MagicMock()
    c.birth_datetime_original.date.return_value = MagicMock(strftime=lambda fmt: "27.04.1988")
    c.chart_data = {"day_master": "丁"}
    return c


def _fake_callback(data: str) -> MagicMock:
    cb = MagicMock()
    cb.message = MagicMock(spec=Message)
    cb.message.answer = AsyncMock()
    cb.message.edit_text = AsyncMock()
    cb.message.delete = AsyncMock()
    cb.answer = AsyncMock()
    cb.data = data
    return cb


# ── handle_chart_delete_request ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_request_shows_confirm_with_label(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: MagicMock,
    fake_user: MagicMock,
) -> None:
    chart = _fake_chart(user_id=fake_user.id)
    monkeypatch.setattr(start_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))
    monkeypatch.setattr(start_module, "_format_chart_label", lambda c: "Моя карта")

    cb = _fake_callback(f"chart:delete:{chart.id}")
    await handle_chart_delete_request(callback=cb, session=fake_session, user=fake_user)

    cb.message.answer.assert_awaited_once()
    args, kwargs = cb.message.answer.call_args
    assert "Моя карта" in args[0]
    assert "навсегда" in args[0].lower()
    # The confirm kb has a chart:delete_confirm:<id> button
    kb = kwargs["reply_markup"]
    callbacks = {btn.callback_data for row in kb.inline_keyboard for btn in row}
    assert f"chart:delete_confirm:{chart.id}" in callbacks
    assert "chart:delete_cancel" in callbacks


@pytest.mark.asyncio
async def test_delete_request_rejects_chart_of_other_user(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: MagicMock,
    fake_user: MagicMock,
) -> None:
    """Server-side ownership check — leaked callback can't delete another user's chart."""
    chart = _fake_chart(user_id=_uuid.uuid4())  # belongs to someone else
    monkeypatch.setattr(start_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))
    delete_mock = AsyncMock()
    monkeypatch.setattr(start_module._chart_repo, "delete", delete_mock)

    cb = _fake_callback(f"chart:delete:{chart.id}")
    await handle_chart_delete_request(callback=cb, session=fake_session, user=fake_user)

    cb.answer.assert_awaited_once()
    # Alert text mentions «не найдена» (we hide ownership for privacy)
    args, kwargs = cb.answer.call_args
    assert "не найдена" in args[0].lower()
    cb.message.answer.assert_not_awaited()
    delete_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_request_handles_garbage_uuid(
    fake_session: MagicMock,
    fake_user: MagicMock,
) -> None:
    cb = _fake_callback("chart:delete:not-a-uuid")
    await handle_chart_delete_request(callback=cb, session=fake_session, user=fake_user)
    cb.answer.assert_awaited_once()
    cb.message.answer.assert_not_awaited()


# ── handle_chart_delete_confirm ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_confirm_calls_repo_and_clears_fsm_pin(
    monkeypatch: pytest.MonkeyPatch,
    fake_state: MagicMock,
    fake_session: MagicMock,
    fake_user: MagicMock,
) -> None:
    chart = _fake_chart(user_id=fake_user.id)
    monkeypatch.setattr(start_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))
    delete_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(start_module._chart_repo, "delete", delete_mock)
    monkeypatch.setattr(start_module, "_format_chart_label", lambda c: "Моя карта")
    send_menu_mock = AsyncMock()
    monkeypatch.setattr(start_module, "send_main_menu", send_menu_mock)

    # FSM had this chart pinned — confirm should clear it.
    await fake_state.update_data(chart_id=str(chart.id))

    cb = _fake_callback(f"chart:delete_confirm:{chart.id}")
    await handle_chart_delete_confirm(
        callback=cb, state=fake_state, session=fake_session, user=fake_user
    )

    delete_mock.assert_awaited_once_with(fake_session, chart.id)
    data = await fake_state.get_data()
    assert data["chart_id"] is None
    cb.message.edit_text.assert_awaited_once()
    edited = cb.message.edit_text.call_args.args[0]
    assert "Моя карта" in edited
    assert "удалена" in edited.lower()
    send_menu_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_confirm_idempotent_when_already_gone(
    monkeypatch: pytest.MonkeyPatch,
    fake_state: MagicMock,
    fake_session: MagicMock,
    fake_user: MagicMock,
) -> None:
    """Race: user double-clicks confirm. Second call finds the row gone
    and surfaces an alert instead of crashing."""
    chart = _fake_chart(user_id=fake_user.id)
    # First get_by_id succeeds, repo.delete returns False (race).
    monkeypatch.setattr(start_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))
    monkeypatch.setattr(start_module._chart_repo, "delete", AsyncMock(return_value=False))
    send_menu_mock = AsyncMock()
    monkeypatch.setattr(start_module, "send_main_menu", send_menu_mock)

    cb = _fake_callback(f"chart:delete_confirm:{chart.id}")
    await handle_chart_delete_confirm(
        callback=cb, state=fake_state, session=fake_session, user=fake_user
    )

    # Alert shown, menu NOT re-rendered.
    cb.answer.assert_awaited_once()
    assert "не найдена" in cb.answer.call_args.args[0].lower()
    send_menu_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_delete_confirm_blocks_cross_user_id(
    monkeypatch: pytest.MonkeyPatch,
    fake_state: MagicMock,
    fake_session: MagicMock,
    fake_user: MagicMock,
) -> None:
    """Ownership check at confirm step too — leaked callback can't be
    replayed to delete someone else's chart."""
    chart = _fake_chart(user_id=_uuid.uuid4())  # not this user's
    monkeypatch.setattr(start_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))
    delete_mock = AsyncMock()
    monkeypatch.setattr(start_module._chart_repo, "delete", delete_mock)

    cb = _fake_callback(f"chart:delete_confirm:{chart.id}")
    await handle_chart_delete_confirm(
        callback=cb, state=fake_state, session=fake_session, user=fake_user
    )

    cb.answer.assert_awaited_once()
    delete_mock.assert_not_awaited()


# ── handle_chart_delete_cancel ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_cancel_removes_confirm_message() -> None:
    cb = _fake_callback("chart:delete_cancel")
    await handle_chart_delete_cancel(callback=cb)

    cb.message.delete.assert_awaited_once()
    cb.answer.assert_awaited_once()
