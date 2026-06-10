"""Wave 3d — paid forecast subscription handlers.

UI flow (hotfix 2026-05-20 — callbacks укорочены под Telegram-лимит 64 bytes):
    forecast:show:<chart_id>          menu (monthly / daily / list)
    fc:bm                              → delivery picker (weekly|bulk)
    fc:mc:<weekly|bulk>                → create + msg
    fc:bd                              → hour picker
    fc:dc:<hour_local>                 → create + msg
    fc:list                            → active subs + cancel buttons
    fc:c:<sub_id>                      → confirm dialog
    fc:cc:<sub_id>                     → repo.cancel + msg
    fc:back                            → back to plans menu

chart_id живёт в FSM data под ключом ``_FSM_FORECAST_CHART`` — handlers
читают его оттуда, callback_data короткие (UUID 36 chars + старые
префиксы ``forecast:monthly_confirm:`` суммарно давали 68 chars >
лимита 64, Telegram отвечал BUTTON_DATA_INVALID).
"""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from datetime import datetime
from typing import Any

import structlog
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_settings
from bot.keyboards import (
    forecast_cancel_kb,
    forecast_daily_hour_kb,
    forecast_menu_kb,
    forecast_monthly_delivery_kb,
    school_selector_kb,
)
from bot.services.payments import (
    forecast_daily_payload,
    forecast_monthly_payload,
    payments_live,
    send_invoice,
)
from db.models import (
    Chart as ChartModel,
)
from db.models import (
    ChartForecastSubscription,
    ForecastKind,
    MonthlyDelivery,
    User,
)
from db.repositories.chart_repo import ChartRepository
from db.repositories.forecast_repo import ChartForecastSubscriptionRepository
from db.repositories.journal_repo import ChartJournalSettingsRepository

# Wave 3d hotfix 2026-05-20: Telegram limits callback_data to 64 bytes.
# UUID = 36 chars → any compound callback with two UUIDs overflows. We
# stash chart_id in FSM data under this key once the user enters the
# forecast menu via ``forecast:show:<chart_id>``; sub-callbacks then
# stay short (``fc:*``).
_FSM_FORECAST_CHART = "forecast_chart_id"

logger = structlog.get_logger(__name__)

# Module-global set of in-flight «kick» tasks. asyncio.create_task без
# хранения ссылки рискует — GC может собрать задачу до её завершения,
# и await-цепочка оборвётся (RUF006).
_kick_tasks: set[asyncio.Task[None]] = set()

forecast_router = Router(name="forecast")
_chart_repo = ChartRepository()
_sub_repo = ChartForecastSubscriptionRepository()
_journal_settings_repo = ChartJournalSettingsRepository()


_NOT_YOUR_CHART = "Эта карта не ваша или удалена."

_SCHOOL_LABELS = {
    "classic": "🎓 Классическая",
    "edoha": "🌀 Мастер ЭдоХа",
    "modern": "🧬 Современная",
}
_VALID_SCHOOLS = frozenset(_SCHOOL_LABELS)
_SESSION_LOST = "Сессия истекла — откройте карту заново и нажмите «📅 Прогнозы»."

_PLANS_INTRO = (
    "<b>📅 Прогнозы от Анастасии</b>\n\n"
    "<b>Месячный план — 500 ₽</b>\n"
    "Я расскажу про весь месяц: главная тема, возможности, риски, "
    "и портрет каждой недели. Пришлю всё сразу одним сообщением "
    "или разобью на 4 еженедельные части — как удобнее.\n\n"
    "<b>Дневной план — 900 ₽/месяц</b>\n"
    "Каждое утро в выбранный вами час я пришлю вам активацию "
    "энергий дня — на что опереться и чего избегать. Буду писать "
    "каждый день в течение месяца.\n\n"
    "{free_note}"
    "Выберите план:"
)
_FREE_BYPASS_NOTE = (
    "<i>Сейчас все планы активируются бесплатно — оплата подключается. "
    "Это временно, пока добавляем ЮKassa.</i>\n\n"
)


def _intro_text() -> str:
    note = _FREE_BYPASS_NOTE if get_settings().forecast_free_bypass else ""
    return _PLANS_INTRO.format(free_note=note)


def _hour_local_to_utc(hour_local: int, tz_offset_hours: float) -> int:
    """Convert «4 утра по моему времени» to a UTC cron hour.

    tz_offset_hours is the chart's offset from UTC (positive = ahead).
    e.g. Moscow (+3) at hour_local=4 → hour_utc = (4 - 3) % 24 = 1.

    Modulo 24 handles wrap-around at day boundaries; the daily slot
    key always uses date.today() at fire time so the right calendar
    day still anchors the forecast."""
    return int(hour_local - tz_offset_hours) % 24


async def _load_chart_for_user(
    session: AsyncSession, *, chart_id: uuid.UUID, user_id: uuid.UUID
) -> ChartModel | None:
    chart = await _chart_repo.get_by_id(session, chart_id)
    if chart is None or chart.user_id != user_id:
        return None
    return chart


def _parse_chart_id(parts: list[str], index: int) -> uuid.UUID | None:
    try:
        return uuid.UUID(parts[index])
    except (ValueError, IndexError):
        return None


async def _stash_chart_id(state: FSMContext, chart_id: uuid.UUID) -> None:
    payload: dict[str, Any] = {_FSM_FORECAST_CHART: str(chart_id)}
    await state.update_data(**payload)


async def _resolve_chart_from_state(
    state: FSMContext, session: AsyncSession, user_id: uuid.UUID
) -> ChartModel | None:
    """Read forecast chart_id from FSM (set by forecast:show) and load
    it with the same ownership check as the original callbacks."""
    data = await state.get_data()
    raw = data.get(_FSM_FORECAST_CHART)
    if not isinstance(raw, str):
        return None
    try:
        chart_id = uuid.UUID(raw)
    except ValueError:
        return None
    return await _load_chart_for_user(session, chart_id=chart_id, user_id=user_id)


# ── forecast:show — main menu (sets FSM chart_id) ────────────────────────


@forecast_router.callback_query(F.data.startswith("forecast:show:"))
async def handle_forecast_show(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    state: FSMContext,
) -> None:
    if not callback.data:
        await callback.answer()
        return
    chart_id = _parse_chart_id(callback.data.split(":"), 2)
    if chart_id is None:
        await callback.answer("Неверная карта", show_alert=True)
        return

    chart = await _load_chart_for_user(session, chart_id=chart_id, user_id=user.id)
    if chart is None:
        await callback.answer(_NOT_YOUR_CHART, show_alert=True)
        return

    await _stash_chart_id(state, chart_id)
    if isinstance(callback.message, Message):
        await callback.message.answer(_intro_text(), reply_markup=forecast_menu_kb(chart_id))
    await callback.answer()


@forecast_router.callback_query(F.data == "fc:back")
async def handle_fc_back(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    state: FSMContext,
) -> None:
    chart = await _resolve_chart_from_state(state, session, user.id)
    if chart is None:
        await callback.answer(_SESSION_LOST, show_alert=True)
        return
    if isinstance(callback.message, Message):
        await callback.message.answer(_intro_text(), reply_markup=forecast_menu_kb(chart.id))
    await callback.answer()


# ── Monthly purchase flow ────────────────────────────────────────────────


@forecast_router.callback_query(F.data == "fc:bm")
async def handle_buy_monthly(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    state: FSMContext,
) -> None:
    chart = await _resolve_chart_from_state(state, session, user.id)
    if chart is None:
        await callback.answer(_SESSION_LOST, show_alert=True)
        return

    if isinstance(callback.message, Message):
        await callback.message.answer(
            "Как мне прислать вам месячный прогноз?",
            reply_markup=forecast_monthly_delivery_kb(),
        )
    await callback.answer()


@forecast_router.callback_query(F.data.startswith("fc:mc:"))
async def handle_monthly_confirm(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    state: FSMContext,
) -> None:
    """Шаг 2/3 покупки месячной подписки — выбран формат доставки
    (weekly|bulk). Сохраняем в FSM и показываем выбор школы. Подписка
    НЕ создаётся пока клиент не выберет школу в handle_monthly_school_confirm.
    """
    if not callback.data:
        await callback.answer()
        return
    parts = callback.data.split(":")
    delivery_raw = parts[2] if len(parts) > 2 else ""
    if delivery_raw not in ("weekly", "bulk"):
        await callback.answer("Неверный выбор", show_alert=True)
        return
    chart = await _resolve_chart_from_state(state, session, user.id)
    if chart is None:
        await callback.answer(_SESSION_LOST, show_alert=True)
        return

    await state.update_data(forecast_monthly_delivery=delivery_raw)

    # Wave 7 / 1.18.14 — if the chart has a default school, skip the
    # school selector and proceed straight to purchase.
    default_school = chart.default_school if chart.default_school in _VALID_SCHOOLS else None
    if default_school is not None and isinstance(callback.message, Message):
        await state.update_data(forecast_monthly_delivery=None)
        await _proceed_monthly(
            callback.message, session, user.id, chart, delivery_raw, default_school
        )
        await callback.answer()
        return

    if isinstance(callback.message, Message):
        await callback.message.answer(
            "В каком стиле прислать прогноз? Выберите школу — от этого "
            "зависит методология и интонация:",
            reply_markup=school_selector_kb(callback_prefix="fc:ms"),
        )
    await callback.answer()


@forecast_router.callback_query(F.data.startswith("fc:ms:"))
async def handle_monthly_school_confirm(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    state: FSMContext,
) -> None:
    """Шаг 3/3 покупки месячной подписки — выбрана школа. Читаем
    delivery из FSM и продолжаем (invoice ЮKassa или free-bypass
    create). Wave 7 Phase 2 ext (2026-05-26), оплата (2026-06-02)."""
    if not callback.data:
        await callback.answer()
        return
    parts = callback.data.split(":")
    school_raw = parts[2] if len(parts) > 2 else ""
    if school_raw not in _VALID_SCHOOLS:
        await callback.answer("Неверный выбор школы", show_alert=True)
        return

    data = await state.get_data()
    delivery_raw = data.get("forecast_monthly_delivery", "")
    if delivery_raw not in ("weekly", "bulk"):
        await callback.answer(
            "Сессия выбора прогноза потеряна. Откройте Прогнозы заново.",
            show_alert=True,
        )
        return

    chart = await _resolve_chart_from_state(state, session, user.id)
    if chart is None:
        await callback.answer(_SESSION_LOST, show_alert=True)
        return

    await state.update_data(forecast_monthly_delivery=None)
    if isinstance(callback.message, Message):
        await _proceed_monthly(callback.message, session, user.id, chart, delivery_raw, school_raw)
    await callback.answer()


async def _proceed_monthly(
    message: Message,
    session: AsyncSession,
    user_id: uuid.UUID,
    chart: ChartModel,
    delivery_raw: str,
    school: str,
) -> None:
    """Either send a ЮKassa invoice (payments live) or create the
    subscription right away (free-dev bypass). Shared by the school-
    confirm handler and the default-school skip path."""
    settings = get_settings()
    if message.bot is None:
        return
    if payments_live(settings):
        token = settings.telegram_payment_provider_token
        assert token is not None  # guarded by payments_live
        await send_invoice(
            message.bot,
            message.chat.id,
            title=f"Месячный прогноз — {_SCHOOL_LABELS[school]}",
            description=(
                "Прогноз на месяц для вашей карты Ба Цзы. "
                f"Доставка: {'раз в неделю' if delivery_raw == 'weekly' else 'всё сразу'}."
            ),
            amount_rub=settings.forecast_monthly_price_rub,
            payload=forecast_monthly_payload(delivery_raw, school, str(chart.id)),
            provider_token=token.get_secret_value(),
        )
        return
    await finalize_monthly_subscription(
        message.bot,
        message.chat.id,
        session,
        user_id=user_id,
        chart=chart,
        delivery=MonthlyDelivery(delivery_raw),
        school=school,
        payment_provider="free_dev_bypass",
        payment_id=None,
    )


async def finalize_monthly_subscription(
    bot: Bot,
    chat_id: int,
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    chart: ChartModel,
    delivery: MonthlyDelivery,
    school: str,
    payment_provider: str | None,
    payment_id: str | None,
) -> None:
    """Create the monthly subscription, enable important-date alerts,
    confirm to the user, and schedule the inline first-delivery kick.
    Called from the free-bypass path and from the ЮKassa
    successful_payment handler (bot/routers/payments.py)."""
    settings = get_settings()
    sub = await _sub_repo.create(
        session,
        user_id=user_id,
        chart_id=chart.id,
        kind=ForecastKind.monthly,
        price_rub=settings.forecast_monthly_price_rub,
        monthly_delivery=delivery,
        payment_provider=payment_provider,
        payment_id=payment_id,
        period_days=settings.forecast_period_days,
        chosen_school=school,
    )
    # 2026-05-21 Bogdan — связка W3↔W4e: subscribing to forecasts
    # auto-enables «important dates» alerts for the same chart.
    await _journal_settings_repo.toggle_important_dates(
        session, chart_id=chart.id, enabled=True, tz_offset=chart.tz_offset
    )
    await session.commit()

    note = (
        "Первую часть я пришлю через минуту, остальные — раз в неделю."
        if delivery == MonthlyDelivery.weekly
        else "Прогноз пришлю через минуту одним сообщением."
    )
    msg = (
        "<b>✓ Подписка активирована</b>\n\n"
        f"Месячный прогноз для этой карты — {settings.forecast_monthly_price_rub} ₽.\n"
        f"Доставка: {'раз в неделю' if delivery == MonthlyDelivery.weekly else 'всё сразу'}.\n"
        f"Школа: {_SCHOOL_LABELS[school]}.\n\n"
        f"{note}"
    )
    logger.info(
        "forecast.subscription.created",
        kind="monthly",
        delivery=delivery.value,
        chosen_school=school,
        subscription_id=str(sub.id),
        user_id=str(user_id),
        chart_id=str(chart.id),
        payment_provider=payment_provider,
    )
    await bot.send_message(chat_id, msg)

    # Inline kick of the first delivery (Wave 7 hotfix 2026-05-26).
    # Without this, the first forecast depended on APScheduler's
    # rebuild_jobs_for_all_subs cycle (every 5 min). If the scheduler
    # container had restarted after subscription was created — the
    # «week=1 fire_at < now-1h» guard in _jobs_for_subscription would
    # silently skip week=1 entirely, and the user never received the
    # «первая часть через минуту» promised in the confirmation msg.
    # Bulk and daily delivery use DateTrigger started_at+60s; weekly
    # week=1 used to use started_at + 0d which is racy.
    sub_id_for_kick = sub.id
    period_start_for_kick = sub.started_at.date()
    first_week = 1 if delivery == MonthlyDelivery.weekly else None

    async def _kick_first_delivery() -> None:
        # Imported locally to avoid forecast.py ↔ scheduler.jobs import
        # cycles on bot startup.
        from bot.scheduler.jobs import send_monthly_forecast_job

        try:
            # 60s delay matches the «через минуту» phrasing in the
            # confirmation message and gives the user time to read it
            # before the photo + text arrive.
            await asyncio.sleep(60)
            await send_monthly_forecast_job(
                subscription_id=sub_id_for_kick,
                period_start=period_start_for_kick,
                week=first_week,
            )
            logger.info(
                "forecast.monthly.inline_first_delivery_done",
                subscription_id=str(sub_id_for_kick),
                week=first_week,
            )
        except Exception as exc:
            # Inline kick is a UX nicety, не контракт. APScheduler-based
            # delivery всё ещё работает фоном — если он подхватит job,
            # клиент получит прогноз с небольшим опозданием.
            logger.exception(
                "forecast.monthly.inline_kick_failed",
                subscription_id=str(sub_id_for_kick),
                week=first_week,
                error=str(exc),
            )

    # Reference хранится в module-global _kick_tasks set, чтобы task
    # не был сразу собран GC (RUF006). discard через add_done_callback.
    task = asyncio.create_task(_kick_first_delivery())
    _kick_tasks.add(task)
    task.add_done_callback(_kick_tasks.discard)


# ── Daily purchase flow ──────────────────────────────────────────────────


@forecast_router.callback_query(F.data == "fc:bd")
async def handle_buy_daily(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    state: FSMContext,
) -> None:
    chart = await _resolve_chart_from_state(state, session, user.id)
    if chart is None:
        await callback.answer(_SESSION_LOST, show_alert=True)
        return

    if isinstance(callback.message, Message):
        await callback.message.answer(
            "В какое время вам присылать дневной прогноз?",
            reply_markup=forecast_daily_hour_kb(),
        )
    await callback.answer()


@forecast_router.callback_query(F.data.startswith("fc:dc:"))
async def handle_daily_confirm(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    state: FSMContext,
) -> None:
    """Шаг 2/3 покупки дневной подписки — выбран час доставки.
    Сохраняем в FSM, показываем школу. Подписка создаётся позже
    в handle_daily_school_confirm."""
    if not callback.data:
        await callback.answer()
        return
    parts = callback.data.split(":")
    try:
        hour_local = int(parts[2])
    except (ValueError, IndexError):
        await callback.answer("Неверный час", show_alert=True)
        return
    if not (0 <= hour_local <= 23):
        await callback.answer("Неверный выбор", show_alert=True)
        return
    chart = await _resolve_chart_from_state(state, session, user.id)
    if chart is None:
        await callback.answer(_SESSION_LOST, show_alert=True)
        return

    await state.update_data(forecast_daily_hour_local=hour_local)

    # Wave 7 / 1.18.14 — default-school skip.
    default_school = chart.default_school if chart.default_school in _VALID_SCHOOLS else None
    if default_school is not None and isinstance(callback.message, Message):
        await state.update_data(forecast_daily_hour_local=None)
        await _proceed_daily(callback.message, session, user.id, chart, hour_local, default_school)
        await callback.answer()
        return

    if isinstance(callback.message, Message):
        await callback.message.answer(
            "В каком стиле присылать дневной прогноз? Выберите школу — "
            "от этого зависит методология и интонация:",
            reply_markup=school_selector_kb(callback_prefix="fc:ds"),
        )
    await callback.answer()


@forecast_router.callback_query(F.data.startswith("fc:ds:"))
async def handle_daily_school_confirm(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    state: FSMContext,
) -> None:
    """Шаг 3/3 покупки дневной подписки — выбрана школа. Продолжаем
    (invoice ЮKassa или free-bypass create). Wave 7 (2026-06-02)."""
    if not callback.data:
        await callback.answer()
        return
    parts = callback.data.split(":")
    school_raw = parts[2] if len(parts) > 2 else ""
    if school_raw not in _VALID_SCHOOLS:
        await callback.answer("Неверный выбор школы", show_alert=True)
        return

    data = await state.get_data()
    hour_local_raw = data.get("forecast_daily_hour_local")
    if not isinstance(hour_local_raw, int) or not (0 <= hour_local_raw <= 23):
        await callback.answer(
            "Сессия выбора прогноза потеряна. Откройте Прогнозы заново.",
            show_alert=True,
        )
        return

    chart = await _resolve_chart_from_state(state, session, user.id)
    if chart is None:
        await callback.answer(_SESSION_LOST, show_alert=True)
        return

    await state.update_data(forecast_daily_hour_local=None)
    if isinstance(callback.message, Message):
        await _proceed_daily(callback.message, session, user.id, chart, hour_local_raw, school_raw)
    await callback.answer()


async def _proceed_daily(
    message: Message,
    session: AsyncSession,
    user_id: uuid.UUID,
    chart: ChartModel,
    hour_local: int,
    school: str,
) -> None:
    """ЮKassa invoice (payments live) or direct create (free bypass)."""
    settings = get_settings()
    if message.bot is None:
        return
    if payments_live(settings):
        token = settings.telegram_payment_provider_token
        assert token is not None
        await send_invoice(
            message.bot,
            message.chat.id,
            title=f"Дневной прогноз — {_SCHOOL_LABELS[school]}",
            description=(
                f"Дневной прогноз + активации на 30 дней, ежедневно в "
                f"{hour_local:02d}:00 вашего времени."
            ),
            amount_rub=settings.forecast_daily_price_rub,
            payload=forecast_daily_payload(hour_local, school, str(chart.id)),
            provider_token=token.get_secret_value(),
        )
        return
    await finalize_daily_subscription(
        message.bot,
        message.chat.id,
        session,
        user_id=user_id,
        chart=chart,
        hour_local=hour_local,
        school=school,
        payment_provider="free_dev_bypass",
        payment_id=None,
    )


async def finalize_daily_subscription(
    bot: Bot,
    chat_id: int,
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    chart: ChartModel,
    hour_local: int,
    school: str,
    payment_provider: str | None,
    payment_id: str | None,
) -> None:
    """Create the daily subscription, enable important-date alerts, and
    confirm. Called from free-bypass path and ЮKassa successful_payment."""
    settings = get_settings()
    hour_utc = _hour_local_to_utc(hour_local, chart.tz_offset)
    sub = await _sub_repo.create(
        session,
        user_id=user_id,
        chart_id=chart.id,
        kind=ForecastKind.daily,
        price_rub=settings.forecast_daily_price_rub,
        daily_send_hour_utc=hour_utc,
        payment_provider=payment_provider,
        payment_id=payment_id,
        period_days=settings.forecast_period_days,
        chosen_school=school,
    )
    await _journal_settings_repo.toggle_important_dates(
        session, chart_id=chart.id, enabled=True, tz_offset=chart.tz_offset
    )
    await session.commit()

    msg = (
        "<b>✓ Подписка активирована</b>\n\n"
        f"Дневной прогноз для этой карты — {settings.forecast_daily_price_rub} ₽ "
        f"на 30 дней.\n"
        f"Я буду писать в {hour_local:02d}:00 вашего местного времени "
        f"(UTC {hour_utc:02d}:00).\n"
        f"Школа: {_SCHOOL_LABELS[school]}.\n\n"
        "Первый прогноз пришлю в указанный час."
    )
    logger.info(
        "forecast.subscription.created",
        kind="daily",
        hour_local=hour_local,
        hour_utc=hour_utc,
        chosen_school=school,
        subscription_id=str(sub.id),
        user_id=str(user_id),
        chart_id=str(chart.id),
        payment_provider=payment_provider,
    )
    await bot.send_message(chat_id, msg)


# ── List + cancel ────────────────────────────────────────────────────────


def _format_sub_row(sub: ChartForecastSubscription) -> str:
    expires = sub.expires_at.strftime("%d.%m.%Y")
    if sub.kind == ForecastKind.daily:
        return f"🌅 Дневной прогноз — {sub.daily_send_hour_utc:02d}:00 UTC, до {expires}"
    delivery_name = (
        "раз в неделю" if sub.monthly_delivery == MonthlyDelivery.weekly else "всё сразу"
    )
    return f"📅 Месячный прогноз — {delivery_name}, до {expires}"


@forecast_router.callback_query(F.data == "fc:list")
async def handle_forecast_list(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    state: FSMContext,
) -> None:
    chart = await _resolve_chart_from_state(state, session, user.id)
    if chart is None:
        await callback.answer(_SESSION_LOST, show_alert=True)
        return

    subs = await _sub_repo.list_active_for_chart(session, chart.id)
    if not subs:
        text = "У этой карты пока нет активных подписок на прогнозы."
        if isinstance(callback.message, Message):
            await callback.message.answer(text, reply_markup=forecast_menu_kb(chart.id))
        await callback.answer()
        return

    rows: list[list[InlineKeyboardButton]] = []
    lines = ["<b>Активные подписки</b>:\n"]
    for sub in subs:
        lines.append(f"• {_format_sub_row(sub)}")
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"🛑 Отменить: {sub.kind.value}",
                    callback_data=f"fc:c:{sub.id}",
                )
            ]
        )
    rows.append([InlineKeyboardButton(text="↩ Назад", callback_data="fc:back")])
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    if isinstance(callback.message, Message):
        await callback.message.answer("\n".join(lines), reply_markup=kb)
    await callback.answer()


@forecast_router.callback_query(F.data.startswith("fc:c:"))
async def handle_cancel_request(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    """Show confirm dialog before cancelling."""
    if not callback.data:
        await callback.answer()
        return
    parts = callback.data.split(":")
    try:
        sub_id = uuid.UUID(parts[2])
    except (ValueError, IndexError):
        await callback.answer("Неверная подписка", show_alert=True)
        return

    sub = await _sub_repo.get_by_id(session, sub_id)
    if sub is None or sub.user_id != user.id:
        await callback.answer("Подписка не найдена", show_alert=True)
        return

    if isinstance(callback.message, Message):
        await callback.message.answer(
            f"Отменить подписку:\n• {_format_sub_row(sub)}?",
            reply_markup=forecast_cancel_kb(sub_id),
        )
    await callback.answer()


@forecast_router.callback_query(F.data.startswith("fc:cc:"))
async def handle_cancel_confirm(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    state: FSMContext,
) -> None:
    if not callback.data:
        await callback.answer()
        return
    parts = callback.data.split(":")
    try:
        sub_id = uuid.UUID(parts[2])
    except (ValueError, IndexError):
        await callback.answer("Неверная подписка", show_alert=True)
        return

    sub = await _sub_repo.get_by_id(session, sub_id)
    if sub is None or sub.user_id != user.id:
        await callback.answer("Подписка не найдена", show_alert=True)
        return

    cancelled = await _sub_repo.cancel(session, sub_id)
    await session.commit()
    if not cancelled:
        await callback.answer("Подписка уже была отменена", show_alert=True)
        return

    logger.info(
        "forecast.subscription.cancelled",
        subscription_id=str(sub_id),
        user_id=str(user.id),
        cancelled_at=datetime.now().isoformat(),
    )
    chart = await _resolve_chart_from_state(state, session, user.id)
    if isinstance(callback.message, Message):
        with contextlib.suppress(Exception):
            await callback.message.edit_text("Подписка отменена.")
        if chart is not None:
            await callback.message.answer(
                "Прогнозы по этой подписке больше не придут.",
                reply_markup=forecast_menu_kb(chart.id),
            )
        else:
            await callback.message.answer("Прогнозы по этой подписке больше не придут.")
    await callback.answer()
