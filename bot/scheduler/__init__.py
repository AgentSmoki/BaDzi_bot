"""Wave 3c — APScheduler service for paid forecast delivery.

Lives in its own Docker container (``scheduler`` in docker-compose).
APScheduler ``AsyncIOScheduler`` + ``SQLAlchemyJobStore`` on Postgres
so scheduled jobs survive restarts. The bot container stays polling-
only and never schedules anything itself.

Architecture (research via Dev_Architect/research_tool 2026-05-19):
- Sync psycopg2 URL for the jobstore (APScheduler doesn't bind to
  asyncpg). Derived from settings.database_url.
- ``rebuild_jobs_for_all_subs`` runs at startup and every 5 minutes;
  it diffs DB-state against in-memory jobs so new purchases or
  cancellations propagate without bouncing the container.
- Daily: ``CronTrigger(hour=daily_send_hour_utc, minute=0,
  timezone=UTC)`` per subscription.
- Monthly weekly: 4x ``DateTrigger`` at +0, +7, +14, +21 days from
  purchase.
- Monthly bulk: one ``DateTrigger`` ~60 s after purchase (so the
  user sees their forecast right after buying).
- Dedup: ``ForecastDelivery.slot_key`` UNIQUE constraint protects
  against double-send on scheduler-container restart.
"""

from __future__ import annotations

from bot.scheduler.jobs import (
    build_daily_slot_key,
    build_monthly_slot_key,
    send_daily_forecast_job,
    send_monthly_forecast_job,
)
from bot.scheduler.runner import (
    derive_sync_db_url,
    rebuild_jobs_for_all_subs,
    run_scheduler,
)

__all__ = [
    "build_daily_slot_key",
    "build_monthly_slot_key",
    "derive_sync_db_url",
    "rebuild_jobs_for_all_subs",
    "run_scheduler",
    "send_daily_forecast_job",
    "send_monthly_forecast_job",
]
