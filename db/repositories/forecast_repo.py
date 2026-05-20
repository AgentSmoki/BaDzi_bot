"""Repository for chart forecast subscriptions + delivery log (Wave 3).

Two responsibilities:
- ``ChartForecastSubscriptionRepository`` — buy/get/list/expire paid
  per-chart forecast plans (monthly 500₽ / daily 900₽).
- ``ForecastDeliveryRepository`` — record what's been sent so the
  scheduler can dedup on retries and surface a per-user history.

While ЮKassa isn't connected (см. ``settings.forecast_free_bypass``
and CHANGELOG in MASTER.md), ``create`` accepts
``payment_provider="free_dev_bypass"`` and skips the payment check.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import (
    ChartForecastSubscription,
    ForecastDelivery,
    ForecastKind,
    MonthlyDelivery,
    SubscriptionStatus,
)


class ChartForecastSubscriptionRepository:
    async def create(
        self,
        session: AsyncSession,
        *,
        user_id: uuid.UUID,
        chart_id: uuid.UUID,
        kind: ForecastKind,
        price_rub: int,
        monthly_delivery: MonthlyDelivery | None = None,
        daily_send_hour_utc: int | None = None,
        payment_provider: str | None = None,
        period_days: int = 30,
    ) -> ChartForecastSubscription:
        """Create a new subscription. Both ``monthly`` and ``daily`` are
        30-day periods by default — adjust ``period_days`` for promos.

        - ``monthly``: requires ``monthly_delivery`` (weekly|bulk).
        - ``daily``: requires ``daily_send_hour_utc`` (0-23).
        Caller validates these before invoking; we don't double-check
        here because the kind/delivery combo is set in the UI handler.
        """
        now = datetime.now(tz=None)
        sub = ChartForecastSubscription(
            user_id=user_id,
            chart_id=chart_id,
            kind=kind,
            monthly_delivery=monthly_delivery,
            daily_send_hour_utc=daily_send_hour_utc,
            status=SubscriptionStatus.active,
            started_at=now,
            expires_at=now + timedelta(days=period_days),
            price_rub=price_rub,
            payment_provider=payment_provider,
        )
        session.add(sub)
        await session.flush()
        return sub

    async def get_by_id(
        self, session: AsyncSession, subscription_id: uuid.UUID
    ) -> ChartForecastSubscription | None:
        return await session.get(ChartForecastSubscription, subscription_id)

    async def list_active_for_chart(
        self, session: AsyncSession, chart_id: uuid.UUID
    ) -> list[ChartForecastSubscription]:
        """All active, non-expired subscriptions for a single chart.
        A chart can have both monthly + daily simultaneously."""
        now = datetime.now(tz=None)
        result = await session.execute(
            sa.select(ChartForecastSubscription)
            .where(
                ChartForecastSubscription.chart_id == chart_id,
                ChartForecastSubscription.status == SubscriptionStatus.active,
                ChartForecastSubscription.expires_at > now,
            )
            .order_by(ChartForecastSubscription.created_at.desc())
        )
        return list(result.scalars().all())

    async def list_all_active(self, session: AsyncSession) -> list[ChartForecastSubscription]:
        """Scheduler-side: every active subscription across users.
        Called by the scheduler's rebuild_jobs sweep."""
        now = datetime.now(tz=None)
        result = await session.execute(
            sa.select(ChartForecastSubscription).where(
                ChartForecastSubscription.status == SubscriptionStatus.active,
                ChartForecastSubscription.expires_at > now,
            )
        )
        return list(result.scalars().all())

    async def cancel(self, session: AsyncSession, subscription_id: uuid.UUID) -> bool:
        """Mark cancelled. Idempotent: cancelling an already-cancelled
        row is a no-op; returns True iff the status flipped."""
        result = await session.execute(
            sa.update(ChartForecastSubscription)
            .where(
                ChartForecastSubscription.id == subscription_id,
                ChartForecastSubscription.status == SubscriptionStatus.active,
            )
            .values(status=SubscriptionStatus.cancelled)
        )
        return bool(getattr(result, "rowcount", 0))


class ForecastDeliveryRepository:
    async def record(
        self,
        session: AsyncSession,
        *,
        subscription_id: uuid.UUID,
        slot_key: str,
        content: str,
    ) -> ForecastDelivery | None:
        """Insert a delivery record. Returns ``None`` if the unique
        constraint (subscription_id, slot_key) blocks the insert —
        i.e. this slot was already recorded by a previous scheduler
        tick. Caller can skip the send.

        The actual ``sent_at`` is filled by ``mark_sent`` after the
        Telegram send succeeds, so a crash between record and send
        will leave the row with sent_at=NULL — the scheduler can
        retry by querying ``WHERE sent_at IS NULL``."""
        delivery = ForecastDelivery(
            subscription_id=subscription_id,
            slot_key=slot_key,
            content=content,
            sent_at=None,
            error=None,
        )
        session.add(delivery)
        try:
            await session.flush()
        except sa.exc.IntegrityError:
            await session.rollback()
            return None
        return delivery

    async def mark_sent(self, session: AsyncSession, delivery_id: uuid.UUID) -> None:
        await session.execute(
            sa.update(ForecastDelivery)
            .where(ForecastDelivery.id == delivery_id)
            .values(sent_at=datetime.now(tz=None))
        )

    async def mark_error(self, session: AsyncSession, delivery_id: uuid.UUID, error: str) -> None:
        await session.execute(
            sa.update(ForecastDelivery)
            .where(ForecastDelivery.id == delivery_id)
            .values(error=error)
        )

    async def get_by_slot(
        self,
        session: AsyncSession,
        *,
        subscription_id: uuid.UUID,
        slot_key: str,
    ) -> ForecastDelivery | None:
        """Lookup an existing delivery for a (sub, slot) pair.
        Used by the scheduler to check "already sent?" before
        regenerating LLM content."""
        result = await session.execute(
            sa.select(ForecastDelivery).where(
                ForecastDelivery.subscription_id == subscription_id,
                ForecastDelivery.slot_key == slot_key,
            )
        )
        return result.scalar_one_or_none()
