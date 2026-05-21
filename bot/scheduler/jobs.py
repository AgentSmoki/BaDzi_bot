"""Job functions executed by APScheduler.

These are the only pieces of bot business logic the scheduler service
runs — everything else (rebuild loop, trigger construction, lifecycle)
lives in ``runner.py``. Each job:
1. Resolves the subscription from the DB (might be cancelled).
2. Generates forecast via ``ai.forecast``.
3. Records ``ForecastDelivery`` with UNIQUE(sub, slot_key) — skips
   the actual Telegram send if the row already exists (rerun safety).
4. Sends to Telegram, marks sent_at or error.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Final

import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ai.forecast import (
    ForecastResult,
    generate_daily_forecast,
    generate_monthly_forecast,
)
from bot.config import get_settings
from calculator.models import ChartOutput
from db.engine import get_engine
from db.models import ForecastKind
from db.repositories.chart_repo import ChartRepository
from db.repositories.forecast_repo import (
    ChartForecastSubscriptionRepository,
    ForecastDeliveryRepository,
)

logger = structlog.get_logger(__name__)


# Wave 3c hotfix 2026-05-20: APScheduler SQLAlchemyJobStore pickles
# job kwargs into Postgres for persistence across restarts. ``Bot``
# (carries SSLContext) and ``async_sessionmaker`` (binds to an
# asyncpg engine) aren't picklable, so we MUST NOT pass them as
# kwargs. Each job function builds these locally at fire time via
# ``_make_bot()`` and ``_make_session_factory()``.


def _make_bot() -> Bot:
    """Fresh Bot per job — caller must ``await bot.session.close()``
    in a ``finally`` block."""
    return Bot(token=get_settings().bot_token.get_secret_value())


def _make_session_factory() -> async_sessionmaker[AsyncSession]:
    """Reuses the cached engine singleton from ``db.engine.get_engine``."""
    return async_sessionmaker(get_engine(), expire_on_commit=False)


_DELIVERY_HEADER: Final[dict[ForecastKind, str]] = {
    ForecastKind.daily: "🌅 <b>Прогноз дня и активации</b>",
    ForecastKind.monthly: "📅 <b>Прогноз на период</b>",
}


def build_daily_slot_key(target_date: date) -> str:
    """Daily slot key: ``daily:YYYY-MM-DD``."""
    return f"daily:{target_date.isoformat()}"


def build_journal_reminder_key(*, chart_id: str, target_date: date) -> str:
    """Wave 4 — journal reminders are per-chart, per-day."""
    return f"journal:{chart_id}:{target_date.isoformat()}"


def build_monthly_slot_key(*, period_start: date, week: int | None) -> str:
    """Monthly slot key.

    - ``week=None`` → ``monthly:YYYY-MM:bulk`` (single bulk send)
    - ``week=N`` (1-4) → ``monthly:YYYY-MM:weekN``
    """
    suffix = "bulk" if week is None else f"week{week}"
    return f"monthly:{period_start.strftime('%Y-%m')}:{suffix}"


async def _resolve_active_chart(
    session: AsyncSession,
    subscription_id: uuid.UUID,
) -> tuple[uuid.UUID, ChartOutput, int] | None:
    """Return (telegram_id, chart_output, chart_id) for an active
    subscription. ``None`` if cancelled or chart deleted."""
    sub_repo = ChartForecastSubscriptionRepository()
    sub = await sub_repo.get_by_id(session, subscription_id)
    if sub is None or sub.status.value != "active":
        return None
    if datetime.now() > sub.expires_at:
        return None

    chart_repo = ChartRepository()
    chart = await chart_repo.get_by_id(session, sub.chart_id)
    if chart is None or chart.chart_data is None:
        return None
    chart_output = ChartOutput.model_validate(chart.chart_data)
    # Telegram id lives on the user — load through chart.user_id directly
    # via a lazy fetch on the user row.
    return sub.chart_id, chart_output, sub.chart_id  # type: ignore[return-value]


async def _send_or_record_error(
    bot: Bot,
    *,
    telegram_id: int,
    text: str,
    delivery_id: uuid.UUID,
    session: AsyncSession,
) -> None:
    """Send to Telegram; on failure mark error on the delivery row so
    the user-facing «история прогнозов» сможет показать что было
    отправлено и что не дошло."""
    delivery_repo = ForecastDeliveryRepository()
    try:
        await bot.send_message(chat_id=telegram_id, text=text, parse_mode="HTML")
        await delivery_repo.mark_sent(session, delivery_id)
        logger.info("forecast.delivered", delivery_id=str(delivery_id))
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        await delivery_repo.mark_error(session, delivery_id, str(exc))
        logger.warning(
            "forecast.delivery_failed",
            delivery_id=str(delivery_id),
            error=str(exc),
            exc_type=type(exc).__name__,
        )


async def send_daily_forecast_job(
    *,
    subscription_id: uuid.UUID,
    target_date: date,
) -> None:
    """Generate and send a single daily forecast.

    APScheduler kwargs are pickled into the jobstore, so we accept only
    picklable args (UUID + date) and build Bot/session_factory locally.

    The function is idempotent: if a delivery for this (sub, slot)
    already exists with sent_at != NULL, we skip the LLM call.
    """
    slot_key = build_daily_slot_key(target_date)
    session_factory = _make_session_factory()
    bot = _make_bot()
    try:
        await _send_daily_forecast_inner(
            subscription_id=subscription_id,
            target_date=target_date,
            slot_key=slot_key,
            bot=bot,
            session_factory=session_factory,
        )
    finally:
        await bot.session.close()


async def _send_daily_forecast_inner(
    *,
    subscription_id: uuid.UUID,
    target_date: date,
    slot_key: str,
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    delivery_repo = ForecastDeliveryRepository()
    sub_repo = ChartForecastSubscriptionRepository()
    chart_repo = ChartRepository()

    async with session_factory() as session:
        # Skip if already delivered.
        existing = await delivery_repo.get_by_slot(
            session, subscription_id=subscription_id, slot_key=slot_key
        )
        if existing is not None and existing.sent_at is not None:
            logger.debug(
                "forecast.daily.skipped_already_sent",
                subscription_id=str(subscription_id),
                slot_key=slot_key,
            )
            return

        sub = await sub_repo.get_by_id(session, subscription_id)
        if sub is None or sub.status.value != "active":
            logger.info(
                "forecast.daily.skipped_inactive",
                subscription_id=str(subscription_id),
            )
            return
        if datetime.now() > sub.expires_at:
            logger.info(
                "forecast.daily.skipped_expired",
                subscription_id=str(subscription_id),
            )
            return

        chart = await chart_repo.get_by_id(session, sub.chart_id)
        if chart is None:
            logger.warning(
                "forecast.daily.chart_missing",
                subscription_id=str(subscription_id),
                chart_id=str(sub.chart_id),
            )
            return
        chart_output = ChartOutput.model_validate(chart.chart_data)

        forecast: ForecastResult = await generate_daily_forecast(
            chart=chart_output, target_date=target_date
        )

        # Render delivery body with header.
        header = _DELIVERY_HEADER[ForecastKind.daily]
        body = f"{header}\n\n{forecast.text}"

        # Insert delivery row (UNIQUE protects retry doubles).
        delivery = await delivery_repo.record(
            session,
            subscription_id=subscription_id,
            slot_key=slot_key,
            content=body,
        )
        await session.commit()
        if delivery is None:
            logger.debug(
                "forecast.daily.dedup_blocked",
                subscription_id=str(subscription_id),
                slot_key=slot_key,
            )
            return

    # Fresh session for the send + final write — keeps LLM call (which
    # held the session open for ~10-30s) decoupled from the network IO.
    async with session_factory() as session:
        # Re-fetch user via chart.user_id → users.telegram_id.
        sub = await sub_repo.get_by_id(session, subscription_id)
        if sub is None:
            return
        chart = await chart_repo.get_by_id(session, sub.chart_id)
        if chart is None:
            return
        from db.models import User

        user = await session.get(User, chart.user_id)
        telegram_id = getattr(user, "telegram_id", None) if user is not None else None
        if telegram_id is None:
            logger.warning(
                "forecast.daily.telegram_id_missing",
                subscription_id=str(subscription_id),
            )
            return
        await _send_or_record_error(
            bot,
            telegram_id=telegram_id,
            text=body,
            delivery_id=delivery.id,
            session=session,
        )
        await session.commit()


async def scan_important_dates_job() -> None:
    """Wave 4e — daily scan for upcoming «important dates» on charts
    that have ``important_dates_enabled=True``.

    Triggered by a single cron at 09:00 UTC. For each enabled chart:
    - look forward 0..2 days (today + 2 ahead)
    - if any ImportantDate falls in that window and the chart hasn't
      been notified within the last 7 days, send a notification
    - mark `last_important_date_at = now()` so we honour the
      ≤1/week rate limit

    No per-chart APScheduler jobs needed — one global cron walks the
    DB and decides who needs a ping. Cheap, idempotent (rate-limit
    keeps duplicates out across scheduler-container restarts).
    """
    from datetime import datetime, timedelta

    from calculator.important_dates import (
        find_important_dates_in_range,
        format_important_date_message,
    )
    from db.models import User
    from db.repositories.journal_repo import ChartJournalSettingsRepository

    session_factory = _make_session_factory()
    bot = _make_bot()
    chart_repo = ChartRepository()
    journal_settings_repo = ChartJournalSettingsRepository()

    try:
        async with session_factory() as session:
            enabled = await journal_settings_repo.list_important_dates_enabled(session)
            logger.info("important_dates.scan_start", enabled_charts=len(enabled))

            now = datetime.now()
            today = now.date()
            horizon_end = today + timedelta(days=2)
            week_ago = now - timedelta(days=7)

            for js in enabled:
                # Rate-limit ≤1/week so we don't spam on consecutive
                # activations (e.g. a stretch of 七杀 days back to back).
                if js.last_important_date_at and js.last_important_date_at > week_ago:
                    continue

                chart = await chart_repo.get_by_id(session, js.chart_id)
                if chart is None:
                    continue
                user = await session.get(User, chart.user_id)
                telegram_id = getattr(user, "telegram_id", None) if user is not None else None
                if telegram_id is None:
                    continue

                chart_data = ChartOutput.model_validate(chart.chart_data)
                hits = find_important_dates_in_range(chart_data, today, horizon_end)
                if not hits:
                    continue

                # Send only the soonest hit per scan to avoid burying
                # the user in a wall of forecasts. Subsequent hits get
                # picked up by next week's scan (or the day-of cron).
                hit = hits[0]
                days_ahead = (hit.date_ - today).days
                text = format_important_date_message(chart_data, hit, days_ahead=days_ahead)
                kb = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="📝 Записать рефлексию",
                                callback_data=f"journal:write:{chart.id}",
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text="◀ К карте",  # noqa: RUF001
                                callback_data=f"chart:open:{chart.id}",
                            )
                        ],
                    ]
                )
                try:
                    await bot.send_message(
                        chat_id=telegram_id,
                        text=text,
                        parse_mode="HTML",
                        reply_markup=kb,
                    )
                    await journal_settings_repo.mark_important_date_sent(session, chart.id)
                    logger.info(
                        "important_dates.notification_sent",
                        chart_id=str(chart.id),
                        telegram_id=telegram_id,
                        target_date=hit.date_.isoformat(),
                        severity=hit.severity,
                    )
                except (TelegramBadRequest, TelegramForbiddenError) as exc:
                    logger.warning(
                        "important_dates.notification_failed",
                        chart_id=str(chart.id),
                        error=str(exc),
                        exc_type=type(exc).__name__,
                    )
            await session.commit()
    finally:
        await bot.session.close()


async def send_journal_reminder_job(*, chart_id: uuid.UUID) -> None:
    """Wave 4 — daily reminder for the reflection journal.

    Fires at the per-chart configured local hour. Bot/session_factory
    built locally — APScheduler kwargs must be picklable.
    """
    from db.models import User
    from db.repositories.journal_repo import ChartJournalSettingsRepository

    session_factory = _make_session_factory()
    bot = _make_bot()
    chart_repo = ChartRepository()
    journal_settings_repo = ChartJournalSettingsRepository()

    async with session_factory() as session:
        chart = await chart_repo.get_by_id(session, chart_id)
        if chart is None:
            return
        settings = await journal_settings_repo.get_or_create(session, chart_id=chart_id)
        if not settings.enabled:
            return
        user = await session.get(User, chart.user_id)
        telegram_id = getattr(user, "telegram_id", None) if user is not None else None
        if telegram_id is None:
            return
        chart_label = chart.name or "вашей карты"

    text = (
        "<b>📔 Время записать рефлексию</b>\n\n"
        f"Как прошёл день для {chart_label}? Опишите своими словами текстом "
        "или запишите голосовое — я расшифрую и сохраню в дневник этой карты."
    )
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📝 Записать сегодня",
                    callback_data=f"journal:write:{chart_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Пропустить сегодня",
                    callback_data=f"journal:show:{chart_id}",
                )
            ],
        ]
    )

    try:
        await bot.send_message(chat_id=telegram_id, text=text, parse_mode="HTML", reply_markup=kb)
        logger.info(
            "journal.reminder_sent",
            chart_id=str(chart_id),
            telegram_id=telegram_id,
        )
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        logger.warning(
            "journal.reminder_failed",
            chart_id=str(chart_id),
            error=str(exc),
            exc_type=type(exc).__name__,
        )
    finally:
        await bot.session.close()


async def send_monthly_forecast_job(
    *,
    subscription_id: uuid.UUID,
    period_start: date,
    week: int | None,
) -> None:
    """Generate and send a monthly forecast.

    APScheduler kwargs are pickled → only picklable args accepted.
    Bot + session_factory built locally inside the job.

    ``week=None`` → bulk delivery (full month text).
    ``week=N`` (1-4) → weekly chunk — for now we send the full forecast
    each week (LLM repeats are cheap).
    """
    slot_key = build_monthly_slot_key(period_start=period_start, week=week)
    session_factory = _make_session_factory()
    bot = _make_bot()
    try:
        await _send_monthly_forecast_inner(
            subscription_id=subscription_id,
            period_start=period_start,
            week=week,
            slot_key=slot_key,
            bot=bot,
            session_factory=session_factory,
        )
    finally:
        await bot.session.close()


async def _send_monthly_forecast_inner(
    *,
    subscription_id: uuid.UUID,
    period_start: date,
    week: int | None,
    slot_key: str,
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    delivery_repo = ForecastDeliveryRepository()
    sub_repo = ChartForecastSubscriptionRepository()
    chart_repo = ChartRepository()

    async with session_factory() as session:
        existing = await delivery_repo.get_by_slot(
            session, subscription_id=subscription_id, slot_key=slot_key
        )
        if existing is not None and existing.sent_at is not None:
            return

        sub = await sub_repo.get_by_id(session, subscription_id)
        if sub is None or sub.status.value != "active":
            return
        if datetime.now() > sub.expires_at:
            return

        chart = await chart_repo.get_by_id(session, sub.chart_id)
        if chart is None:
            return
        chart_output = ChartOutput.model_validate(chart.chart_data)

        forecast = await generate_monthly_forecast(chart=chart_output, period_start=period_start)
        header_label = (
            f"{_DELIVERY_HEADER[ForecastKind.monthly]} — неделя {week}"
            if week is not None
            else _DELIVERY_HEADER[ForecastKind.monthly]
        )
        body = f"{header_label}\n\n{forecast.text}"

        delivery = await delivery_repo.record(
            session,
            subscription_id=subscription_id,
            slot_key=slot_key,
            content=body,
        )
        await session.commit()
        if delivery is None:
            return

    async with session_factory() as session:
        sub = await sub_repo.get_by_id(session, subscription_id)
        if sub is None:
            return
        chart = await chart_repo.get_by_id(session, sub.chart_id)
        if chart is None:
            return
        from db.models import User

        user = await session.get(User, chart.user_id)
        telegram_id = getattr(user, "telegram_id", None) if user is not None else None
        if telegram_id is None:
            return
        await _send_or_record_error(
            bot,
            telegram_id=telegram_id,
            text=body,
            delivery_id=delivery.id,
            session=session,
        )
        await session.commit()
