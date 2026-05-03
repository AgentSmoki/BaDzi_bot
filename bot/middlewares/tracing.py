from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

import structlog
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, User

from bot.logging import bind_trace_id, clear_context

logger = structlog.get_logger(__name__)


class TracingMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:  # noqa: ANN401  -- aiogram middleware returns whatever the handler returns
        trace_id = str(uuid4())
        bind_trace_id(trace_id)
        data["trace_id"] = trace_id

        # TODO: hash user_id for public logs once PII policy lands.
        user: User | None = data.get("event_from_user")
        logger.info(
            "telegram.update_received",
            event_type=type(event).__name__,
            user_id=user.id if user else None,
        )

        try:
            return await handler(event, data)
        except Exception:
            logger.exception("telegram.update_failed", event_type=type(event).__name__)
            raise
        finally:
            clear_context()
