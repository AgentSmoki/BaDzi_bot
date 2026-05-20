"""Tests for bot.routers.journal (Wave 4).

Repos + session mocked. Verifies ownership checks, FSM transitions,
voice transcription error fallback, and the export markdown shape.
"""

from __future__ import annotations

import uuid as _uuid
from datetime import date
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Message

from bot.routers import journal as journal_module
from bot.routers.journal import (
    _build_energies_summary,
    _hour_local_to_utc,
    _render_export_md,
    handle_disable,
    handle_enable_set,
    handle_export,
    handle_journal_show,
    handle_text_reflection,
    handle_write_start,
)
from bot.services.teletranscribe import TeleTranscribeError
from bot.states import JournalState
from db.models import JournalEntrySource

# ── Fixtures ─────────────────────────────────────────────────────────────


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


@pytest.fixture
def fake_user() -> MagicMock:
    u = MagicMock()
    u.id = _uuid.uuid4()
    u.telegram_id = 545371253
    return u


@pytest.fixture
def fake_session() -> MagicMock:
    s = MagicMock()
    s.commit = AsyncMock()
    return s


def _fake_chart(*, user_id: _uuid.UUID, tz_offset: float = 3.0) -> MagicMock:
    c = MagicMock()
    c.id = _uuid.uuid4()
    c.user_id = user_id
    c.tz_offset = tz_offset
    c.name = "Моя карта"
    c.chart_data = {"day_master": "丁"}
    return c


def _fake_settings(*, enabled: bool = False, hour_local: int = 21) -> MagicMock:
    s = MagicMock()
    s.enabled = enabled
    s.reminder_hour_local = hour_local
    s.reminder_hour_utc = (hour_local - 3) % 24
    return s


def _fake_callback(data: str) -> MagicMock:
    cb = MagicMock()
    cb.message = MagicMock(spec=Message)
    cb.message.answer = AsyncMock()
    cb.message.answer_document = AsyncMock()
    cb.message.edit_text = AsyncMock()
    cb.answer = AsyncMock()
    cb.data = data
    return cb


def _fake_message_text(text: str) -> MagicMock:
    m = MagicMock()
    m.text = text
    m.voice = None
    m.answer = AsyncMock()
    return m


# ── Utility ──────────────────────────────────────────────────────────────


def test_hour_local_to_utc_basic() -> None:
    assert _hour_local_to_utc(21, 3.0) == 18  # Moscow 21:00 → 18:00 UTC
    assert _hour_local_to_utc(7, 3.0) == 4


def test_build_energies_summary_includes_natal_dm_and_day_pillars() -> None:
    chart = _fake_chart(user_id=_uuid.uuid4())
    summary = _build_energies_summary(chart, target_day=date(2026, 5, 20))
    assert "20.05.2026" in summary
    assert "丁" in summary
    assert "Столпы дня" in summary


def test_render_export_md_includes_entries() -> None:
    entries = [
        MagicMock(
            entry_date=date(2026, 5, 19),
            energies_summary="energies-1",
            user_reflection="reflection-1",
            source=MagicMock(value="text"),
        ),
        MagicMock(
            entry_date=date(2026, 5, 20),
            energies_summary="energies-2",
            user_reflection=None,
            source=MagicMock(value="auto"),
        ),
    ]
    md = _render_export_md(chart_label="Моя", entries=entries)
    assert "# Дневник рефлексии — Моя" in md
    assert "19.05.2026" in md and "20.05.2026" in md
    assert "energies-1" in md and "reflection-1" in md
    assert "автоматическая запись" in md  # auto-source label


# ── Show / enable / disable ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_show_renders_enabled_state(
    monkeypatch: pytest.MonkeyPatch, fake_session: MagicMock, fake_user: MagicMock
) -> None:
    chart = _fake_chart(user_id=fake_user.id)
    monkeypatch.setattr(journal_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))
    monkeypatch.setattr(
        journal_module._settings_repo,
        "get_or_create",
        AsyncMock(return_value=_fake_settings(enabled=True, hour_local=7)),
    )
    cb = _fake_callback(f"journal:show:{chart.id}")
    await handle_journal_show(callback=cb, session=fake_session, user=fake_user)

    answer = cb.message.answer.call_args.args[0]
    assert "Включён" in answer
    assert "07:00" in answer


@pytest.mark.asyncio
async def test_show_blocks_other_user_chart(
    monkeypatch: pytest.MonkeyPatch, fake_session: MagicMock, fake_user: MagicMock
) -> None:
    chart = _fake_chart(user_id=_uuid.uuid4())  # not this user's
    monkeypatch.setattr(journal_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))
    cb = _fake_callback(f"journal:show:{chart.id}")
    await handle_journal_show(callback=cb, session=fake_session, user=fake_user)
    cb.message.answer.assert_not_awaited()


@pytest.mark.asyncio
async def test_enable_set_calls_update_schedule(
    monkeypatch: pytest.MonkeyPatch, fake_session: MagicMock, fake_user: MagicMock
) -> None:
    chart = _fake_chart(user_id=fake_user.id, tz_offset=3.0)
    monkeypatch.setattr(journal_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))
    update_mock = AsyncMock()
    monkeypatch.setattr(journal_module._settings_repo, "update_schedule", update_mock)

    cb = _fake_callback(f"journal:enable_set:{chart.id}:7")
    await handle_enable_set(callback=cb, session=fake_session, user=fake_user)

    update_mock.assert_awaited_once()
    kwargs = update_mock.call_args.kwargs
    assert kwargs["enabled"] is True
    assert kwargs["reminder_hour_local"] == 7
    assert kwargs["reminder_hour_utc"] == 4  # 7 local - 3 tz = 4 UTC


@pytest.mark.asyncio
async def test_disable_flips_enabled_false(
    monkeypatch: pytest.MonkeyPatch, fake_session: MagicMock, fake_user: MagicMock
) -> None:
    chart = _fake_chart(user_id=fake_user.id)
    monkeypatch.setattr(journal_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))
    monkeypatch.setattr(
        journal_module._settings_repo,
        "get_or_create",
        AsyncMock(return_value=_fake_settings(enabled=True)),
    )
    update_mock = AsyncMock()
    monkeypatch.setattr(journal_module._settings_repo, "update_schedule", update_mock)

    cb = _fake_callback(f"journal:disable:{chart.id}")
    await handle_disable(callback=cb, session=fake_session, user=fake_user)

    update_mock.assert_awaited_once()
    assert update_mock.call_args.kwargs["enabled"] is False


# ── Write text reflection ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_write_start_sets_fsm(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_state: MagicMock,
) -> None:
    chart = _fake_chart(user_id=fake_user.id)
    monkeypatch.setattr(journal_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))

    cb = _fake_callback(f"journal:write:{chart.id}")
    await handle_write_start(callback=cb, session=fake_session, user=fake_user, state=fake_state)

    data = await fake_state.get_data()
    assert data["__state"] == JournalState.waiting_reflection
    assert data["journal_chart_id"] == str(chart.id)


@pytest.mark.asyncio
async def test_text_reflection_upserts_entry(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_state: MagicMock,
) -> None:
    chart = _fake_chart(user_id=fake_user.id)
    await fake_state.update_data(journal_chart_id=str(chart.id))
    monkeypatch.setattr(journal_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))
    upsert_mock = AsyncMock()
    monkeypatch.setattr(journal_module._entry_repo, "upsert", upsert_mock)

    msg = _fake_message_text("Хороший день, прошёл медитацию.")
    await handle_text_reflection(
        message=msg, session=fake_session, state=fake_state, user=fake_user
    )

    upsert_mock.assert_awaited_once()
    kwargs = upsert_mock.call_args.kwargs
    assert kwargs["user_reflection"] == "Хороший день, прошёл медитацию."
    assert kwargs["source"] == JournalEntrySource.text
    assert kwargs["chart_id"] == chart.id


# ── Voice flow — failure path ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_voice_transcribe_failure_falls_back_gracefully(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_state: MagicMock,
) -> None:
    """TT service down → user gets a polite message, FSM doesn't progress."""
    from bot.routers.journal import handle_voice_reflection

    chart = _fake_chart(user_id=fake_user.id)
    await fake_state.update_data(journal_chart_id=str(chart.id))
    monkeypatch.setattr(journal_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))

    msg = MagicMock()
    msg.voice = MagicMock(file_id="vfid")
    msg.answer = AsyncMock()

    bot = MagicMock()

    async def fake_download(_file_id: str, *, destination: Any) -> None:
        destination.write(b"fake-audio")

    bot.download = fake_download
    monkeypatch.setattr(
        journal_module, "transcribe_voice", AsyncMock(side_effect=TeleTranscribeError("502"))
    )

    await handle_voice_reflection(
        message=msg, session=fake_session, state=fake_state, user=fake_user, bot=bot
    )

    # Two answers: «Расшифровываю...» then the failure fallback.
    assert msg.answer.await_count >= 2
    fallback_text = msg.answer.await_args_list[-1].args[0]
    assert "не отвечает" in fallback_text or "не получилось" in fallback_text


# ── Export ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_export_sends_document_with_entries(
    monkeypatch: pytest.MonkeyPatch, fake_session: MagicMock, fake_user: MagicMock
) -> None:
    chart = _fake_chart(user_id=fake_user.id)
    monkeypatch.setattr(journal_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))
    entry = MagicMock(
        entry_date=date(2026, 5, 20),
        energies_summary="x",
        user_reflection="y",
        source=MagicMock(value="text"),
    )
    monkeypatch.setattr(
        journal_module._entry_repo, "list_by_chart", AsyncMock(return_value=[entry])
    )

    cb = _fake_callback(f"journal:export:{chart.id}")
    await handle_export(callback=cb, session=fake_session, user=fake_user)

    cb.message.answer_document.assert_awaited_once()


@pytest.mark.asyncio
async def test_export_empty_journal_alerts_user(
    monkeypatch: pytest.MonkeyPatch, fake_session: MagicMock, fake_user: MagicMock
) -> None:
    chart = _fake_chart(user_id=fake_user.id)
    monkeypatch.setattr(journal_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))
    monkeypatch.setattr(journal_module._entry_repo, "list_by_chart", AsyncMock(return_value=[]))

    cb = _fake_callback(f"journal:export:{chart.id}")
    await handle_export(callback=cb, session=fake_session, user=fake_user)

    cb.message.answer_document.assert_not_awaited()
    cb.answer.assert_awaited_once()
