"""Repository for journal settings + entries (Wave 4)."""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Final

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ChartJournalSettings, JournalEntry, JournalEntrySource

# Wave 4e v2 — day-of reflection prompt fires at 18:00 chart-local:
# день прожит, есть что рефлексировать (vs прежние 12:00 MSK).
REFLECTION_HOUR_LOCAL: Final = 18


def reflection_hour_utc_for(tz_offset_hours: float) -> int:
    """UTC hour at which 18:00 chart-local occurs.

    Same conversion as bot.routers.forecast._hour_local_to_utc, defined
    locally — db/ слой живёт без импортов из bot/."""
    return int(REFLECTION_HOUR_LOCAL - tz_offset_hours) % 24


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
        self,
        session: AsyncSession,
        *,
        chart_id: uuid.UUID,
        enabled: bool,
        tz_offset: float | None = None,
    ) -> ChartJournalSettings:
        """Wave 4e — turn important-date alerts on/off for one chart.

        ``tz_offset`` (chart's offset from UTC) — when given, recompute
        ``reflection_hour_utc`` so the day-of reflection prompt lands at
        18:00 chart-local. Callers that know the chart should pass it;
        ``None`` keeps the stored value (default 15 = 18:00 MSK)."""
        settings = await self.get_or_create(session, chart_id=chart_id)
        settings.important_dates_enabled = enabled
        if tz_offset is not None:
            settings.reflection_hour_utc = reflection_hour_utc_for(tz_offset)
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

    async def list_reflection_due_at(
        self, session: AsyncSession, *, hour_utc: int
    ) -> list[ChartJournalSettings]:
        """Wave 4e v2 — charts whose day-of reflection prompt is due at
        this UTC hour. Filter в SQL, не в Python: почасовой глобальный
        скан остаётся дешёвым на тысячах карт."""
        result = await session.execute(
            sa.select(ChartJournalSettings).where(
                ChartJournalSettings.important_dates_enabled.is_(True),
                ChartJournalSettings.reflection_hour_utc == hour_utc,
            )
        )
        return list(result.scalars().all())

    async def mark_warning_sent(
        self,
        session: AsyncSession,
        chart_id: uuid.UUID,
        *,
        target_date: date,
        now: datetime,
    ) -> None:
        """Record that an ahead-of-time WARNING for ``target_date`` was
        delivered. Atomic UPDATE (not flush) so the mark is durable the
        moment it runs — the scheduler commits per-chart right after.
        ``last_important_date_at`` drives the ≤1/week anti-spam;
        ``last_important_warning_date`` dedups the specific date."""
        await session.execute(
            sa.update(ChartJournalSettings)
            .where(ChartJournalSettings.chart_id == chart_id)
            .values(last_important_date_at=now, last_important_warning_date=target_date)
        )

    async def mark_reflection_prompt_sent(
        self, session: AsyncSession, chart_id: uuid.UUID, *, day: date
    ) -> None:
        """Record that the day-of REFLECTION prompt was sent on ``day`` —
        dedups so we don't re-prompt the same day."""
        await session.execute(
            sa.update(ChartJournalSettings)
            .where(ChartJournalSettings.chart_id == chart_id)
            .values(last_reflection_prompt_date=day)
        )


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
