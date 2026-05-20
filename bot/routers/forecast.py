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

import contextlib
import uuid
from datetime import datetime
from typing import Any

import structlog
from aiogram import F, Router
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

# Wave 3d hotfix 2026-05-20: Telegram limits callback_data to 64 bytes.
# UUID = 36 chars → any compound callback with two UUIDs overflows. We
# stash chart_id in FSM data under this key once the user enters the
# forecast menu via ``forecast:show:<chart_id>``; sub-callbacks then
# stay short (``fc:*``).
_FSM_FORECAST_CHART = "forecast_chart_id"

logger = structlog.get_logger(__name__)

forecast_router = Router(name="forecast")
_chart_repo = ChartRepository()
_sub_repo = ChartForecastSubscriptionRepository()


_NOT_YOUR_CHART = "Эта карта не ваша или удалена."
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

    settings = get_settings()
    delivery = MonthlyDelivery(delivery_raw)
    sub = await _sub_repo.create(
        session,
        user_id=user.id,
        chart_id=chart.id,
        kind=ForecastKind.monthly,
        price_rub=settings.forecast_monthly_price_rub,
        monthly_delivery=delivery,
        payment_provider="free_dev_bypass" if settings.forecast_free_bypass else None,
        period_days=settings.forecast_period_days,
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
        f"Доставка: {'раз в неделю' if delivery == MonthlyDelivery.weekly else 'всё сразу'}.\n\n"
        f"{note}"
    )
    logger.info(
        "forecast.subscription.created",
        kind="monthly",
        delivery=delivery.value,
        subscription_id=str(sub.id),
        user_id=str(user.id),
        chart_id=str(chart.id),
        free_bypass=settings.forecast_free_bypass,
    )
    if isinstance(callback.message, Message):
        await callback.message.answer(msg)
    await callback.answer()


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

    settings = get_settings()
    hour_utc = _hour_local_to_utc(hour_local, chart.tz_offset)

    sub = await _sub_repo.create(
        session,
        user_id=user.id,
        chart_id=chart.id,
        kind=ForecastKind.daily,
        price_rub=settings.forecast_daily_price_rub,
        daily_send_hour_utc=hour_utc,
        payment_provider="free_dev_bypass" if settings.forecast_free_bypass else None,
        period_days=settings.forecast_period_days,
    )
    await session.commit()

    msg = (
        "<b>✓ Подписка активирована</b>\n\n"
        f"Дневной прогноз для этой карты — {settings.forecast_daily_price_rub} ₽ "
        f"на 30 дней.\n"
        f"Я буду писать в {hour_local:02d}:00 вашего местного времени "
        f"(UTC {hour_utc:02d}:00).\n\n"
        "Первый прогноз пришлю в указанный час."
    )
    logger.info(
        "forecast.subscription.created",
        kind="daily",
        hour_local=hour_local,
        hour_utc=hour_utc,
        subscription_id=str(sub.id),
        user_id=str(user.id),
        chart_id=str(chart.id),
        free_bypass=settings.forecast_free_bypass,
    )
    if isinstance(callback.message, Message):
        await callback.message.answer(msg)
    await callback.answer()


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
