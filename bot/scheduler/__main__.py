"""Entry point: ``python -m bot.scheduler``.

Started by the ``scheduler`` Docker service in docker-compose.yml. The
main bot container is unchanged — it stays polling-only."""

from __future__ import annotations

import asyncio

from bot.scheduler.runner import run_scheduler


def main() -> None:
    asyncio.run(run_scheduler())


if __name__ == "__main__":
    main()
