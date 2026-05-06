import re
from datetime import date, datetime, time
from typing import Final

import dateparser
import structlog
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from bot.keyboards import time_skip_kb
from bot.states import BirthDataForm

logger = structlog.get_logger(__name__)

birth_data_router = Router(name="birth_data")

YEAR_RE: Final[re.Pattern[str]] = re.compile(r"\b(18|19|20)\d{2}\b")
TIME_RE: Final[re.Pattern[str]] = re.compile(r"^\s*(\d{1,2})[:.\- ](\d{2})\s*$")
HOUR_ONLY_RE: Final[re.Pattern[str]] = re.compile(r"^\s*(\d{1,2})\s*$")
MIN_YEAR: Final = 1900

DATE_PROMPT = (
    "Назови дату своего рождения.\n\n"
    "Можно цифрами (15.07.1990, 1990-07-15) или словами (15 июля 1990)."
)
DATE_INVALID = "Не разобрала дату. Попробуй ещё раз — например: 15.07.1990"
DATE_FUTURE = "Дата в будущем. Назови дату своего рождения."
DATE_TOO_OLD = f"Слишком давняя дата. Я работаю с датами не раньше {MIN_YEAR} года."
DATE_ACCEPTED = (
    "Принято: {formatted}.\n\n"
    "Теперь время рождения — час и минуты, например 14:30. "
    "Если время неизвестно — нажми кнопку ниже."
)

TIME_INVALID = "Не разобрала время. Формат — HH:MM, например 09:15 или 14:30."
TIME_ACCEPTED = "Принято: {formatted}.\n\nДальше — город рождения."
TIME_SKIPPED = (
    "Хорошо, посчитаю карту на полдень. Анализ будет упрощённым — без столпа часа.\n\n"
    "Дальше — город рождения."
)


def _parse_birth_date(text: str) -> date | None:
    if not YEAR_RE.search(text):
        return None
    parsed: datetime | None = dateparser.parse(text, languages=["ru", "en"])
    if parsed is None:
        return None
    return parsed.date()


def _parse_birth_time(text: str) -> time | None:
    match = TIME_RE.match(text)
    if match is not None:
        hours, minutes = int(match.group(1)), int(match.group(2))
        if 0 <= hours <= 23 and 0 <= minutes <= 59:
            return time(hours, minutes)
        return None
    match = HOUR_ONLY_RE.match(text)
    if match is not None:
        hours = int(match.group(1))
        if 0 <= hours <= 23:
            return time(hours, 0)
    return None


@birth_data_router.callback_query(F.data == "menu:calc")
async def handle_calc(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(BirthDataForm.waiting_date)
    if isinstance(callback.message, Message):
        await callback.message.answer(DATE_PROMPT)
    await callback.answer()


@birth_data_router.message(BirthDataForm.waiting_date, F.text)
async def handle_date(message: Message, state: FSMContext) -> None:
    parsed = _parse_birth_date(message.text or "")
    if parsed is None:
        await message.answer(DATE_INVALID)
        return

    today = datetime.now().date()
    if parsed > today:
        await message.answer(DATE_FUTURE)
        return
    if parsed.year < MIN_YEAR:
        await message.answer(DATE_TOO_OLD)
        return

    await state.update_data(birth_date=parsed.isoformat())
    await state.set_state(BirthDataForm.waiting_time)

    logger.info(
        "birth_data.date_accepted",
        telegram_id=message.from_user.id if message.from_user else None,
        date=parsed.isoformat(),
    )
    await message.answer(
        DATE_ACCEPTED.format(formatted=parsed.strftime("%d.%m.%Y")),
        reply_markup=time_skip_kb(),
    )


@birth_data_router.message(BirthDataForm.waiting_time, F.text)
async def handle_time(message: Message, state: FSMContext) -> None:
    parsed = _parse_birth_time(message.text or "")
    if parsed is None:
        await message.answer(TIME_INVALID, reply_markup=time_skip_kb())
        return

    await state.update_data(birth_time=parsed.isoformat(), has_birth_time=True)
    await state.set_state(BirthDataForm.waiting_city)

    logger.info(
        "birth_data.time_accepted",
        telegram_id=message.from_user.id if message.from_user else None,
        time=parsed.isoformat(),
    )
    await message.answer(TIME_ACCEPTED.format(formatted=parsed.strftime("%H:%M")))


@birth_data_router.callback_query(BirthDataForm.waiting_time, F.data == "time:skip")
async def handle_time_skip(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(birth_time=None, has_birth_time=False)
    await state.set_state(BirthDataForm.waiting_city)

    logger.info(
        "birth_data.time_skipped",
        telegram_id=callback.from_user.id if callback.from_user else None,
    )
    if isinstance(callback.message, Message):
        await callback.message.answer(TIME_SKIPPED)
    await callback.answer()
