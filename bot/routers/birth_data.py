import re
from datetime import date, datetime, time
from typing import Final

import dateparser
import structlog
from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.keyboards import (
    back_to_time_kb,
    city_choice_kb,
    confirm_kb,
    edit_menu_kb,
    gender_kb,
    name_skip_kb,
    time_step_kb,
)
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
# Permissive time separators: colon, dot, comma, dash, slash, space, "ч"/"h"
TIME_RE: Final[re.Pattern[str]] = re.compile(r"^\s*(\d{1,2})\s*[:.,\-/\sчh]\s*(\d{2})\s*$")
# 3 digits: HMM (e.g. 955 → 9:55). 4 digits: HHMM (e.g. 2355 → 23:55).
TIME_PACKED_RE: Final[re.Pattern[str]] = re.compile(r"^\s*(\d{3,4})\s*$")
HOUR_ONLY_RE: Final[re.Pattern[str]] = re.compile(r"^\s*(\d{1,2})\s*[чh]?\s*$")
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
    "Не разобрала «{text}». Можно так: 14:30, 14.30, 14,30, 14-30, 1430, или просто час: 14."
)
TIME_ACCEPTED = "Принято: {formatted}.\n\nНапиши свой город рождения:"
TIME_SKIPPED = (
    "Хорошо. Без точного часа я анализирую только три столпа из четырёх — год, месяц "
    "и день. Столп часа в анализе не появится.\n\n"
    "Напиши свой город рождения:"
)

CITY_PROMPT = "Напиши свой город рождения:"
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

CALC_RESULT_HEADER_FULL = "Карта рассчитана."
CALC_RESULT_HEADER_NO_HOUR = "Карта рассчитана (без столпа часа — время неизвестно)."
CALC_PILLARS_FULL = (
    "<b>Четыре столпа:</b>\n  Год: {year}\n  Месяц: {month}\n  День: {day}\n  Час: {hour}"
)
CALC_PILLARS_NO_HOUR = "<b>Три столпа:</b>\n  Год: {year}\n  Месяц: {month}\n  День: {day}"
CALC_RESULT_FOOTER = (
    "<b>Дневной мастер:</b> {day_master}\n"
    "<b>Баланс элементов:</b> {balance}\n\n"
    "Дальше я научусь интерпретировать эту карту словами — следующая большая фича."
)
CALC_FAILED = "Что-то пошло не так при расчёте. Попробуй ещё раз через /start."
RESTART_PROMPT = "Хорошо, начинаем заново. " + DATE_PROMPT
NAME_PROMPT = (
    "Хочешь дать карте имя? Можно написать своё (например, «Я» или «Маша») "
    "или нажать «Пропустить» — тогда карта будет показываться как "
    "{day_master} {date}."
)
NAME_SAVED = "Сохранила: «{name}»."
NAME_SKIPPED = "Хорошо, оставлю по умолчанию."

EDIT_MENU_PROMPT = "Что хочешь поправить?"
EDIT_PROMPTS = {
    "date": DATE_PROMPT,
    "time": "Назови время рождения — например 14:30. Если не помнишь — нажми кнопку.",
    "city": CITY_PROMPT,
    "gender": "Выбери пол:",
}

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
    match = TIME_PACKED_RE.match(text)
    if match is not None:
        digits = match.group(1)
        hours, minutes = int(digits[:-2]), int(digits[-2:])
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
    logger.info(
        "birth_data.date_accepted",
        telegram_id=message.from_user.id if message.from_user else None,
        date=parsed.isoformat(),
    )
    if await _is_edit_mode(state):
        await _back_to_confirm(message, state)
        return
    await state.set_state(BirthDataForm.waiting_time)
    await message.answer(
        DATE_ACCEPTED.format(formatted=parsed.strftime("%d.%m.%Y")),
        reply_markup=time_step_kb(),
    )


@birth_data_router.message(BirthDataForm.waiting_time, F.text)
async def handle_time(message: Message, state: FSMContext) -> None:
    text = message.text or ""
    parsed = _parse_birth_time(text)
    if parsed is None:
        await message.answer(TIME_INVALID.format(text=text), reply_markup=time_step_kb())
        return

    await state.update_data(birth_time=parsed.isoformat(), has_birth_time=True)
    logger.info(
        "birth_data.time_accepted",
        telegram_id=message.from_user.id if message.from_user else None,
        time=parsed.isoformat(),
    )
    if await _is_edit_mode(state):
        await _back_to_confirm(message, state)
        return
    await state.set_state(BirthDataForm.waiting_city)
    await message.answer(
        TIME_ACCEPTED.format(formatted=parsed.strftime("%H:%M")),
        reply_markup=back_to_time_kb(),
    )


@birth_data_router.callback_query(BirthDataForm.waiting_time, F.data == "time:skip")
async def handle_time_skip(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(birth_time=None, has_birth_time=False)
    logger.info(
        "birth_data.time_skipped",
        telegram_id=callback.from_user.id if callback.from_user else None,
    )
    if await _is_edit_mode(state):
        if isinstance(callback.message, Message):
            await _back_to_confirm(callback.message, state)
        await callback.answer()
        return
    await state.set_state(BirthDataForm.waiting_city)
    if isinstance(callback.message, Message):
        await callback.message.answer(TIME_SKIPPED, reply_markup=back_to_time_kb())
    await callback.answer()


@birth_data_router.message(BirthDataForm.waiting_city, F.text)
async def handle_city(message: Message, state: FSMContext) -> None:
    query = (message.text or "").strip()
    candidates = await search_cities(query, limit=3)
    if not candidates:
        await message.answer(CITY_NOT_FOUND.format(query=query), reply_markup=back_to_time_kb())
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
    logger.info(
        "birth_data.city_accepted",
        telegram_id=callback.from_user.id if callback.from_user else None,
        timezone=chosen["timezone"],
    )
    if await _is_edit_mode(state):
        if isinstance(callback.message, Message):
            await _back_to_confirm(callback.message, state)
        await callback.answer()
        return
    await state.set_state(BirthDataForm.waiting_gender)
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
    logger.info(
        "birth_data.gender_accepted",
        telegram_id=callback.from_user.id if callback.from_user else None,
        gender=value,
    )
    if isinstance(callback.message, Message):
        await _back_to_confirm(callback.message, state)
    await callback.answer()


async def _is_edit_mode(state: FSMContext) -> bool:
    """gender is the last field set in the linear flow — its presence in
    FSM data uniquely identifies "user came from the edit menu, every other
    field is already valid". Used by date/time/city handlers to decide
    whether to advance to the next step or jump back to the summary."""
    data = await state.get_data()
    return bool(data.get("gender")) and bool(data.get("city_name"))


async def _back_to_confirm(message: Message, state: FSMContext) -> None:
    await state.set_state(BirthDataForm.confirm)
    data = await state.get_data()
    await message.answer(_format_summary(data), reply_markup=confirm_kb())


@birth_data_router.callback_query(BirthDataForm.confirm, F.data == "edit:menu")
async def handle_edit_menu(callback: CallbackQuery) -> None:
    if isinstance(callback.message, Message):
        await callback.message.answer(EDIT_MENU_PROMPT, reply_markup=edit_menu_kb())
    await callback.answer()


@birth_data_router.callback_query(BirthDataForm.confirm, F.data == "edit:cancel")
async def handle_edit_cancel(callback: CallbackQuery, state: FSMContext) -> None:
    if isinstance(callback.message, Message):
        await _back_to_confirm(callback.message, state)
    await callback.answer()


@birth_data_router.callback_query(BirthDataForm.confirm, F.data == "edit:date")
async def handle_edit_date(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(BirthDataForm.waiting_date)
    if isinstance(callback.message, Message):
        await callback.message.answer(EDIT_PROMPTS["date"])
    await callback.answer()


@birth_data_router.callback_query(BirthDataForm.confirm, F.data == "edit:time")
async def handle_edit_time(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(BirthDataForm.waiting_time)
    if isinstance(callback.message, Message):
        await callback.message.answer(EDIT_PROMPTS["time"], reply_markup=time_step_kb())
    await callback.answer()


@birth_data_router.callback_query(BirthDataForm.confirm, F.data == "edit:city")
async def handle_edit_city(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(BirthDataForm.waiting_city)
    if isinstance(callback.message, Message):
        await callback.message.answer(EDIT_PROMPTS["city"])
    await callback.answer()


@birth_data_router.callback_query(BirthDataForm.confirm, F.data == "edit:gender")
async def handle_edit_gender(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(BirthDataForm.waiting_gender)
    if isinstance(callback.message, Message):
        await callback.message.answer(EDIT_PROMPTS["gender"], reply_markup=gender_kb())
    await callback.answer()


def _format_summary(data: dict[str, str | float | bool | None]) -> str:
    birth_time = data.get("birth_time")
    has_time = bool(data.get("has_birth_time"))
    if has_time and isinstance(birth_time, str):
        time_str = birth_time[:5]
    else:
        time_str = "не указано — столп часа в анализ не войдёт"

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


@birth_data_router.callback_query(F.data == "fsm:restart")
async def handle_fsm_restart(callback: CallbackQuery, state: FSMContext) -> None:
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
        result = await _calculate_and_persist(data, user=user, session=session)
    except Exception:
        logger.exception(
            "birth_data.calc_failed",
            telegram_id=callback.from_user.id if callback.from_user else None,
        )
        if isinstance(callback.message, Message):
            await callback.message.answer(CALC_FAILED)
        await callback.answer()
        return

    chart_id = result["chart_id"]
    day_master = result["day_master"]
    date_str = result["date_str"]
    if isinstance(callback.message, Message):
        await callback.message.answer(_format_chart_summary(result))
        await state.set_state(BirthDataForm.naming)
        await state.update_data(chart_id=str(chart_id))
        await callback.message.answer(
            NAME_PROMPT.format(day_master=day_master, date=date_str),
            reply_markup=name_skip_kb(),
        )
    await callback.answer()


@birth_data_router.message(BirthDataForm.naming, F.text)
async def handle_naming_input(message: Message, state: FSMContext, session: AsyncSession) -> None:
    name = (message.text or "").strip()
    if not name:
        return
    data = await state.get_data()
    raw_id = data.get("chart_id")
    if not isinstance(raw_id, str):
        await state.clear()
        return
    import uuid as _uuid

    await _chart_repo.update_name(session, _uuid.UUID(raw_id), name)
    await state.clear()
    await message.answer(NAME_SAVED.format(name=name))


@birth_data_router.callback_query(BirthDataForm.naming, F.data == "name:skip")
async def handle_naming_skip(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if isinstance(callback.message, Message):
        await callback.message.answer(NAME_SKIPPED)
    await callback.answer()


async def _calculate_and_persist(
    data: dict[str, str | float | bool | None],
    *,
    user: User,
    session: AsyncSession,
) -> dict[str, object]:
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

    chart = await _chart_repo.create(
        session,
        user_id=user.id,
        birth_datetime_utc=resolved.utc_aware.replace(tzinfo=None),
        birth_datetime_original=resolved.naive_local,
        latitude=lat,
        longitude=lon,
        tz_offset=resolved.tz_offset_hours,
        chart_data=chart_data,
        name=None,
        has_birth_time=has_time,
    )
    # city_name is no longer stored on Chart.name (the user names the chart in
    # the next step) — we keep it in chart_data for record-keeping.
    chart_data["city_name"] = city_name

    return {
        "chart_id": chart.id,
        "date_str": resolved.naive_local.strftime("%d.%m.%Y"),
        "pillars": chart_data["pillars"],
        "day_master": chart_data["day_master"],
        "element_balance": chart_data["element_balance"],
        "has_birth_time": has_time,
    }


def _format_chart_summary(chart: dict[str, object]) -> str:
    pillars = chart["pillars"]
    assert isinstance(pillars, list)
    year, month, day, hour = pillars[0], pillars[1], pillars[2], pillars[3]
    balance = chart["element_balance"]
    assert isinstance(balance, dict)
    balance_str = ", ".join(f"{k} {v:.0%}" for k, v in balance.items())
    day_master = chart["day_master"]
    assert isinstance(day_master, str)
    has_time = bool(chart.get("has_birth_time"))

    if has_time:
        header = CALC_RESULT_HEADER_FULL
        pillars_block = CALC_PILLARS_FULL.format(
            year=f"{year['stem']}{year['branch']}",
            month=f"{month['stem']}{month['branch']}",
            day=f"{day['stem']}{day['branch']}",
            hour=f"{hour['stem']}{hour['branch']}",
        )
    else:
        header = CALC_RESULT_HEADER_NO_HOUR
        pillars_block = CALC_PILLARS_NO_HOUR.format(
            year=f"{year['stem']}{year['branch']}",
            month=f"{month['stem']}{month['branch']}",
            day=f"{day['stem']}{day['branch']}",
        )
    footer = CALC_RESULT_FOOTER.format(day_master=day_master, balance=balance_str)
    return f"{header}\n\n{pillars_block}\n\n{footer}"
