"""Shared helpers for the returning-user 'main menu' card list.

start.py owns the /start handler that first renders this menu, but other
routers (birth_data.py after the chart is named, future settings router)
also need to drop the user back into the same view. Keeping the helpers
in a dedicated service module avoids cross-router imports."""

import uuid

from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards import returning_user_kb
from db.models import Chart, User
from db.repositories.chart_repo import ChartRepository

GREETING_RETURNING_USER = "С возвращением, {name}. Что вас интересует сегодня?"
GREETING_AFTER_NAMING = "Что планируете дальше?"

_chart_repo = ChartRepository()


def format_chart_label(chart: Chart) -> str:
    """Button label shown in the returning-user menu.

    Legacy charts created before the naming flow had Chart.name auto-set
    to the city's full address (e.g. 'Волжский, Волгоградская область,
    Россия'). A name with commas almost certainly came from there, so
    treat it as auto-generated and fall through to day-master + date.
    """
    if chart.name and "," not in chart.name:
        return chart.name
    date_str = chart.birth_datetime_original.strftime("%d.%m.%Y")
    day_master = chart.chart_data.get("day_master", "?") if chart.chart_data else "?"
    return f"{day_master} {date_str}"


def charts_to_buttons(charts: list[Chart]) -> list[tuple[uuid.UUID, str]]:
    return [(chart.id, format_chart_label(chart)) for chart in charts]


async def send_main_menu(
    message: Message,
    user: User,
    session: AsyncSession,
    state: FSMContext | None = None,
    *,
    greeting: str | None = None,
) -> None:
    """Drop the user back into the returning-user menu after some action
    (named a chart, came back from a sub-flow). Lists all their charts,
    deduplicating same-date / same-place variants — the time-less version
    of an otherwise identical chart, for example, doesn't earn its own
    button.

    `greeting` overrides the default `GREETING_RETURNING_USER` prompt.
    Pass `GREETING_AFTER_NAMING` from naming-completion handlers so the
    user doesn't see the same return-greeting twice in a row.

    When `state` is given, the new message id is saved as the FSM anchor
    so the next inline button click can edit this card in place rather
    than appending another bubble below.
    """
    charts = await _chart_repo.list_unique_by_user(session, user.id)
    text = greeting or GREETING_RETURNING_USER.format(name=user.first_name)
    sent = await message.answer(
        text,
        reply_markup=returning_user_kb(charts=charts_to_buttons(charts)),
    )
    if state is not None:
        await state.update_data(fsm_msg_id=sent.message_id)
