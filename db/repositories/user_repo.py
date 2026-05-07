import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import insert as pg_insert
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
        # Postgres-specific upsert keeps two concurrent /start handlers from
        # both racing to INSERT and one losing to UniqueViolationError. The
        # SELECT-then-INSERT approach with FOR UPDATE SKIP LOCKED used to
        # silently let one handler skip the lock and re-insert.
        stmt = (
            pg_insert(User)
            .values(telegram_id=telegram_id, first_name=first_name, username=username)
            .on_conflict_do_nothing(index_elements=[User.telegram_id])
            .returning(User.id)
        )
        result = await session.execute(stmt)
        inserted_id = result.scalar_one_or_none()
        if inserted_id is not None:
            user = await session.get(User, inserted_id)
            assert user is not None
            return user, True

        # Row already existed — fetch it. Safe because telegram_id is unique.
        existing = await session.execute(sa.select(User).where(User.telegram_id == telegram_id))
        return existing.scalar_one(), False

    async def mark_free_question_used(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        await session.execute(
            sa.update(User).where(User.id == user_id).values(free_question_used=True)
        )
