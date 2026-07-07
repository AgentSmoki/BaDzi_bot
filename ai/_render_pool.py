"""Lazy ProcessPoolExecutor for SVG → PNG rendering.

CairoSVG + Pillow are GIL-bound C extensions; pushing renders into a
process pool keeps the asyncio event loop free for I/O while letting
the CPU spend full cores on rasterisation. Pool is created on first
use and reused for the lifetime of the process.

Pool size resolution order:
1. Env ``RENDER_POOL_SIZE`` (positive int) — explicit override.
2. ``max(1, os.cpu_count() // 2)`` — leave half the cores for asyncio
   plus everything else running in the main process.
"""

from __future__ import annotations

import asyncio
import os
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor
from functools import partial
from threading import Lock
from typing import Any, Final, TypeVar

import structlog

T = TypeVar("T")

logger = structlog.get_logger(__name__)

_pool: ProcessPoolExecutor | None = None
_pool_size: int = 0
_pool_lock: Final = Lock()


def _resolve_pool_size() -> int:
    raw = os.environ.get("RENDER_POOL_SIZE", "").strip()
    if raw:
        try:
            n = int(raw)
            if n > 0:
                return n
        except ValueError:
            pass
    cpu = os.cpu_count() or 2
    return max(1, cpu // 2)


def get_render_pool() -> ProcessPoolExecutor:
    """Return the singleton render pool, creating it on first call."""
    global _pool, _pool_size
    if _pool is not None:
        return _pool
    with _pool_lock:
        if _pool is None:
            _pool_size = _resolve_pool_size()
            _pool = ProcessPoolExecutor(max_workers=_pool_size)
            logger.info("render_pool.started", workers=_pool_size)
    return _pool


def get_pool_size() -> int:
    """Return the worker count of the active pool (0 if not started)."""
    return _pool_size


def shutdown_render_pool() -> None:
    """Idempotent shutdown — safe to call from app lifecycle hooks."""
    global _pool, _pool_size
    with _pool_lock:
        if _pool is not None:
            _pool.shutdown(wait=False, cancel_futures=True)
            _pool = None
            _pool_size = 0
            logger.info("render_pool.stopped")


async def run_in_pool(fn: Callable[..., T], *args: Any, **kwargs: Any) -> T:  # noqa: ANN401
    """Schedule *fn* in the render pool and await the result.

    Wraps the executor call so callers don't have to thread the loop
    through their code. ``functools.partial`` is used internally so
    keyword arguments survive the executor hand-off.
    """
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(get_render_pool(), partial(fn, *args, **kwargs))
