import re
from datetime import date, datetime, time
from typing import Final

import dateparser
import structlog
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards import city_choice_kb, confirm_kb, gender_kb, time_skip_kb
from bot.services.birth_datetime import resolve as resolve_birth_datetime
from bot.services.geocoding import search_cities
from bot.states import BirthDataForm
from calculator import calculate_chart
from calculator.models import ChartInput
from db.models import User
from db.repositories.chart_repo import ChartRepository

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
DATE_INVALID = (
    "Не разобрала «{text}». Можно цифрами (15.07.1990), словами (15 июля 1990) "
    "или ISO (1990-07-15). Главное — год должен быть."
)
DATE_FUTURE = "«{text}» — дата в будущем. Нужна твоя дата рождения."
DATE_TOO_OLD = (
    f"«{{text}}» раньше {MIN_YEAR} года — я с такими датами не работаю. "
    "Проверь, правильно ли указан год."
)
DATE_ACCEPTED = (
    "Принято: {formatted}.\n\n"
    "Теперь время рождения — час и минуты, например 14:30. "
    "Если время неизвестно — нажми кнопку ниже."
)

TIME_INVALID = (
    "Не разобрала «{text}». Формат — ЧЧ:ММ, например 09:15 или 14:30. Можно и просто час: 14."
)
TIME_ACCEPTED = "Принято: {formatted}.\n\nТеперь город рождения."
TIME_SKIPPED = (
    "Хорошо, посчитаю карту на полдень. Анализ будет упрощённым — без столпа часа.\n\n"
    "Теперь город рождения."
)

CITY_PROMPT = "Назови город рождения. Можно по-русски или по-английски."
CITY_NOT_FOUND = (
    "Не нашла «{query}». Похоже на опечатку — проверь написание и попробуй ещё раз. "
    "Можно с уточнением региона: «Тверь, Тверская область»."
)
CITY_CHOICES = "Нашла несколько вариантов — выбери свой:"
CITY_ACCEPTED = "Принято: {name}.\n\nПоследний шаг — твой пол."

GENDER_PROMPT = "Выбери пол:"
SUMMARY_TEMPLATE = (
    "Проверь данные:\n\n"
    "<b>Дата:</b> {date}\n"
    "<b>Время:</b> {time}\n"
    "<b>Город:</b> {city}\n"
    "<b>Часовой пояс:</b> {timezone}\n"
    "<b>Пол:</b> {gender}\n\n"
    "Если всё верно — рассчитываю карту."
)
GENDER_LABELS = {"male": "мужской", "female": "женский"}

CALC_RESULT_TEMPLATE = (
    "Карта рассчитана.\n\n"
    "<b>Четыре столпа:</b>\n"
    "  Год: {year_stem}{year_branch}\n"
    "  Месяц: {month_stem}{month_branch}\n"
    "  День: {day_stem}{day_branch}\n"
    "  Час: {hour_stem}{hour_branch}\n\n"
    "<b>Дневной мастер:</b> {day_master}\n"
    "<b>Баланс элементов:</b> {balance}\n\n"
    "Дальше я научусь интерпретировать эту карту словами — следующая большая фича."
)
CALC_FAILED = "Что-то пошло не так при расчёте. Попробуй ещё раз через /start."
RESTART_PROMPT = "Хорошо, начинаем заново. " + DATE_PROMPT

_chart_repo = ChartRepository()


def _parse_birth_date(text: str) -> date | None:
    if not YEAR_RE.search(text):
        return None
    # DATE_ORDER=DMY: in en locale dateparser defaults to MM.DD.YYYY which is
    # surprising for Russian users — force day-month-year for both locales.
    parsed: datetime | None = dateparser.parse(
        text,
        languages=["ru", "en"],
        settings={"DATE_ORDER": "DMY"},
    )
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
    text = message.text or ""
    parsed = _parse_birth_date(text)
    if parsed is None:
        await message.answer(DATE_INVALID.format(text=text))
        return

    today = datetime.now().date()
    if parsed > today:
        await message.answer(DATE_FUTURE.format(text=text))
        return
    if parsed.year < MIN_YEAR:
        await message.answer(DATE_TOO_OLD.format(text=text))
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
    text = message.text or ""
    parsed = _parse_birth_time(text)
    if parsed is None:
        await message.answer(TIME_INVALID.format(text=text), reply_markup=time_skip_kb())
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


@birth_data_router.message(BirthDataForm.waiting_city, F.text)
async def handle_city(message: Message, state: FSMContext) -> None:
    query = (message.text or "").strip()
    candidates = await search_cities(query, limit=3)
    if not candidates:
        await message.answer(CITY_NOT_FOUND.format(query=query))
        return

    await state.update_data(city_candidates=[c.to_dict() for c in candidates])
    options = [(c.short_label(), f"city:{i}") for i, c in enumerate(candidates)]
    await message.answer(CITY_CHOICES, reply_markup=city_choice_kb(options))


@birth_data_router.callback_query(BirthDataForm.waiting_city, F.data == "city:retry")
async def handle_city_retry(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(city_candidates=None)
    if isinstance(callback.message, Message):
        await callback.message.answer(CITY_PROMPT)
    await callback.answer()


@birth_data_router.callback_query(BirthDataForm.waiting_city, F.data.startswith("city:"))
async def handle_city_choice(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data:
        await callback.answer()
        return
    try:
        idx = int(callback.data.split(":", 1)[1])
    except ValueError:
        await callback.answer()
        return

    data = await state.get_data()
    candidates = data.get("city_candidates") or []
    if idx < 0 or idx >= len(candidates):
        await callback.answer("Этот вариант устарел, введи город заново.", show_alert=True)
        return

    chosen = candidates[idx]
    await state.update_data(
        city_name=chosen["display_name"],
        latitude=chosen["latitude"],
        longitude=chosen["longitude"],
        timezone=chosen["timezone"],
        city_candidates=None,
    )
    await state.set_state(BirthDataForm.waiting_gender)

    logger.info(
        "birth_data.city_accepted",
        telegram_id=callback.from_user.id if callback.from_user else None,
        timezone=chosen["timezone"],
    )
    if isinstance(callback.message, Message):
        await callback.message.answer(
            CITY_ACCEPTED.format(name=chosen["display_name"]),
            reply_markup=gender_kb(),
        )
    await callback.answer()


@birth_data_router.callback_query(BirthDataForm.waiting_gender, F.data.startswith("gender:"))
async def handle_gender(callback: CallbackQuery, state: FSMContext) -> None:
    if not callback.data:
        await callback.answer()
        return
    value = callback.data.split(":", 1)[1]
    if value not in ("male", "female"):
        await callback.answer()
        return

    await state.update_data(gender=value)
    await state.set_state(BirthDataForm.confirm)

    data = await state.get_data()
    summary = _format_summary(data)

    logger.info(
        "birth_data.gender_accepted",
        telegram_id=callback.from_user.id if callback.from_user else None,
        gender=value,
    )
    if isinstance(callback.message, Message):
        await callback.message.answer(summary, reply_markup=confirm_kb())
    await callback.answer()


def _format_summary(data: dict[str, str | float | bool | None]) -> str:
    birth_time = data.get("birth_time")
    has_time = bool(data.get("has_birth_time"))
    if has_time and isinstance(birth_time, str):
        time_str = birth_time[:5]
    else:
        time_str = "не указано (карта будет упрощённой)"

    raw_date = data.get("birth_date")
    date_str = (
        date.fromisoformat(raw_date).strftime("%d.%m.%Y") if isinstance(raw_date, str) else "—"
    )
    gender_value = data.get("gender")
    gender_label = GENDER_LABELS.get(gender_value, "—") if isinstance(gender_value, str) else "—"
    city_name = data.get("city_name") if isinstance(data.get("city_name"), str) else "—"
    tz = data.get("timezone") if isinstance(data.get("timezone"), str) else "—"

    return SUMMARY_TEMPLATE.format(
        date=date_str,
        time=time_str,
        city=city_name,
        timezone=tz,
        gender=gender_label,
    )


@birth_data_router.callback_query(BirthDataForm.confirm, F.data == "confirm:restart")
async def handle_confirm_restart(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(BirthDataForm.waiting_date)
    if isinstance(callback.message, Message):
        await callback.message.answer(RESTART_PROMPT)
    await callback.answer()


@birth_data_router.callback_query(BirthDataForm.confirm, F.data == "confirm:calc")
async def handle_confirm_calc(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
) -> None:
    data = await state.get_data()
    try:
        chart = await _calculate_and_persist(data, user=user, session=session)
    except Exception:
        logger.exception(
            "birth_data.calc_failed",
            telegram_id=callback.from_user.id if callback.from_user else None,
        )
        if isinstance(callback.message, Message):
            await callback.message.answer(CALC_FAILED)
        await callback.answer()
        return

    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.answer(_format_chart_summary(chart))
    await callback.answer()


async def _calculate_and_persist(
    data: dict[str, str | float | bool | None],
    *,
    user: User,
    session: AsyncSession,
) -> dict[str, str | dict[str, str]]:
    raw_date = data["birth_date"]
    raw_time = data.get("birth_time")
    has_time = bool(data.get("has_birth_time"))
    tz_iana = data["timezone"]
    lat = data["latitude"]
    lon = data["longitude"]
    gender = data["gender"]
    city_name = data["city_name"]
    assert isinstance(raw_date, str) and isinstance(tz_iana, str)
    assert isinstance(lat, float) and isinstance(lon, float)
    assert isinstance(gender, str) and isinstance(city_name, str)

    resolved = resolve_birth_datetime(
        birth_date=raw_date,
        birth_time=raw_time if isinstance(raw_time, str) else None,
        tz_iana=tz_iana,
    )

    chart_input = ChartInput(
        birth_datetime=resolved.naive_local,
        latitude=lat,
        longitude=lon,
        tz_offset=resolved.tz_offset_hours,
        gender=gender,  # type: ignore[arg-type]
    )
    chart_output = calculate_chart(chart_input)
    chart_data = chart_output.model_dump(mode="json")

    await _chart_repo.create(
        session,
        user_id=user.id,
        birth_datetime_utc=resolved.utc_aware.replace(tzinfo=None),
        birth_datetime_original=resolved.naive_local,
        latitude=lat,
        longitude=lon,
        tz_offset=resolved.tz_offset_hours,
        chart_data=chart_data,
        name=city_name,
        has_birth_time=has_time,
    )

    return {
        "pillars": chart_data["pillars"],
        "day_master": chart_data["day_master"],
        "element_balance": chart_data["element_balance"],
    }


def _format_chart_summary(chart: dict[str, str | dict[str, str]]) -> str:
    pillars = chart["pillars"]
    assert isinstance(pillars, list)
    year, month, day, hour = pillars[0], pillars[1], pillars[2], pillars[3]
    balance = chart["element_balance"]
    assert isinstance(balance, dict)
    balance_str = ", ".join(f"{k} {v:.0%}" for k, v in balance.items())
    day_master = chart["day_master"]
    assert isinstance(day_master, str)
    return CALC_RESULT_TEMPLATE.format(
        year_stem=year["stem"],
        year_branch=year["branch"],
        month_stem=month["stem"],
        month_branch=month["branch"],
        day_stem=day["stem"],
        day_branch=day["branch"],
        hour_stem=hour["stem"],
        hour_branch=hour["branch"],
        day_master=day_master,
        balance=balance_str,
    )
