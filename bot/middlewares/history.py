"""Inject the singleton HistoryStore into every handler's data dict.

Single shared instance for the whole process — Redis connection
pool is created lazily on first use and reused across handlers.
``bot.main`` constructs the store at startup and tears it down on
shutdown, so the middleware just hands the instance through.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject

from ai.context import HistoryStore


class HistoryMiddleware(BaseMiddleware):
    def __init__(self, store: HistoryStore) -> None:
        self._store = store

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:  # noqa: ANN401
        data["history_store"] = self._store
        return await handler(event, data)
