import uuid
from typing import Any

import structlog
from aiogram import F, Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from ai.card_renderer import RenderRequest, render_chart_png
from bot.keyboards import new_user_kb, returning_user_kb
from calculator.models import ChartOutput
from db.models import Chart, User
from db.repositories.chart_repo import ChartRepository

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

GREETING_RETURNING_USER = "С возвращением, {name}. Что вас интересует сегодня?"


def _format_chart_label(chart: Chart) -> str:
    """User-set name wins; otherwise show day-master + date.

    Legacy charts created before the naming flow had Chart.name auto-set to
    the city's full address (e.g. "Волжский, Волгоградская область, Россия").
    A name with commas almost certainly came from there, so treat it as
    auto-generated and fall through to day-master + date for clarity.
    """
    if chart.name and "," not in chart.name:
        return chart.name
    date_str = chart.birth_datetime_original.strftime("%d.%m.%Y")
    day_master = chart.chart_data.get("day_master", "?") if chart.chart_data else "?"
    return f"{day_master} {date_str}"


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
    charts = await _chart_repo.list_by_user(session, user.id)

    if not charts:
        logger.info("start.new_user", telegram_id=user.telegram_id, user_id=str(user.id))
        await message.answer(
            GREETING_NEW_USER.format(name=user.first_name),
            reply_markup=new_user_kb(),
        )
        return

    logger.info(
        "start.returning_user",
        telegram_id=user.telegram_id,
        user_id=str(user.id),
        charts_count=len(charts),
    )
    await message.answer(
        GREETING_RETURNING_USER.format(name=user.first_name),
        reply_markup=returning_user_kb(charts=_charts_to_buttons(charts)),
    )


def _charts_to_buttons(charts: list[Chart]) -> list[tuple[uuid.UUID, str]]:
    return [(chart.id, _format_chart_label(chart)) for chart in charts]


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

    charts = await _chart_repo.list_by_user(session, user.id)
    if isinstance(callback.message, Message):
        await callback.message.edit_reply_markup(
            reply_markup=returning_user_kb(charts=_charts_to_buttons(charts), page=page)
        )
    await callback.answer()


@start_router.callback_query(F.data.startswith("chart:open:"))
async def handle_chart_open(callback: CallbackQuery, session: AsyncSession) -> None:
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

    if isinstance(callback.message, Message):
        try:
            png = await _render_chart(chart)
        except Exception:
            logger.exception("chart_open.render_failed", chart_id=str(chart.id))
            await callback.message.answer(_format_chart_view(chart))
            await callback.answer()
            return
        title = _format_chart_label(chart)
        await callback.message.answer_photo(
            BufferedInputFile(png, "chart.png"),
            caption=f"<b>{title}</b>",
        )
    await callback.answer()


async def _render_chart(chart: Chart) -> bytes:
    chart_output = ChartOutput.model_validate(chart.chart_data)
    short_city = chart.chart_data.get("city_name") if chart.chart_data else None
    if isinstance(short_city, str) and "," in short_city:
        short_city = short_city.split(",")[0].strip()
    has_time = bool(chart.has_birth_time)
    time_part = chart.birth_datetime_original.strftime("%H:%M") if has_time else "без часа"
    subtitle_parts = [p for p in (short_city, time_part) if p]
    subtitle = " · ".join(subtitle_parts) if subtitle_parts else ""
    return await render_chart_png(
        RenderRequest(
            chart=chart_output,
            title=_format_chart_label(chart),
            subtitle=subtitle,
            has_birth_time=has_time,
        )
    )
