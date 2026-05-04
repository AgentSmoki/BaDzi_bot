import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import Subscription, SubscriptionPlan, SubscriptionStatus


class SubscriptionRepository:
    async def get_by_user_id(
        self, session: AsyncSession, user_id: uuid.UUID
    ) -> Subscription | None:
        result = await session.execute(
            sa.select(Subscription).where(Subscription.user_id == user_id)
        )
        return result.scalar_one_or_none()

    async def create_free(self, session: AsyncSession, user_id: uuid.UUID) -> Subscription:
        subscription = Subscription(
            user_id=user_id,
            plan=SubscriptionPlan.free,
            status=SubscriptionStatus.active,
        )
        session.add(subscription)
        await session.flush()
        return subscription

    async def update_plan(
        self,
        session: AsyncSession,
        user_id: uuid.UUID,
        *,
        plan: SubscriptionPlan,
        status: SubscriptionStatus = SubscriptionStatus.active,
        expires_at: datetime | None = None,
        payment_provider: str | None = None,
    ) -> Subscription:
        sub = await self.get_by_user_id(session, user_id)
        if sub is None:
            sub = Subscription(user_id=user_id)
            session.add(sub)

        sub.plan = plan
        sub.status = status
        sub.payment_provider = payment_provider

        if plan == SubscriptionPlan.monthly or plan == SubscriptionPlan.quarterly:
            sub.monthly_expires_at = expires_at
        elif plan == SubscriptionPlan.annual:
            sub.monthly_expires_at = expires_at

        await session.flush()
        return sub
