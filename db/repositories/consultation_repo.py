import uuid
from datetime import UTC, datetime
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Consultation

_DEFAULT_LIST_LIMIT: int = 50


class ConsultationRepository:
    async def create(
        self,
        session: AsyncSession,
        *,
        user_id: uuid.UUID,
        chart_id: uuid.UUID,
        user_message: str,
        ai_response: str,
        model_used: str,
        trace_id: str,
        topic: str | None = None,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        cost_usd: Decimal = Decimal("0"),
        latency_ms: int = 0,
    ) -> Consultation:
        consultation = Consultation(
            user_id=user_id,
            chart_id=chart_id,
            topic=topic,
            user_message=user_message,
            ai_response=ai_response,
            model_used=model_used,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost_usd,
            latency_ms=latency_ms,
            trace_id=trace_id,
        )
        session.add(consultation)
        await session.flush()
        return consultation

    async def list_by_user(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        limit: int = _DEFAULT_LIST_LIMIT,
    ) -> list[Consultation]:
        result = await session.execute(
            sa.select(Consultation)
            .where(Consultation.user_id == user_id)
            .order_by(Consultation.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    async def count_today_by_user(self, session: AsyncSession, user_id: uuid.UUID) -> int:
        today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        result = await session.execute(
            sa.select(sa.func.count())
            .select_from(Consultation)
            .where(
                Consultation.user_id == user_id,
                Consultation.created_at >= today_start,
            )
        )
        return result.scalar_one()
