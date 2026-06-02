"""Tests for scan_important_dates_job (Wave 4e fix, 2026-06-02).

Verifies the two-block redesign:
- day-of REFLECTION prompt (days_ahead==0) with per-day dedup,
- ahead-of-time WARNING (days_ahead 1..2) with ≤1/week + per-date dedup,
- per-chart commit.

Repos/bot/session all mocked; find_important_dates_in_range monkeypatched
so we control which dates "fire".
"""

from __future__ import annotations

import uuid as _uuid
from datetime import date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

import bot.scheduler.jobs as jobs
import calculator.important_dates as important_dates
from calculator.important_dates import ImportantDate
from db.repositories.chart_repo import ChartRepository
from db.repositories.journal_repo import ChartJournalSettingsRepository


class _FakeSessionCM:
    def __init__(self, session: object) -> None:
        self._s = session

    async def __aenter__(self) -> object:
        return self._s

    async def __aexit__(self, *a: object) -> bool:
        return False


def _setup(
    monkeypatch: pytest.MonkeyPatch,
    *,
    js: SimpleNamespace,
    hits: list[ImportantDate],
) -> tuple[MagicMock, AsyncMock, AsyncMock]:
    """Wire all the mocks. Returns (bot, mark_reflection, mark_warning)."""
    session = MagicMock()
    session.commit = AsyncMock()
    session.get = AsyncMock(return_value=SimpleNamespace(telegram_id=12345))

    monkeypatch.setattr(jobs, "_make_session_factory", lambda: (lambda: _FakeSessionCM(session)))

    bot = MagicMock()
    bot.send_message = AsyncMock()
    bot.session = MagicMock()
    bot.session.close = AsyncMock()
    monkeypatch.setattr(jobs, "_make_bot", lambda: bot)

    chart = SimpleNamespace(id=js.chart_id, user_id=_uuid.uuid4(), chart_data={})
    monkeypatch.setattr(ChartRepository, "get_by_id", AsyncMock(return_value=chart))
    monkeypatch.setattr(jobs.ChartOutput, "model_validate", lambda _data: MagicMock())

    monkeypatch.setattr(
        ChartJournalSettingsRepository,
        "list_important_dates_enabled",
        AsyncMock(return_value=[js]),
    )
    mark_reflection = AsyncMock()
    mark_warning = AsyncMock()
    monkeypatch.setattr(
        ChartJournalSettingsRepository, "mark_reflection_prompt_sent", mark_reflection
    )
    monkeypatch.setattr(ChartJournalSettingsRepository, "mark_warning_sent", mark_warning)

    monkeypatch.setattr(important_dates, "find_important_dates_in_range", lambda *a, **k: hits)
    return bot, mark_reflection, mark_warning


def _js(**over: object) -> SimpleNamespace:
    base: dict[str, object] = {
        "chart_id": _uuid.uuid4(),
        "last_important_date_at": None,
        "last_important_warning_date": None,
        "last_reflection_prompt_date": None,
    }
    base.update(over)
    return SimpleNamespace(**base)


@pytest.mark.asyncio
async def test_day_of_sends_reflection_and_marks(monkeypatch: pytest.MonkeyPatch) -> None:
    today = date.today()
    hit = ImportantDate(date_=today, active_stars=("文昌贵人",), severity="low")
    js = _js()
    bot, mark_reflection, mark_warning = _setup(monkeypatch, js=js, hits=[hit])

    await jobs.scan_important_dates_job()

    bot.send_message.assert_awaited_once()
    text = bot.send_message.await_args.kwargs["text"]
    assert "Сегодня" in text
    mark_reflection.assert_awaited_once()
    mark_warning.assert_not_awaited()


@pytest.mark.asyncio
async def test_day_of_dedup_skips_when_already_prompted(monkeypatch: pytest.MonkeyPatch) -> None:
    today = date.today()
    hit = ImportantDate(date_=today, active_stars=("文昌贵人",), severity="low")
    js = _js(last_reflection_prompt_date=today)  # already prompted today
    bot, mark_reflection, _ = _setup(monkeypatch, js=js, hits=[hit])

    await jobs.scan_important_dates_job()

    bot.send_message.assert_not_awaited()
    mark_reflection.assert_not_awaited()


@pytest.mark.asyncio
async def test_ahead_sends_warning_without_reflection_button(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    today = date.today()
    target = today + timedelta(days=2)
    hit = ImportantDate(date_=target, active_stars=("白虎",), severity="high")
    js = _js()
    bot, _, mark_warning = _setup(monkeypatch, js=js, hits=[hit])

    await jobs.scan_important_dates_job()

    bot.send_message.assert_awaited_once()
    text = bot.send_message.await_args.kwargs["text"]
    assert "Через 2 дня" in text
    kb = bot.send_message.await_args.kwargs["reply_markup"]
    callbacks = {b.callback_data for row in kb.inline_keyboard for b in row}
    assert not any(c.startswith("journal:write:") for c in callbacks)  # no reflection button
    mark_warning.assert_awaited_once()
    assert mark_warning.await_args.kwargs["target_date"] == target


@pytest.mark.asyncio
async def test_warning_dedup_same_date_not_resent(monkeypatch: pytest.MonkeyPatch) -> None:
    today = date.today()
    target = today + timedelta(days=2)
    hit = ImportantDate(date_=target, active_stars=("白虎",), severity="high")
    js = _js(last_important_warning_date=target)  # already warned for this date
    bot, _, mark_warning = _setup(monkeypatch, js=js, hits=[hit])

    await jobs.scan_important_dates_job()

    bot.send_message.assert_not_awaited()
    mark_warning.assert_not_awaited()


@pytest.mark.asyncio
async def test_warning_rate_limited_within_week(monkeypatch: pytest.MonkeyPatch) -> None:
    today = date.today()
    target = today + timedelta(days=1)
    hit = ImportantDate(date_=target, active_stars=("桃花",), severity="medium")
    js = _js(last_important_date_at=datetime.now() - timedelta(days=2))  # warned 2 days ago
    bot, _, mark_warning = _setup(monkeypatch, js=js, hits=[hit])

    await jobs.scan_important_dates_job()

    bot.send_message.assert_not_awaited()
    mark_warning.assert_not_awaited()
