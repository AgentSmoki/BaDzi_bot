"""TaskIQ broker — Redis pub/sub + result backend.

Single ``broker`` instance imported by both producers (handlers in
``bot/routers/*``) and the worker process (``taskiq worker
tasks.broker:broker``). Same Redis instance carries the queue *and*
result storage so we don't have to manage two connection strings.

Why TaskIQ over a direct asyncio.Task:
- LLM calls take 30-60s on K2.6 thinking. Holding the aiogram update
  handler open that long means a worker process per concurrent
  consultation, and Telegram retries the update if we don't ACK
  fast enough.
- TaskIQ lets us return immediately, run the LLM in a worker, and
  push the result back to the user via ``send_message``.

Initialisation pattern: tasks live in ``tasks/`` modules and
register themselves on the broker via ``@broker.task``. The worker
imports ``tasks.broker:broker`` and the registry comes along by
side-effect (each task module is imported by ``tasks/__init__.py``).
"""

from __future__ import annotations

from taskiq_redis import ListQueueBroker, RedisAsyncResultBackend

from bot.config import get_settings

_settings = get_settings()

# Result backend — stores task return values keyed by task_id, TTL
# kept tight (1h) since we only consume them once via wait_result.
_result_backend: RedisAsyncResultBackend[object] = RedisAsyncResultBackend(
    redis_url=_settings.redis_url,
    result_ex_time=60 * 60,
)

# ListQueueBroker uses LPUSH/BRPOP — first-in-first-out, simple and
# fast for our scale (~10 tasks/sec at peak). For higher throughput
# or multiple priorities we'd switch to streams; not needed yet.
broker = ListQueueBroker(url=_settings.redis_url).with_result_backend(_result_backend)


__all__ = ["broker"]
