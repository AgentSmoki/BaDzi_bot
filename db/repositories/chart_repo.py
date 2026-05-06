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

    async def update_name(
        self, session: AsyncSession, chart_id: uuid.UUID, name: str | None
    ) -> None:
        await session.execute(sa.update(Chart).where(Chart.id == chart_id).values(name=name))
