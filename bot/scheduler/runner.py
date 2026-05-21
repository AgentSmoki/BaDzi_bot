"""Scheduler service entry point + job-rebuild loop.

Spawned as a separate Docker service (``scheduler`` in docker-compose).
Runs forever; the only side effect is APScheduler firing forecast jobs
at their scheduled times.
"""

from __future__ import annotations

import asyncio
import re
import uuid
from datetime import datetime, timedelta
from typing import Any

import structlog
from apscheduler.jobstores.sqlalchemy import SQLAlchemyJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from sqlalchemy.ext.asyncio import async_sessionmaker

from bot.config import get_settings
from bot.scheduler.jobs import (
    scan_important_dates_job,
    send_daily_forecast_job,
    send_journal_reminder_job,
    send_monthly_forecast_job,
)
from db.engine import get_engine
from db.models import ChartForecastSubscription, ForecastKind, MonthlyDelivery
from db.repositories.forecast_repo import ChartForecastSubscriptionRepository
from db.repositories.journal_repo import ChartJournalSettingsRepository

logger = structlog.get_logger(__name__)

# How often the rebuild loop walks the DB looking for new / cancelled
# subscriptions. 5 minutes matches the research recommendation — short
# enough that a new daily subscriber gets fired up before tomorrow's
# 04:00, long enough that DB load is negligible.
_REBUILD_INTERVAL_SECONDS = 300


def derive_sync_db_url(async_url: str) -> str:
    """Convert ``postgresql+asyncpg://...`` to ``postgresql+psycopg2://...``.

    APScheduler's ``SQLAlchemyJobStore`` uses a sync engine — it doesn't
    bind to asyncpg. Same Postgres instance, same DB, different driver.

    Driver-specific query params also need translation:
    - asyncpg uses ``ssl=<mode>``
    - psycopg2 uses ``sslmode=<mode>``
    Otherwise psycopg2 raises ``invalid dsn: invalid connection option
    "ssl"`` (we hit this exact crash on YC Managed PG deploy 2026-05-20).
    """
    sync = re.sub(r"^postgresql\+asyncpg://", "postgresql+psycopg2://", async_url, count=1)
    # Translate asyncpg's ssl=... → psycopg2's sslmode=... (covers both
    # ``?ssl=require`` standalone and ``&ssl=require`` mid-querystring).
    sync = re.sub(r"([?&])ssl=", r"\1sslmode=", sync)
    return sync


def _job_id_for_daily(subscription_id: str) -> str:
    return f"forecast_daily:{subscription_id}"


def _job_id_for_monthly_week(subscription_id: str, week: int) -> str:
    return f"forecast_monthly_week:{subscription_id}:w{week}"


def _job_id_for_monthly_bulk(subscription_id: str) -> str:
    return f"forecast_monthly_bulk:{subscription_id}"


def _build_trigger_for_subscription(
    sub: ChartForecastSubscription,
) -> list[tuple[str, Any, dict[str, Any]]]:
    """Return list of (job_id, trigger, kwargs) for a subscription.

    A monthly subscription expands into 1 trigger (bulk) or 4 triggers
    (weekly). A daily subscription expands into 1 cron trigger.
    """
    items: list[tuple[str, Any, dict[str, Any]]] = []

    if sub.kind == ForecastKind.daily:
        # CronTrigger fires every day at the configured UTC hour.
        hour = sub.daily_send_hour_utc or 4
        trigger = CronTrigger(hour=hour, minute=0, timezone="UTC")
        items.append(
            (
                _job_id_for_daily(str(sub.id)),
                trigger,
                {
                    "subscription_id": sub.id,
                    # ``target_date`` is computed at fire time — APScheduler
                    # will pass it; here we just pin a placeholder that the
                    # job overrides. Simpler: leave it out and the job
                    # computes ``date.today()`` itself. See jobs.py.
                },
            )
        )
        return items

    # Monthly — period starts at sub.started_at.date().
    period_start = sub.started_at.date()
    if sub.monthly_delivery == MonthlyDelivery.bulk:
        # Fire ~60s after purchase so the user sees the first message
        # while they're still in the chat.
        fire_at = max(sub.started_at, datetime.now()) + timedelta(seconds=60)
        items.append(
            (
                _job_id_for_monthly_bulk(str(sub.id)),
                DateTrigger(run_date=fire_at),
                {
                    "subscription_id": sub.id,
                    "period_start": period_start,
                    "week": None,
                },
            )
        )
    elif sub.monthly_delivery == MonthlyDelivery.weekly:
        for week in (1, 2, 3, 4):
            fire_at = sub.started_at + timedelta(days=7 * (week - 1))
            # Don't fire jobs for past weeks if the subscription is
            # being re-registered after a long-running restart.
            if fire_at < datetime.now() - timedelta(hours=1):
                continue
            items.append(
                (
                    _job_id_for_monthly_week(str(sub.id), week),
                    DateTrigger(run_date=fire_at),
                    {
                        "subscription_id": sub.id,
                        "period_start": period_start,
                        "week": week,
                    },
                )
            )
    return items


async def rebuild_jobs_for_all_subs(
    scheduler: AsyncIOScheduler,
    session_factory: async_sessionmaker[Any],
) -> int:
    """Walk all active subscriptions and (re)register their APScheduler
    jobs. Returns count of jobs reconciled.

    APScheduler ``add_job(replace_existing=True)`` makes this idempotent
    — already-scheduled jobs are updated in place, new ones get added,
    and jobs for cancelled subscriptions stay until expiry (we don't
    proactively remove since DateTriggers for the past are skipped by
    APScheduler anyway).
    """
    sub_repo = ChartForecastSubscriptionRepository()
    journal_settings_repo = ChartJournalSettingsRepository()
    count = 0
    async with session_factory() as session:
        subs = await sub_repo.list_all_active(session)
        journal_settings = await journal_settings_repo.list_enabled(session)

    # Wave 4e — single global cron at 09:00 UTC scans all charts with
    # `important_dates_enabled=True` for upcoming activations and pings
    # the user (rate-limited to ≤1/week per chart, handled inside the job).
    scheduler.add_job(
        scan_important_dates_job,
        trigger=CronTrigger(hour=9, minute=0, timezone="UTC"),
        id="important_dates:daily_scan",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    count += 1

    # Wave 4 — journal reminders: one cron per enabled-journal chart.
    # ⚠ APScheduler SQLAlchemyJobStore pickles kwargs into PG. ``Bot``
    # and ``async_sessionmaker`` carry SSL/engine state that doesn't
    # pickle. Pass only UUIDs / dates / ints — jobs build runtime
    # singletons themselves.
    for js in journal_settings:
        job_id = f"journal_reminder:{js.chart_id}"
        trigger = CronTrigger(hour=js.reminder_hour_utc, minute=0, timezone="UTC")
        scheduler.add_job(
            send_journal_reminder_job,
            trigger=trigger,
            kwargs={"chart_id": js.chart_id},
            id=job_id,
            replace_existing=True,
            misfire_grace_time=3600,
        )
        count += 1

    for sub in subs:
        triggers = _build_trigger_for_subscription(sub)
        for job_id, trigger, kwargs in triggers:
            if sub.kind == ForecastKind.daily:
                scheduler.add_job(
                    _fire_daily,
                    trigger=trigger,
                    kwargs={"subscription_id": sub.id},
                    id=job_id,
                    replace_existing=True,
                    misfire_grace_time=3600,
                )
            else:
                scheduler.add_job(
                    send_monthly_forecast_job,
                    trigger=trigger,
                    kwargs=kwargs,
                    id=job_id,
                    replace_existing=True,
                    misfire_grace_time=3600,
                )
            count += 1
    logger.info(
        "scheduler.rebuild_done",
        subscriptions=len(subs),
        journal_reminders=len(journal_settings),
        jobs=count,
    )
    return count


async def _fire_daily(*, subscription_id: uuid.UUID) -> None:
    """Daily cron wrapper — computes ``date.today()`` at fire time
    and delegates to the actual job (which builds Bot/session locally)."""
    from datetime import date

    await send_daily_forecast_job(
        subscription_id=subscription_id,
        target_date=date.today(),
    )


async def run_scheduler() -> None:
    """Entry point used by `python -m bot.scheduler`. Blocks forever.

    Builds:
    - SQLAlchemy jobstore on Postgres (sync URL)
    - AsyncIOScheduler with the jobstore
    - aiogram Bot instance for Telegram sends
    - Rebuild-jobs loop every 5 minutes
    """
    settings = get_settings()
    sync_db_url = derive_sync_db_url(settings.database_url)

    scheduler = AsyncIOScheduler(
        jobstores={"default": SQLAlchemyJobStore(url=sync_db_url)},
        timezone="UTC",
    )
    engine = get_engine()
    session_factory: async_sessionmaker[Any] = async_sessionmaker(engine, expire_on_commit=False)

    scheduler.start()
    logger.info("scheduler.started", sync_db_url_redacted=sync_db_url.split("@")[-1])

    # Initial rebuild + periodic rebuild loop. Bot is built inside each
    # job; the rebuild loop only needs the session_factory to read DB.
    await rebuild_jobs_for_all_subs(scheduler, session_factory)

    try:
        while True:
            await asyncio.sleep(_REBUILD_INTERVAL_SECONDS)
            try:
                await rebuild_jobs_for_all_subs(scheduler, session_factory)
            except Exception:
                logger.exception("scheduler.rebuild_failed")
    finally:
        scheduler.shutdown(wait=False)
