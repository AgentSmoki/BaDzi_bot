import uuid
from typing import Any

import structlog
from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from ai.card_renderer import RenderRequest, render_chart_png
from bot.keyboards import (
    chart_actions_kb,
    new_user_kb,
    pricing_kb,
    returning_user_kb,
)
from bot.services.menu import (
    charts_to_buttons,
    format_chart_label,
    send_main_menu,
)
from calculator.models import ChartOutput
from db.models import Chart, User
from db.repositories.chart_repo import ChartRepository

PRICING_STUB_TEXT = (
    "<b>Тарифы Анастасии</b>\n\n"
    "• Месяц — 290 ₽\n"
    "• 3 месяца — 990 ₽\n"
    "• Год — 2 490 ₽\n\n"
    "Оплата подключается — пока пользуйтесь бесплатным вопросом."
)
PAY_STUB_ALERT = "Оплата подключается. Совсем скоро здесь появится ЮKassa."

logger = structlog.get_logger(__name__)

start_router = Router(name="start")
_chart_repo = ChartRepository()

GREETING_NEW_USER = (
    "Здравствуйте, {name}. Меня зовут Анастасия — я консультант по древнекитайской "
    "системе Ба Цзы.\n\n"
    "Эта система читает карту вашего рождения как карту местности: показывает сильные "
    "стороны, ритмы судьбы, благоприятные годы и узкие места.\n\n"
    "<blockquote>Мастер ЭдоХа:\n"
    "<i>БаЦзы — это наука о том как оказаться в нужное время, месте с правильными "
    "людьми.</i></blockquote>\n\n"
    "Расчёт карты и базовое прочтение бесплатно — я помогаю увидеть рисунок, "
    "по которому идёт ваша жизнь.\n\n"
    "Чтобы начать — укажите данные вашего рождения, которые помните: дата, время и город.\n\n"
    "Начнём?"
)

# Re-export so existing chart-render helpers below stay readable; the actual
# implementation lives in bot.services.menu now.
_format_chart_label = format_chart_label


def _format_chart_view(chart: Chart) -> str:
    """Render an existing Chart from the JSONB chart_data — same shape as the
    post-calculation summary so the user sees a consistent view."""
    data = chart.chart_data or {}
    pillars = data.get("pillars") or []
    day_master = data.get("day_master", "?")
    balance = data.get("element_balance") or {}
    has_time = bool(chart.has_birth_time)

    title = _format_chart_label(chart)
    date_str = chart.birth_datetime_original.strftime("%d.%m.%Y")
    time_str = chart.birth_datetime_original.strftime("%H:%M") if has_time else "—"

    def pillar_str(p: dict[str, Any]) -> str:
        return f"{p['stem']}{p['branch']}"

    if has_time and len(pillars) >= 4:
        pillars_block = (
            "<b>Четыре столпа:</b>\n"
            f"  Год: {pillar_str(pillars[0])}\n"
            f"  Месяц: {pillar_str(pillars[1])}\n"
            f"  День: {pillar_str(pillars[2])}\n"
            f"  Час: {pillar_str(pillars[3])}"
        )
    elif len(pillars) >= 3:
        pillars_block = (
            "<b>Три столпа:</b>\n"
            f"  Год: {pillar_str(pillars[0])}\n"
            f"  Месяц: {pillar_str(pillars[1])}\n"
            f"  День: {pillar_str(pillars[2])}"
        )
    else:
        pillars_block = "<i>(нет данных по столпам)</i>"

    balance_str = ", ".join(f"{k} {v:.0%}" for k, v in balance.items()) if balance else "—"

    header = f"<b>{title}</b>\nДата: {date_str}\nВремя: {time_str}"
    return (
        f"{header}\n\n"
        f"{pillars_block}\n\n"
        f"<b>Дневной мастер:</b> {day_master}\n"
        f"<b>Баланс элементов:</b> {balance_str}"
    )


@start_router.message(CommandStart())
async def handle_start(
    message: Message, user: User, session: AsyncSession, state: FSMContext
) -> None:
    await state.clear()
    charts = await _chart_repo.list_unique_by_user(session, user.id)

    if not charts:
        logger.info("start.new_user", telegram_id=user.telegram_id, user_id=str(user.id))
        sent = await message.answer(
            GREETING_NEW_USER.format(name=user.first_name),
            reply_markup=new_user_kb(),
        )
        # Track the greeting message so the first FSM step (handle_calc) can
        # edit it in place instead of stacking a new prompt below.
        await state.update_data(fsm_msg_id=sent.message_id)
        return

    logger.info(
        "start.returning_user",
        telegram_id=user.telegram_id,
        user_id=str(user.id),
        charts_count=len(charts),
    )
    await send_main_menu(message, user, session, state=state)


@start_router.callback_query(F.data.startswith("charts:page:"))
async def handle_charts_page(callback: CallbackQuery, user: User, session: AsyncSession) -> None:
    if not callback.data:
        await callback.answer()
        return
    try:
        page = int(callback.data.split(":")[2])
    except (ValueError, IndexError):
        await callback.answer()
        return

    charts = await _chart_repo.list_unique_by_user(session, user.id)
    if isinstance(callback.message, Message):
        await callback.message.edit_reply_markup(
            reply_markup=returning_user_kb(charts=charts_to_buttons(charts), page=page)
        )
    await callback.answer()


@start_router.callback_query(F.data.startswith("chart:open:"))
async def handle_chart_open(
    callback: CallbackQuery, state: FSMContext, session: AsyncSession
) -> None:
    if not callback.data:
        await callback.answer()
        return
    try:
        chart_id = uuid.UUID(callback.data.split(":")[2])
    except (ValueError, IndexError):
        await callback.answer("Неверная карта", show_alert=True)
        return

    chart = await _chart_repo.get_by_id(session, chart_id)
    if chart is None:
        await callback.answer("Карта не найдена", show_alert=True)
        return

    # Pin this chart as the active one for the upcoming consultation —
    # `consultation._resolve_active_chart` reads `chart_id` from FSM
    # before falling back to "latest". Without this a user opening an old
    # chart and pressing "Задать вопрос" would silently get the latest.
    await state.update_data(chart_id=str(chart.id))

    if isinstance(callback.message, Message):
        try:
            png = await _render_chart(chart)
        except Exception:
            logger.exception("chart_open.render_failed", chart_id=str(chart.id))
            await callback.message.answer(
                _format_chart_view(chart), reply_markup=chart_actions_kb()
            )
            await callback.answer()
            return
        title = _format_chart_label(chart)
        await callback.message.answer_photo(
            BufferedInputFile(png, "chart.png"),
            caption=f"<b>{title}</b>",
            reply_markup=chart_actions_kb(),
        )
    await callback.answer()


# ── Generic main-menu navigation (menu:back / menu:pricing / pay:*) ──────


@start_router.callback_query(F.data == "menu:back")
async def handle_menu_back(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
) -> None:
    """Return to the returning-user main menu.

    Called from `_after_answer_kb` (consultation), `chart_actions_kb`,
    and the pricing-stub `pricing_kb`. Clears any in-flight FSM (e.g.
    `ConsultationState.waiting_question`) so the user lands cleanly in
    the menu instead of in a half-state.
    """
    await state.set_state(None)
    if isinstance(callback.message, Message):
        await send_main_menu(callback.message, user, session, state=state)
    await callback.answer()


@start_router.callback_query(F.data == "menu:pricing")
async def handle_menu_pricing(callback: CallbackQuery) -> None:
    """Stub until 1.12 (ЮKassa). Shows the price-list keyboard so the
    user can see what's coming, but `pay:*` itself just answers an alert.
    """
    if isinstance(callback.message, Message):
        await callback.message.answer(PRICING_STUB_TEXT, reply_markup=pricing_kb())
    await callback.answer()


@start_router.callback_query(F.data.startswith("pay:"))
async def handle_pay_stub(callback: CallbackQuery) -> None:
    """Placeholder for `pay:monthly|quarterly|annual` — surfaces a Telegram
    alert so the user knows the click was registered. Will be replaced by
    ЮKassa CreatePayment + redirect URL in 1.12.3."""
    await callback.answer(PAY_STUB_ALERT, show_alert=True)


async def _render_chart(chart: Chart) -> bytes:
    chart_output = ChartOutput.model_validate(chart.chart_data)
    short_city = chart.chart_data.get("city_name") if chart.chart_data else None
    if isinstance(short_city, str) and "," in short_city:
        short_city = short_city.split(",")[0].strip()
    has_time = bool(chart.has_birth_time)
    time_part = chart.birth_datetime_original.strftime("%H:%M") if has_time else "без часа"
    subtitle_parts = [p for p in (short_city, time_part) if p]
    subtitle = " · ".join(subtitle_parts) if subtitle_parts else ""
    # SVG title uses a Latin-priority font, so we drop the CJK day-master prefix
    # here — the day master is already displayed prominently inside the card.
    if chart.name and "," not in chart.name:
        title = chart.name
    else:
        title = chart.birth_datetime_original.strftime("%d.%m.%Y")
    return await render_chart_png(
        RenderRequest(
            chart=chart_output,
            title=title,
            subtitle=subtitle,
            has_birth_time=has_time,
        )
    )
