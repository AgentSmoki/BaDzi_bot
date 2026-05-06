import structlog
from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards import new_user_kb, returning_user_kb
from db.models import Chart, User
from db.repositories.chart_repo import ChartRepository

logger = structlog.get_logger(__name__)

start_router = Router(name="start")
_chart_repo = ChartRepository()

GREETING_NEW_USER = (
    "Здравствуй, {name}. Меня зовут Анастасия — я консультант по древнекитайской "
    "системе Ба Цзы.\n\n"
    "Эта система читает карту твоего рождения как карту местности: показывает сильные "
    "стороны, ритмы судьбы, благоприятные годы и узкие места.\n\n"
    "<blockquote>Мастер ЭдоХа:\n"
    "<i>БаЦзы — это наука о том как оказаться в нужное время, месте с правильными "
    "людьми.</i></blockquote>\n\n"
    "Я не предсказываю — я помогаю увидеть рисунок, по которому идёт твоя жизнь.\n\n"
    "Расчёт карты и базовое прочтение бесплатны для всех. Чтобы начать — нужны "
    "точные данные твоего рождения: дата, время и город."
)

GREETING_RETURNING_USER = "С возвращением, {name}. Что тебя интересует сегодня?"


def _format_chart_label(chart: Chart) -> str:
    label = chart.birth_datetime_original.strftime("%d.%m.%Y %H:%M")
    if chart.name:
        label = f"{label} — {chart.name}"
    return label


@start_router.message(CommandStart())
async def handle_start(
    message: Message, user: User, session: AsyncSession, state: FSMContext
) -> None:
    await state.clear()
    last_chart = await _chart_repo.get_latest_by_user(session, user.id)

    if last_chart is None:
        logger.info("start.new_user", telegram_id=user.telegram_id, user_id=str(user.id))
        await message.answer(
            GREETING_NEW_USER.format(name=user.first_name),
            reply_markup=new_user_kb(),
        )
        return

    logger.info("start.returning_user", telegram_id=user.telegram_id, user_id=str(user.id))
    await message.answer(
        GREETING_RETURNING_USER.format(name=user.first_name),
        reply_markup=returning_user_kb(
            chart_id=last_chart.id,
            chart_label=_format_chart_label(last_chart),
        ),
    )
