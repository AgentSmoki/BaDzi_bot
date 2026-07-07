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

    async def increment_free_questions(self, session: AsyncSession, user_id: uuid.UUID) -> int:
        """Wave 7 UX rework (2026-05-24): bump counter after each free
        consultation. Returns NEW count (1 after first, 2 after second,
        etc). Caller compares with ``settings.free_questions_limit``
        to render the «осталось N/3» footer or trigger the pricing
        screen on the next turn."""
        result = await session.execute(
            sa.update(User)
            .where(User.id == user_id)
            .values(free_questions_used=User.free_questions_used + 1)
            .returning(User.free_questions_used)
        )
        return int(result.scalar_one())

    async def reset_free_questions(self, session: AsyncSession, user_id: uuid.UUID) -> None:
        """Drop the counter back to zero. Used by ``handle_pricing_skip``
        — пока ЮКасса не подключена, кнопка «Продолжить бесплатно»
        доступна всем (не только admin как раньше). После подключения
        оплаты — метод вызывает только webhook успешной транзакции."""
        await session.execute(
            sa.update(User).where(User.id == user_id).values(free_questions_used=0)
        )
