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

from ai.day_image import fetch_day_energy_image
from ai.forecast import (
    ForecastResult,
    generate_daily_forecast,
    generate_monthly_forecast,
)
from ai.prompts import SchoolName
from bot.config import get_settings
from bot.services.telegram_split import split_for_telegram
from calculator import calculate_chart
from calculator.models import ChartInput, ChartOutput
from db.engine import get_engine
from db.models import ChartForecastSubscription, ForecastKind
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


def _school_from_sub(sub: ChartForecastSubscription | None) -> SchoolName | None:
    """Достать ChartForecastSubscription.chosen_school как Literal-school.

    Возвращает None если sub нет или значение не в SchoolName Literal
    (например legacy-подписка с пустой строкой), чтобы forecast.py
    fall back на универсальный base.md. Wave 7 Phase 2 ext 2026-05-26.
    """
    if sub is None:
        return None
    value = (sub.chosen_school or "").strip().lower()
    if value in ("classic", "edoha", "modern"):
        return value  # type: ignore[return-value]
    return None


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
    hero_image_url: str | None = None,
) -> None:
    """Send to Telegram; on failure mark error on the delivery row so
    the user-facing «история прогнозов» сможет показать что было
    отправлено и что не дошло.

    Wave 7 Phase E: ``hero_image_url`` (опц.) — Unsplash-картинка
    под энергию столпа дня, отправляется как отдельное photo-сообщение
    перед текстом прогноза. Если ``None`` (Unsplash отключён / ошибка)
    — отправляем только текст как раньше.
    """
    delivery_repo = ForecastDeliveryRepository()
    try:
        if hero_image_url:
            # Photo first без caption — Telegram caption capped at 1024
            # chars, и текст прогноза часто длиннее. Картинка идёт как
            # «открывающий кадр», текст следом.
            try:
                await bot.send_photo(chat_id=telegram_id, photo=hero_image_url)
            except (TelegramBadRequest, TelegramForbiddenError) as photo_exc:
                # Картинка — украшение, не контракт. Падение тут не
                # должно блокировать доставку текста; логируем и идём
                # дальше.
                logger.warning(
                    "forecast.hero_image_failed",
                    delivery_id=str(delivery_id),
                    url=hero_image_url,
                    error=str(photo_exc),
                )
        # Split длинного текста на параграфы чтобы не словить
        # «Bad Request: message is too long» (Telegram cap 4096 chars).
        # Без split один длинный forecast → photo прошёл, текст упал →
        # клиент видит только картинку.
        chunks = split_for_telegram(text)
        for chunk in chunks:
            await bot.send_message(chat_id=telegram_id, text=chunk, parse_mode="HTML")
        await delivery_repo.mark_sent(session, delivery_id)
        logger.info(
            "forecast.delivered",
            delivery_id=str(delivery_id),
            had_hero_image=bool(hero_image_url),
            chunk_count=len(chunks),
        )
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

        # Re-use already-generated content when retrying a failed send.
        # См. forecast.monthly.reusing_existing_content fix — без этого
        # каждые 5 мин rebuild_jobs запускает новый LLM-вызов для
        # delivery row которая зависла без sent_at.
        if existing is not None and existing.content:
            body = existing.content
            logger.info(
                "forecast.daily.reusing_existing_content",
                subscription_id=str(subscription_id),
                slot_key=slot_key,
                delivery_id=str(existing.id),
            )
        else:
            forecast: ForecastResult = await generate_daily_forecast(
                chart=chart_output,
                target_date=target_date,
                school=_school_from_sub(sub),
            )

            # Render delivery body with header.
            header = _DELIVERY_HEADER[ForecastKind.daily]
            body = f"{header}\n\n{forecast.text}"

        # Wave 7 Phase E — Unsplash hero image на основе столпа дня
        # target_date. Берём день из synthetic noon-chart (тот же что
        # forecast.py использует для генерации текста), извлекаем
        # дневной столп, просим Unsplash картинку под энергии. Кэш
        # по stem+branch = одна картинка на день для всех юзеров.
        # При ошибке fetch_day_energy_image вернёт None → ниже
        # _send_or_record_error отправит только текст без картинки.
        try:
            day_chart = calculate_chart(
                ChartInput(
                    birth_datetime=datetime.combine(
                        target_date, datetime.min.time().replace(hour=12)
                    ),
                    latitude=0.0,
                    longitude=0.0,
                    tz_offset=0.0,
                    gender="male",
                )
            )
            day_pillar = day_chart.pillars[2]  # year=0, month=1, day=2, hour=3
            hero_image_url = await fetch_day_energy_image(day_pillar)
        except Exception as exc:
            logger.warning(
                "forecast.daily.hero_image_skipped",
                subscription_id=str(subscription_id),
                error=str(exc),
            )
            hero_image_url = None

        # Insert delivery row (UNIQUE protects retry doubles). If we
        # already have an existing row with content (failed previous send)
        # — re-use it instead of creating a new one.
        if existing is not None and existing.content:
            delivery = existing
        else:
            new_delivery = await delivery_repo.record(
                session,
                subscription_id=subscription_id,
                slot_key=slot_key,
                content=body,
            )
            await session.commit()
            if new_delivery is None:
                logger.debug(
                    "forecast.daily.dedup_blocked",
                    subscription_id=str(subscription_id),
                    slot_key=slot_key,
                )
                return
            delivery = new_delivery

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
            hero_image_url=hero_image_url,
        )
        await session.commit()


async def scan_important_dates_job() -> None:
    """Wave 4e — daily scan for upcoming «important dates» on charts
    that have ``important_dates_enabled=True``.

    Triggered by a single cron at 09:00 UTC. For each enabled chart:
    - look forward 1..2 days ahead
    - if any ImportantDate falls in that window and the chart hasn't
      been notified within the last 7 days, send a WARNING
    - mark `last_important_date_at = now()` so we honour the
      ≤1/week rate limit

    Wave 4e v2 (2026-06-10): этот скан шлёт ТОЛЬКО предупреждение
    (за 1-2 дня, утром — ок). Day-of приглашение записать рефлексию
    переехало в почасовой ``scan_reflection_prompts_job`` — оно
    приходит в 18:00 местного времени карты, когда день прожит.

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
                # Capture fields up-front: we commit per-chart below, which
                # expires ORM attributes — read what we need first.
                chart_id = js.chart_id
                last_warning_at = js.last_important_date_at
                last_warning_date = js.last_important_warning_date

                chart = await chart_repo.get_by_id(session, chart_id)
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

                # ── ahead-of-time WARNING (days_ahead 1..2) ──
                # Heads-up, no reflection button, ≤1/week + per-date dedup.
                ahead = [h for h in hits if h.date_ > today]
                warned_recently = bool(last_warning_at and last_warning_at > week_ago)
                if ahead and not warned_recently:
                    hit = ahead[0]
                    if last_warning_date != hit.date_:
                        days_ahead = (hit.date_ - today).days
                        text = format_important_date_message(chart_data, hit, days_ahead=days_ahead)
                        kb = InlineKeyboardMarkup(
                            inline_keyboard=[
                                [
                                    InlineKeyboardButton(
                                        text="◀ К карте",
                                        callback_data=f"chart:open:{chart_id}",
                                    )
                                ]
                            ]
                        )
                        try:
                            await bot.send_message(
                                chat_id=telegram_id,
                                text=text,
                                parse_mode="HTML",
                                reply_markup=kb,
                            )
                            await journal_settings_repo.mark_warning_sent(
                                session, chart_id, target_date=hit.date_, now=now
                            )
                            await session.commit()
                            logger.info(
                                "important_dates.warning_sent",
                                chart_id=str(chart_id),
                                telegram_id=telegram_id,
                                target_date=hit.date_.isoformat(),
                                severity=hit.severity,
                            )
                        except (TelegramBadRequest, TelegramForbiddenError) as exc:
                            logger.warning(
                                "important_dates.warning_failed",
                                chart_id=str(chart_id),
                                error=str(exc),
                                exc_type=type(exc).__name__,
                            )
    finally:
        await bot.session.close()


async def scan_reflection_prompts_job() -> None:
    """Wave 4e v2 (2026-06-10) — hourly scan delivering the day-of
    REFLECTION prompt at ~18:00 chart-local time.

    Каждый час: берём карты с ``reflection_hour_utc == текущий UTC-час``
    (фильтр в SQL — see ``list_reflection_due_at``), для каждой считаем
    локальную «сегодняшнюю» дату через chart.tz_offset и, если она
    важная и приглашение ещё не уходило сегодня, шлём prompt с кнопкой
    «Записать рефлексию». Commit per-chart, дедуп через
    ``last_reflection_prompt_date``.

    Почасовой глобальный скан вместо per-chart cron: important-dates
    включены по умолчанию у ВСЕХ карт, per-chart регистрация дала бы
    тысячи джобов в APScheduler.
    """
    from datetime import UTC, datetime, timedelta

    from calculator.important_dates import (
        find_important_dates_in_range,
        format_important_date_reflection,
    )
    from db.models import User
    from db.repositories.journal_repo import ChartJournalSettingsRepository

    session_factory = _make_session_factory()
    bot = _make_bot()
    chart_repo = ChartRepository()
    journal_settings_repo = ChartJournalSettingsRepository()

    try:
        async with session_factory() as session:
            now_utc = datetime.now(UTC)
            due = await journal_settings_repo.list_reflection_due_at(session, hour_utc=now_utc.hour)
            logger.info(
                "important_dates.reflection_scan_start",
                hour_utc=now_utc.hour,
                due_charts=len(due),
            )

            for js in due:
                # Capture fields up-front: commit per-chart below expires
                # ORM attributes.
                chart_id = js.chart_id
                last_reflection_date = js.last_reflection_prompt_date

                chart = await chart_repo.get_by_id(session, chart_id)
                if chart is None:
                    continue
                user = await session.get(User, chart.user_id)
                telegram_id = getattr(user, "telegram_id", None) if user is not None else None
                if telegram_id is None:
                    continue

                # «Сегодня» в часовом поясе карты: в 18:00 local для
                # UTC-7 уже наступила следующая UTC-дата — наивный
                # date.today() промахнулся бы на день.
                tz_offset = float(getattr(chart, "tz_offset", 0.0) or 0.0)
                local_today = (now_utc + timedelta(hours=tz_offset)).date()
                if last_reflection_date == local_today:
                    continue

                chart_data = ChartOutput.model_validate(chart.chart_data)
                hits = find_important_dates_in_range(chart_data, local_today, local_today)
                today_hits = [h for h in hits if h.date_ == local_today]
                if not today_hits:
                    continue

                hit = today_hits[0]
                text = format_important_date_reflection(chart_data, hit)
                kb = InlineKeyboardMarkup(
                    inline_keyboard=[
                        [
                            InlineKeyboardButton(
                                text="📝 Записать рефлексию",
                                callback_data=f"journal:write:{chart_id}",
                            )
                        ],
                        [
                            InlineKeyboardButton(
                                text="◀ К карте",
                                callback_data=f"chart:open:{chart_id}",
                            )
                        ],
                    ]
                )
                try:
                    await bot.send_message(
                        chat_id=telegram_id, text=text, parse_mode="HTML", reply_markup=kb
                    )
                    await journal_settings_repo.mark_reflection_prompt_sent(
                        session, chart_id, day=local_today
                    )
                    await session.commit()
                    logger.info(
                        "important_dates.reflection_sent",
                        chart_id=str(chart_id),
                        telegram_id=telegram_id,
                        target_date=local_today.isoformat(),
                        severity=hit.severity,
                    )
                except (TelegramBadRequest, TelegramForbiddenError) as exc:
                    logger.warning(
                        "important_dates.reflection_failed",
                        chart_id=str(chart_id),
                        error=str(exc),
                        exc_type=type(exc).__name__,
                    )
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

        # Re-use already-generated content when retrying a failed send.
        # Без этого rebuild_jobs every 5min regenerates LLM (7-10k tokens)
        # for a delivery row that just failed на «message too long».
        if existing is not None and existing.content:
            body = existing.content
            delivery = existing
            logger.info(
                "forecast.monthly.reusing_existing_content",
                subscription_id=str(subscription_id),
                slot_key=slot_key,
                delivery_id=str(existing.id),
            )
        else:
            forecast = await generate_monthly_forecast(
                chart=chart_output,
                period_start=period_start,
                school=_school_from_sub(sub),
            )
            header_label = (
                f"{_DELIVERY_HEADER[ForecastKind.monthly]} — неделя {week}"
                if week is not None
                else _DELIVERY_HEADER[ForecastKind.monthly]
            )
            body = f"{header_label}\n\n{forecast.text}"

            new_delivery = await delivery_repo.record(
                session,
                subscription_id=subscription_id,
                slot_key=slot_key,
                content=body,
            )
            await session.commit()
            if new_delivery is None:
                return
            delivery = new_delivery

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
