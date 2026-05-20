"""Tests for bot.scheduler — pure-logic only.

We don't spin up the real AsyncIOScheduler in unit tests (it would
need a running Postgres jobstore). Instead we test:
- ``derive_sync_db_url`` — URL transformation
- slot key builders (daily/monthly)
- ``_build_trigger_for_subscription`` — what triggers a sub produces
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from unittest.mock import MagicMock

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger

from bot.scheduler.jobs import build_daily_slot_key, build_monthly_slot_key
from bot.scheduler.runner import _build_trigger_for_subscription, derive_sync_db_url
from db.models import ForecastKind, MonthlyDelivery, SubscriptionStatus

# ── URL conversion ───────────────────────────────────────────────────────


def test_derive_sync_db_url_replaces_asyncpg() -> None:
    src = "postgresql+asyncpg://user:pwd@host:5432/dbname"
    assert derive_sync_db_url(src) == "postgresql+psycopg2://user:pwd@host:5432/dbname"


def test_derive_sync_db_url_idempotent_on_already_sync() -> None:
    """If somebody already passed a sync URL, leave it alone."""
    src = "postgresql+psycopg2://x:y@z/n"
    assert derive_sync_db_url(src) == src


def test_derive_sync_db_url_keeps_query_params() -> None:
    src = "postgresql+asyncpg://u:p@h/db?ssl=require"
    assert derive_sync_db_url(src) == "postgresql+psycopg2://u:p@h/db?ssl=require"


# ── Slot keys ────────────────────────────────────────────────────────────


def test_daily_slot_key_format() -> None:
    assert build_daily_slot_key(date(2026, 5, 19)) == "daily:2026-05-19"


def test_monthly_slot_key_bulk() -> None:
    assert (
        build_monthly_slot_key(period_start=date(2026, 6, 1), week=None) == "monthly:2026-06:bulk"
    )


def test_monthly_slot_key_weekly() -> None:
    assert build_monthly_slot_key(period_start=date(2026, 6, 1), week=3) == "monthly:2026-06:week3"


# ── Trigger construction ─────────────────────────────────────────────────


def _fake_sub(
    *,
    kind: ForecastKind,
    monthly_delivery: MonthlyDelivery | None = None,
    daily_send_hour_utc: int | None = None,
    started_at: datetime | None = None,
) -> MagicMock:
    sub = MagicMock()
    sub.id = uuid.uuid4()
    sub.kind = kind
    sub.monthly_delivery = monthly_delivery
    sub.daily_send_hour_utc = daily_send_hour_utc
    sub.status = SubscriptionStatus.active
    sub.started_at = started_at or datetime.now()
    sub.expires_at = sub.started_at + timedelta(days=30)
    return sub


def test_daily_subscription_produces_cron_trigger() -> None:
    sub = _fake_sub(kind=ForecastKind.daily, daily_send_hour_utc=1)
    items = _build_trigger_for_subscription(sub)
    assert len(items) == 1
    job_id, trigger, kwargs = items[0]
    assert "forecast_daily" in job_id
    assert isinstance(trigger, CronTrigger)
    assert kwargs["subscription_id"] == sub.id


def test_daily_subscription_defaults_to_hour_4_when_none() -> None:
    """If daily_send_hour_utc is missing in DB, fall back to 4 UTC."""
    sub = _fake_sub(kind=ForecastKind.daily, daily_send_hour_utc=None)
    items = _build_trigger_for_subscription(sub)
    trigger = items[0][1]
    # Trigger str representation contains hour='4' (we can't introspect
    # cron fields directly without poking at private state — but the
    # str repr is stable enough for a smoke check).
    assert "hour='4'" in str(trigger)


def test_monthly_bulk_subscription_produces_one_date_trigger() -> None:
    sub = _fake_sub(kind=ForecastKind.monthly, monthly_delivery=MonthlyDelivery.bulk)
    items = _build_trigger_for_subscription(sub)
    assert len(items) == 1
    job_id, trigger, kwargs = items[0]
    assert "forecast_monthly_bulk" in job_id
    assert isinstance(trigger, DateTrigger)
    assert kwargs["week"] is None


def test_monthly_weekly_subscription_produces_four_date_triggers() -> None:
    sub = _fake_sub(
        kind=ForecastKind.monthly,
        monthly_delivery=MonthlyDelivery.weekly,
    )
    items = _build_trigger_for_subscription(sub)
    assert len(items) == 4
    weeks = sorted(kwargs["week"] for _, _, kwargs in items)
    assert weeks == [1, 2, 3, 4]
    for _, trigger, _ in items:
        assert isinstance(trigger, DateTrigger)


def test_monthly_weekly_skips_past_weeks_after_restart() -> None:
    """If the scheduler container is recovering and the subscription
    was bought 21 days ago, weeks 1-3 should be skipped (their fire-at
    is in the past), only week 4 remains."""
    started_long_ago = datetime.now() - timedelta(days=21)
    sub = _fake_sub(
        kind=ForecastKind.monthly,
        monthly_delivery=MonthlyDelivery.weekly,
        started_at=started_long_ago,
    )
    items = _build_trigger_for_subscription(sub)
    weeks = sorted(kwargs["week"] for _, _, kwargs in items)
    assert weeks == [4]
