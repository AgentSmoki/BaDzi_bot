import uuid
from datetime import datetime
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Chart


class ChartRepository:
    async def create(
        self,
        session: AsyncSession,
        *,
        user_id: uuid.UUID,
        birth_datetime_utc: datetime,
        birth_datetime_original: datetime,
        latitude: float,
        longitude: float,
        tz_offset: float,
        chart_data: dict[str, Any],
        name: str | None = None,
        has_birth_time: bool = True,
        early_rat: bool = False,
        hidden_stems_school: str = "traditional",
    ) -> Chart:
        chart = Chart(
            user_id=user_id,
            name=name,
            birth_datetime_utc=birth_datetime_utc,
            birth_datetime_original=birth_datetime_original,
            latitude=latitude,
            longitude=longitude,
            tz_offset=tz_offset,
            chart_data=chart_data,
            has_birth_time=has_birth_time,
            early_rat=early_rat,
            hidden_stems_school=hidden_stems_school,
        )
        session.add(chart)
        await session.flush()
        return chart

    async def get_by_id(self, session: AsyncSession, chart_id: uuid.UUID) -> Chart | None:
        return await session.get(Chart, chart_id)

    async def get_latest_by_user(self, session: AsyncSession, user_id: uuid.UUID) -> Chart | None:
        result = await session.execute(
            sa.select(Chart)
            .where(Chart.user_id == user_id)
            .order_by(Chart.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def list_by_user(self, session: AsyncSession, user_id: uuid.UUID) -> list[Chart]:
        result = await session.execute(
            sa.select(Chart).where(Chart.user_id == user_id).order_by(Chart.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_unique_by_user(self, session: AsyncSession, user_id: uuid.UUID) -> list[Chart]:
        """Return the user's charts with duplicates collapsed.

        Two charts collapse if they share birth date, location (≈100 m
        precision), and gender. Within a group:
        - if any chart carries a birth time, the time-less variants are
          dropped (they're strictly less informative);
        - charts with the *same* exact birth time also collapse to one;
        - among equally-informative duplicates, the user-named one wins,
          and freshest created_at breaks the remaining tie.
        """
        all_charts = await self.list_by_user(session, user_id)
        if not all_charts:
            return []

        groups: dict[tuple[Any, ...], list[Chart]] = {}
        for chart in all_charts:
            key = _coarse_key(chart)
            groups.setdefault(key, []).append(chart)

        result: list[Chart] = []
        for group in groups.values():
            result.extend(_pick_best_in_group(group))

        result.sort(key=lambda c: c.created_at, reverse=True)
        return result

    async def update_name(
        self, session: AsyncSession, chart_id: uuid.UUID, name: str | None
    ) -> None:
        await session.execute(sa.update(Chart).where(Chart.id == chart_id).values(name=name))

    async def delete(self, session: AsyncSession, chart_id: uuid.UUID) -> bool:
        """Hard-delete a chart by id (Wave 1b).

        Cascades on ``consultations`` (FK ondelete=CASCADE) and on
        ``events`` (same). Sets ``charts.partner_chart_id = NULL`` on
        any chart that referenced this one as a partner (FK ondelete
        SET NULL — from Wave 6 migration).

        Returns True if a row was actually deleted, False if the id
        didn't exist. Caller decides whether to surface a «not found»
        message; the bot handler shows an alert in that case.
        """
        result = await session.execute(sa.delete(Chart).where(Chart.id == chart_id))
        # rowcount is dialect-dependent — Postgres always returns it; for
        # mocks in tests we coerce to int defensively.
        return bool(getattr(result, "rowcount", 0))

    async def set_partner(
        self,
        session: AsyncSession,
        *,
        owner_chart_id: uuid.UUID,
        partner_chart_id: uuid.UUID,
    ) -> None:
        """Link a partner chart to an owner chart for the relationships
        skill (Wave 6 / ADR-010). Both charts must belong to the same
        user — enforced by the bot handler, not the DB.

        Idempotent: setting the same partner_chart_id twice is a no-op
        beyond updating the row. Caller should commit/flush as needed."""
        await session.execute(
            sa.update(Chart)
            .where(Chart.id == owner_chart_id)
            .values(partner_chart_id=partner_chart_id)
        )

    async def set_default_school(
        self,
        session: AsyncSession,
        chart_id: uuid.UUID,
        school: str | None,
    ) -> None:
        """Set (or clear) the chart's default interpretation school
        (Wave 7 / 1.18.14). ``school`` must be one of classic|edoha|modern
        or ``None`` to clear (ask every time). Whitelist validation is the
        caller's responsibility. Caller commits/flushes."""
        await session.execute(
            sa.update(Chart).where(Chart.id == chart_id).values(default_school=school)
        )


def _coarse_key(chart: Chart) -> tuple[Any, ...]:
    """Group key that ignores birth time but keeps everything that
    legitimately makes a chart different."""
    gender = None
    if chart.chart_data:
        gender = (chart.chart_data.get("input") or {}).get("gender")
    return (
        chart.birth_datetime_original.date(),
        round(chart.latitude, 3),
        round(chart.longitude, 3),
        gender,
    )


def _pick_best_in_group(group: list[Chart]) -> list[Chart]:
    """Within a same-date+place+gender group, dedup by birth time and pick the
    most informative variant. With-time entries always dominate time-less ones.
    Same exact time collapses to one chart, preferring user-named + newest."""
    with_time = [c for c in group if c.has_birth_time]
    pool = with_time if with_time else group

    by_time: dict[Any, list[Chart]] = {}
    for chart in pool:
        time_key = chart.birth_datetime_original.time() if chart.has_birth_time else None
        by_time.setdefault(time_key, []).append(chart)

    picked: list[Chart] = []
    for variants in by_time.values():
        # Sort: user-named first (commaless), then newest. variants[0] wins.
        variants.sort(
            key=lambda c: (
                c.name is None or "," in (c.name or ""),
                -c.created_at.timestamp(),
            )
        )
        picked.append(variants[0])
    return picked
