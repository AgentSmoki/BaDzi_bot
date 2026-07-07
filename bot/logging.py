import logging
import sys

import structlog
from structlog.types import Processor

from bot.config import get_settings

_configured: bool = False


def configure_logging() -> None:
    global _configured
    if _configured:
        return

    settings = get_settings()

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    renderer: Processor = (
        structlog.dev.ConsoleRenderer(colors=True)
        if settings.environment == "development"
        else structlog.processors.JSONRenderer()
    )

    level_no = logging.getLevelNamesMapping()[settings.log_level]

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(level_no),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    logging.basicConfig(
        level=level_no,
        format="%(message)s",
        stream=sys.stdout,
        force=True,
    )

    _configured = True


def bind_trace_id(trace_id: str) -> None:
    structlog.contextvars.bind_contextvars(trace_id=trace_id)


def clear_context() -> None:
    structlog.contextvars.clear_contextvars()
