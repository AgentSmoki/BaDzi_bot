"""Repository for master-meeting transcripts (Wave 5)."""

from __future__ import annotations

import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import MasterMeeting, MasterMeetingSource, MasterMeetingStatus


class MasterMeetingRepository:
    async def create_queued(
        self,
        session: AsyncSession,
        *,
        user_id: uuid.UUID,
        chart_id: uuid.UUID,
        source_url: str,
        source_type: MasterMeetingSource,
        title: str | None = None,
    ) -> MasterMeeting:
        """Insert a new meeting row in ``queued`` status. The background
        worker picks it up, sets ``transcribing``, then ``ready``/``failed``."""
        meeting = MasterMeeting(
            user_id=user_id,
            chart_id=chart_id,
            source_url=source_url,
            source_type=source_type,
            title=title,
            status=MasterMeetingStatus.queued,
        )
        session.add(meeting)
        await session.flush()
        return meeting

    async def get_by_id(self, session: AsyncSession, meeting_id: uuid.UUID) -> MasterMeeting | None:
        return await session.get(MasterMeeting, meeting_id)

    async def list_by_chart(
        self, session: AsyncSession, chart_id: uuid.UUID
    ) -> list[MasterMeeting]:
        """Newest-first for the per-chart «my meetings» list."""
        result = await session.execute(
            sa.select(MasterMeeting)
            .where(MasterMeeting.chart_id == chart_id)
            .order_by(MasterMeeting.uploaded_at.desc())
        )
        return list(result.scalars().all())

    async def list_ready_summaries(
        self, session: AsyncSession, chart_id: uuid.UUID, *, limit: int = 5
    ) -> list[MasterMeeting]:
        """Summaries Anastasia injects into ``[MASTER_MEETING_NOTES]``.

        Newest first, capped at ``limit`` — typical chat budget can
        afford 3-5 short summaries before exceeding context."""
        result = await session.execute(
            sa.select(MasterMeeting)
            .where(
                MasterMeeting.chart_id == chart_id,
                MasterMeeting.status == MasterMeetingStatus.ready,
                MasterMeeting.summary.is_not(None),
            )
            .order_by(MasterMeeting.uploaded_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_status(
        self,
        session: AsyncSession,
        *,
        meeting_id: uuid.UUID,
        status: MasterMeetingStatus,
        transcript: str | None = None,
        summary: str | None = None,
        duration_seconds: int | None = None,
        error: str | None = None,
    ) -> None:
        """Single-shot update from the background worker."""
        values: dict[str, object] = {"status": status}
        if transcript is not None:
            values["transcript"] = transcript
        if summary is not None:
            values["summary"] = summary
        if duration_seconds is not None:
            values["duration_seconds"] = duration_seconds
        if error is not None:
            values["error"] = error
        if status == MasterMeetingStatus.ready:
            values["transcribed_at"] = datetime.now()
        await session.execute(
            sa.update(MasterMeeting).where(MasterMeeting.id == meeting_id).values(**values)
        )

    async def delete(self, session: AsyncSession, meeting_id: uuid.UUID) -> bool:
        result = await session.execute(
            sa.delete(MasterMeeting).where(MasterMeeting.id == meeting_id)
        )
        return bool(getattr(result, "rowcount", 0))
