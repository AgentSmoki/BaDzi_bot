"""Tests for bot.routers.master_meeting + service.detect_source_type (Wave 5)."""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Message

from bot.routers import master_meeting as meeting_module
from bot.routers.master_meeting import (
    _is_valid_url,
    handle_add_start,
    handle_delete_confirm,
    handle_show,
    handle_url_input,
    handle_view,
)
from bot.services.teletranscribe import detect_source_type
from bot.states import MasterMeetingState
from db.models import MasterMeetingSource, MasterMeetingStatus

# ── URL source detection ─────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://www.youtube.com/watch?v=abc", "youtube"),
        ("https://youtu.be/abc", "youtube"),
        ("https://drive.google.com/file/d/X/view", "gdrive"),
        ("https://disk.yandex.ru/i/abc", "ydisk"),
        ("https://yadi.sk/d/xyz", "ydisk"),
        ("https://cloud.mail.ru/public/abc", "cloud_mail"),
        ("https://us04web.zoom.us/rec/share/xyz", "zoom"),
        ("https://example.com/audio.mp3", "other"),
    ],
)
def test_detect_source_type(url: str, expected: str) -> None:
    assert detect_source_type(url) == expected


def test_is_valid_url_accepts_http_and_https() -> None:
    assert _is_valid_url("https://example.com/x")
    assert _is_valid_url("http://example.com/x")
    assert not _is_valid_url("example.com/x")
    assert not _is_valid_url("not a url at all")
    assert not _is_valid_url("https://has space.com")


# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def fake_user() -> MagicMock:
    u = MagicMock()
    u.id = _uuid.uuid4()
    return u


@pytest.fixture
def fake_session() -> MagicMock:
    s = MagicMock()
    s.commit = AsyncMock()
    return s


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

    async def _clear() -> None:
        data.clear()

    s.get_data = _get_data
    s.update_data = _update_data
    s.set_state = _set_state
    s.clear = _clear
    return s


def _fake_chart(*, user_id: _uuid.UUID) -> MagicMock:
    c = MagicMock()
    c.id = _uuid.uuid4()
    c.user_id = user_id
    return c


def _fake_meeting(
    *,
    user_id: _uuid.UUID,
    status: MasterMeetingStatus = MasterMeetingStatus.ready,
    summary: str | None = "## Темы\nрост, отношения",
) -> MagicMock:
    m = MagicMock()
    m.id = _uuid.uuid4()
    m.user_id = user_id
    m.chart_id = _uuid.uuid4()
    m.status = status
    m.summary = summary
    m.transcript = "long text"
    m.source_type = MasterMeetingSource.youtube
    m.uploaded_at = datetime.now()
    m.error = None
    return m


def _fake_callback(data: str) -> MagicMock:
    cb = MagicMock()
    cb.message = MagicMock(spec=Message)
    cb.message.answer = AsyncMock()
    cb.message.edit_text = AsyncMock()
    cb.answer = AsyncMock()
    cb.data = data
    return cb


def _fake_message(text: str) -> MagicMock:
    m = MagicMock()
    m.text = text
    m.answer = AsyncMock()
    return m


# ── show ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_show_lists_meetings(
    monkeypatch: pytest.MonkeyPatch, fake_session: MagicMock, fake_user: MagicMock
) -> None:
    chart = _fake_chart(user_id=fake_user.id)
    monkeypatch.setattr(meeting_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))
    meeting = _fake_meeting(user_id=fake_user.id)
    monkeypatch.setattr(
        meeting_module._meeting_repo,
        "list_by_chart",
        AsyncMock(return_value=[meeting]),
    )
    cb = _fake_callback(f"meeting:show:{chart.id}")
    await handle_show(callback=cb, session=fake_session, user=fake_user)

    cb.message.answer.assert_awaited_once()
    text = cb.message.answer.call_args.args[0]
    assert "Встречи с мастером" in text
    # kb contains «Добавить ссылку» + at least one meeting button
    kb = cb.message.answer.call_args.kwargs["reply_markup"]
    callback_data = {btn.callback_data for row in kb.inline_keyboard for btn in row}
    assert f"meeting:add:{chart.id}" in callback_data
    assert any(cb_data.startswith(f"meeting:view:{meeting.id}") for cb_data in callback_data)


@pytest.mark.asyncio
async def test_show_blocks_other_user_chart(
    monkeypatch: pytest.MonkeyPatch, fake_session: MagicMock, fake_user: MagicMock
) -> None:
    chart = _fake_chart(user_id=_uuid.uuid4())
    monkeypatch.setattr(meeting_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))
    cb = _fake_callback(f"meeting:show:{chart.id}")
    await handle_show(callback=cb, session=fake_session, user=fake_user)
    cb.message.answer.assert_not_awaited()


# ── add + url input ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_add_start_sets_fsm(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_state: MagicMock,
) -> None:
    chart = _fake_chart(user_id=fake_user.id)
    monkeypatch.setattr(meeting_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))

    cb = _fake_callback(f"meeting:add:{chart.id}")
    await handle_add_start(callback=cb, session=fake_session, user=fake_user, state=fake_state)

    data = await fake_state.get_data()
    assert data["__state"] == MasterMeetingState.waiting_url
    assert data["meeting_chart_id"] == str(chart.id)


@pytest.mark.asyncio
async def test_url_input_rejects_garbage(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_state: MagicMock,
) -> None:
    await fake_state.update_data(meeting_chart_id=str(_uuid.uuid4()))
    create_mock = AsyncMock()
    monkeypatch.setattr(meeting_module._meeting_repo, "create_queued", create_mock)

    msg = _fake_message("not a url")
    await handle_url_input(message=msg, session=fake_session, state=fake_state, user=fake_user)

    create_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_url_input_creates_and_enqueues(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_state: MagicMock,
) -> None:
    chart = _fake_chart(user_id=fake_user.id)
    await fake_state.update_data(meeting_chart_id=str(chart.id))
    monkeypatch.setattr(meeting_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))
    created_meeting = MagicMock(id=_uuid.uuid4())
    create_mock = AsyncMock(return_value=created_meeting)
    monkeypatch.setattr(meeting_module._meeting_repo, "create_queued", create_mock)
    kiq_mock = AsyncMock()
    monkeypatch.setattr(meeting_module.transcribe_master_meeting, "kiq", kiq_mock)

    msg = _fake_message("https://youtu.be/abc123")
    await handle_url_input(message=msg, session=fake_session, state=fake_state, user=fake_user)

    create_mock.assert_awaited_once()
    kwargs = create_mock.call_args.kwargs
    assert kwargs["source_url"] == "https://youtu.be/abc123"
    assert kwargs["source_type"] == MasterMeetingSource.youtube
    kiq_mock.assert_awaited_once_with(str(created_meeting.id))


# ── view ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_view_shows_summary_when_ready(
    monkeypatch: pytest.MonkeyPatch, fake_session: MagicMock, fake_user: MagicMock
) -> None:
    chart_id = _uuid.uuid4()
    meeting = _fake_meeting(user_id=fake_user.id, status=MasterMeetingStatus.ready)
    monkeypatch.setattr(meeting_module._meeting_repo, "get_by_id", AsyncMock(return_value=meeting))

    cb = _fake_callback(f"meeting:view:{meeting.id}:{chart_id}")
    await handle_view(callback=cb, session=fake_session, user=fake_user)

    text = cb.message.answer.call_args.args[0]
    assert "Темы" in text


@pytest.mark.asyncio
async def test_view_shows_status_when_transcribing(
    monkeypatch: pytest.MonkeyPatch, fake_session: MagicMock, fake_user: MagicMock
) -> None:
    chart_id = _uuid.uuid4()
    meeting = _fake_meeting(
        user_id=fake_user.id, status=MasterMeetingStatus.transcribing, summary=None
    )
    monkeypatch.setattr(meeting_module._meeting_repo, "get_by_id", AsyncMock(return_value=meeting))

    cb = _fake_callback(f"meeting:view:{meeting.id}:{chart_id}")
    await handle_view(callback=cb, session=fake_session, user=fake_user)

    text = cb.message.answer.call_args.args[0]
    assert "расшифровывается" in text or "Статус" in text


# ── delete ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_delete_confirm_calls_repo(
    monkeypatch: pytest.MonkeyPatch, fake_session: MagicMock, fake_user: MagicMock
) -> None:
    chart_id = _uuid.uuid4()
    meeting = _fake_meeting(user_id=fake_user.id)
    monkeypatch.setattr(meeting_module._meeting_repo, "get_by_id", AsyncMock(return_value=meeting))
    delete_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(meeting_module._meeting_repo, "delete", delete_mock)
    monkeypatch.setattr(meeting_module._meeting_repo, "list_by_chart", AsyncMock(return_value=[]))

    cb = _fake_callback(f"meeting:delete_confirm:{meeting.id}:{chart_id}")
    await handle_delete_confirm(callback=cb, session=fake_session, user=fake_user)

    delete_mock.assert_awaited_once()


@pytest.mark.asyncio
async def test_delete_blocks_cross_user(
    monkeypatch: pytest.MonkeyPatch, fake_session: MagicMock, fake_user: MagicMock
) -> None:
    meeting = _fake_meeting(user_id=_uuid.uuid4())  # someone else's
    monkeypatch.setattr(meeting_module._meeting_repo, "get_by_id", AsyncMock(return_value=meeting))
    delete_mock = AsyncMock()
    monkeypatch.setattr(meeting_module._meeting_repo, "delete", delete_mock)

    cb = _fake_callback(f"meeting:delete_confirm:{meeting.id}:{_uuid.uuid4()}")
    await handle_delete_confirm(callback=cb, session=fake_session, user=fake_user)

    delete_mock.assert_not_awaited()
