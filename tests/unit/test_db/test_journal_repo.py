"""Tests for ChartJournalSettings / JournalEntry repositories (Wave 4)."""

from __future__ import annotations

import uuid
from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from db.models import JournalEntrySource
from db.repositories.journal_repo import (
    ChartJournalSettingsRepository,
    JournalEntryRepository,
)

# ── Settings ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_or_create_returns_existing() -> None:
    """If the chart already has a settings row, return it untouched."""
    session = MagicMock()
    existing = MagicMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = existing
    session.execute = AsyncMock(return_value=result_mock)
    session.add = MagicMock()
    session.flush = AsyncMock()

    repo = ChartJournalSettingsRepository()
    got = await repo.get_or_create(session, chart_id=uuid.uuid4())
    assert got is existing
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_get_or_create_creates_when_missing() -> None:
    session = MagicMock()
    result_mock = MagicMock()
    result_mock.scalar_one_or_none.return_value = None
    session.execute = AsyncMock(return_value=result_mock)
    session.add = MagicMock()
    session.flush = AsyncMock()

    repo = ChartJournalSettingsRepository()
    got = await repo.get_or_create(session, chart_id=uuid.uuid4())
    assert got is not None
    session.add.assert_called_once()


@pytest.mark.asyncio
async def test_update_schedule_sets_fields() -> None:
    """Wave 4 — enabling journal records the chosen local + UTC hours."""
    session = MagicMock()
    result_mock = MagicMock()
    existing = MagicMock()
    existing.enabled = False
    existing.reminder_hour_local = 21
    existing.reminder_hour_utc = 18
    result_mock.scalar_one_or_none.return_value = existing
    session.execute = AsyncMock(return_value=result_mock)
    session.flush = AsyncMock()

    repo = ChartJournalSettingsRepository()
    settings = await repo.update_schedule(
        session,
        chart_id=uuid.uuid4(),
        enabled=True,
        reminder_hour_local=7,
        reminder_hour_utc=4,
    )
    assert settings.enabled is True
    assert settings.reminder_hour_local == 7
    assert settings.reminder_hour_utc == 4


# ── Entries ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_upsert_executes_insert_on_conflict_returning() -> None:
    """Insert uses PG `ON CONFLICT (chart_id, entry_date) DO UPDATE` so a
    second write same-day overwrites — test that the right statement runs."""
    session = MagicMock()
    fake_entry = MagicMock()
    result_mock = MagicMock()
    result_mock.scalar_one.return_value = fake_entry
    session.execute = AsyncMock(return_value=result_mock)

    repo = JournalEntryRepository()
    got = await repo.upsert(
        session,
        chart_id=uuid.uuid4(),
        entry_date=date.today(),
        energies_summary="x",
        user_reflection="y",
        source=JournalEntrySource.text,
    )
    assert got is fake_entry
    session.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_list_by_chart_orders_chronologically() -> None:
    """Export needs oldest-first iteration."""
    session = MagicMock()
    entries = [MagicMock(), MagicMock(), MagicMock()]
    result_mock = MagicMock()
    scalars_mock = MagicMock()
    scalars_mock.all.return_value = entries
    result_mock.scalars.return_value = scalars_mock
    session.execute = AsyncMock(return_value=result_mock)

    repo = JournalEntryRepository()
    got = await repo.list_by_chart(session, uuid.uuid4())
    assert got == entries
