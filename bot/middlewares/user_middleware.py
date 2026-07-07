from collections.abc import Awaitable, Callable
from typing import Any

import structlog
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from aiogram.types import User as TelegramUser
from sqlalchemy.ext.asyncio import AsyncSession

from db.repositories.user_repo import UserRepository

logger = structlog.get_logger(__name__)


class UserMiddleware(BaseMiddleware):
    def __init__(self) -> None:
        self._repo = UserRepository()

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:  # noqa: ANN401  -- aiogram middleware returns whatever the handler returns
        tg_user: TelegramUser | None = data.get("event_from_user")
        if tg_user is None or tg_user.is_bot:
            return await handler(event, data)

        session: AsyncSession = data["session"]
        user, created = await self._repo.get_or_create(
            session,
            telegram_id=tg_user.id,
            first_name=tg_user.first_name,
            username=tg_user.username,
        )
        data["user"] = user
        if created:
            logger.info("user.created", telegram_id=tg_user.id, user_id=str(user.id))
        return await handler(event, data)
