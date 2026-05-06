import asyncio

import structlog
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.redis import RedisStorage

from bot.config import Settings, get_settings
from bot.logging import configure_logging
from bot.middlewares import DbSessionMiddleware, TracingMiddleware, UserMiddleware
from db.engine import get_engine

logger = structlog.get_logger(__name__)


def _build_bot(settings: Settings) -> Bot:
    return Bot(
        token=settings.bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )


def _build_dispatcher(settings: Settings) -> Dispatcher:
    storage = RedisStorage.from_url(settings.redis_url)
    dispatcher = Dispatcher(storage=storage)
    dispatcher.update.outer_middleware(TracingMiddleware())
    dispatcher.update.outer_middleware(DbSessionMiddleware())
    dispatcher.update.outer_middleware(UserMiddleware())
    _include_routers(dispatcher)
    return dispatcher


def _include_routers(dispatcher: Dispatcher) -> None:
    # Routers are wired starting from task 1.6.1 (start_router).
    return


async def _shutdown(bot: Bot, dispatcher: Dispatcher) -> None:
    await dispatcher.storage.close()
    await bot.session.close()
    await get_engine().dispose()


async def main() -> None:
    configure_logging()
    settings = get_settings()
    bot = _build_bot(settings)
    dispatcher = _build_dispatcher(settings)

    logger.info("bot.start", environment=settings.environment)
    try:
        await bot.delete_webhook(drop_pending_updates=True)
        await dispatcher.start_polling(bot)
    finally:
        logger.info("bot.shutdown")
        await _shutdown(bot, dispatcher)


if __name__ == "__main__":
    asyncio.run(main())
