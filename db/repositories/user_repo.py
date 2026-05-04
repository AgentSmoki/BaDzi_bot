import uuid

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import User


class UserRepository:
    async def get_by_telegram_id(self, session: AsyncSession, telegram_id: int) -> User | None:
        result = await session.execute(sa.select(User).where(User.telegram_id == telegram_id))
        return result.scalar_one_or_none()

    async def get_by_id(self, session: AsyncSession, user_id: uuid.UUID) -> User | None:
        return await session.get(User, user_id)

    async def create(
        self,
        session: AsyncSession,
        *,
        telegram_id: int,
        first_name: str,
        username: str | None = None,
        locale: str = "ru",
    ) -> User:
        user = User(
            telegram_id=telegram_id,
            first_name=first_name,
            username=username,
            locale=locale,
        )
        session.add(user)
        await session.flush()
        return user

    async def get_or_create(
        self,
        session: AsyncSession,
        *,
        telegram_id: int,
        first_name: str,
        username: str | None = None,
    ) -> tuple[User, bool]:
        # SELECT FOR UPDATE prevents race condition on concurrent /start
        result = await session.execute(
            sa.select(User).where(User.telegram_id == telegram_id).with_for_update(skip_locked=True)
        )
        user = result.scalar_one_or_none()
        if user is not None:
            return user, False

        user = await self.create(
            session,
            telegram_id=telegram_id,
            first_name=first_name,
            username=username,
        )
        return user, True

    async def mark_free_question_used(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        await session.execute(
            sa.update(User).where(User.id == user_id).values(free_question_used=True)
        )
