"""Repository for journal settings + entries (Wave 4)."""

from __future__ import annotations

import uuid
from datetime import date

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ChartJournalSettings, JournalEntry, JournalEntrySource


class ChartJournalSettingsRepository:
    async def get_or_create(
        self, session: AsyncSession, *, chart_id: uuid.UUID
    ) -> ChartJournalSettings:
        """Return existing settings or create defaults (disabled, 21:00 local)."""
        existing = await session.execute(
            sa.select(ChartJournalSettings).where(ChartJournalSettings.chart_id == chart_id)
        )
        row = existing.scalar_one_or_none()
        if row is not None:
            return row
        settings = ChartJournalSettings(chart_id=chart_id)
        session.add(settings)
        await session.flush()
        return settings

    async def update_schedule(
        self,
        session: AsyncSession,
        *,
        chart_id: uuid.UUID,
        enabled: bool,
        reminder_hour_local: int,
        reminder_hour_utc: int,
    ) -> ChartJournalSettings:
        """Idempotent upsert of enabled + reminder hours."""
        settings = await self.get_or_create(session, chart_id=chart_id)
        settings.enabled = enabled
        settings.reminder_hour_local = reminder_hour_local
        settings.reminder_hour_utc = reminder_hour_utc
        await session.flush()
        return settings

    async def list_enabled(self, session: AsyncSession) -> list[ChartJournalSettings]:
        """Scheduler-side: every chart with journal reminder turned on."""
        result = await session.execute(
            sa.select(ChartJournalSettings).where(ChartJournalSettings.enabled.is_(True))
        )
        return list(result.scalars().all())

    async def toggle_important_dates(
        self, session: AsyncSession, *, chart_id: uuid.UUID, enabled: bool
    ) -> ChartJournalSettings:
        """Wave 4e — turn important-date alerts on/off for one chart."""
        settings = await self.get_or_create(session, chart_id=chart_id)
        settings.important_dates_enabled = enabled
        await session.flush()
        return settings

    async def list_important_dates_enabled(
        self, session: AsyncSession
    ) -> list[ChartJournalSettings]:
        """Scheduler-side: charts that opted into important-date alerts."""
        result = await session.execute(
            sa.select(ChartJournalSettings).where(
                ChartJournalSettings.important_dates_enabled.is_(True)
            )
        )
        return list(result.scalars().all())

    async def mark_important_date_sent(self, session: AsyncSession, chart_id: uuid.UUID) -> None:
        """Record that an important-date alert was just delivered, so
        the rate-limit (no more than once per 7 days) holds."""
        from datetime import datetime

        settings = await self.get_or_create(session, chart_id=chart_id)
        settings.last_important_date_at = datetime.now()
        await session.flush()


class JournalEntryRepository:
    async def upsert(
        self,
        session: AsyncSession,
        *,
        chart_id: uuid.UUID,
        entry_date: date,
        energies_summary: str,
        user_reflection: str | None,
        source: JournalEntrySource,
    ) -> JournalEntry:
        """Upsert by (chart_id, entry_date) — overwriting the day's
        reflection is the expected UX (user re-records the same day)."""
        stmt = (
            pg_insert(JournalEntry)
            .values(
                chart_id=chart_id,
                entry_date=entry_date,
                energies_summary=energies_summary,
                user_reflection=user_reflection,
                source=source,
            )
            .on_conflict_do_update(
                index_elements=["chart_id", "entry_date"],
                set_={
                    "energies_summary": energies_summary,
                    "user_reflection": user_reflection,
                    "source": source,
                },
            )
            .returning(JournalEntry)
        )
        result = await session.execute(stmt)
        return result.scalar_one()

    async def list_by_chart(self, session: AsyncSession, chart_id: uuid.UUID) -> list[JournalEntry]:
        """All entries for a chart, oldest first (for the MD export)."""
        result = await session.execute(
            sa.select(JournalEntry)
            .where(JournalEntry.chart_id == chart_id)
            .order_by(JournalEntry.entry_date)
        )
        return list(result.scalars().all())

    async def get_by_date(
        self, session: AsyncSession, *, chart_id: uuid.UUID, entry_date: date
    ) -> JournalEntry | None:
        result = await session.execute(
            sa.select(JournalEntry).where(
                JournalEntry.chart_id == chart_id,
                JournalEntry.entry_date == entry_date,
            )
        )
        return result.scalar_one_or_none()
