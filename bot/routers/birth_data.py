import asyncio
import re
from datetime import date, datetime, time
from typing import Any, Final

import dateparser
import structlog
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from ai.card_renderer import RenderRequest, render_chart_png
from ai.text_extract import ExtractedBirthData, extract_birth_data
from bot.keyboards import (
    back_to_time_kb,
    calc_intro_kb,
    city_choice_kb,
    confirm_kb,
    edit_menu_kb,
    gender_kb,
    name_skip_kb,
    time_step_kb,
)
from bot.services.birth_datetime import resolve as resolve_birth_datetime
from bot.services.geocoding import search_cities
from bot.services.menu import GREETING_AFTER_NAMING, send_main_menu
from bot.states import BirthDataForm
from calculator import calculate_chart
from calculator.models import ChartInput, ChartOutput
from db.models import User
from db.repositories.chart_repo import ChartRepository

logger = structlog.get_logger(__name__)

birth_data_router = Router(name="birth_data")

YEAR_RE: Final[re.Pattern[str]] = re.compile(r"\b(18|19|20)\d{2}\b")
# Packed numeric date — 8 digits, DDMMYYYY: 12091999 → 12.09.1999.
PACKED_DATE_RE: Final[re.Pattern[str]] = re.compile(r"^\s*(\d{2})(\d{2})(\d{4})\s*$")
# ISO format YYYY-MM-DD (1990-05-15). Wave 1a — Bogdan reports this didn't
# parse before because YEAR_RE found the year but dateparser with
# DATE_ORDER=DMY guessed day-month-year and confused the layout.
ISO_DATE_RE: Final[re.Pattern[str]] = re.compile(r"^\s*(\d{4})-(\d{1,2})-(\d{1,2})\s*$")
# Two-digit year forms: dd.mm.yy / dd-mm-yy / dd/mm/yy / dd mm yy
# (27.04.88 → 27.04.1988). Separators match _parse_birth_time spirit.
SHORT_YEAR_DOT_RE: Final[re.Pattern[str]] = re.compile(
    r"^\s*(\d{1,2})[.,\-/\s](\d{1,2})[.,\-/\s](\d{2})\s*$"
)
# Packed 6 digits ddmmyy (270488 → 27.04.1988).
SHORT_YEAR_PACKED_RE: Final[re.Pattern[str]] = re.compile(r"^\s*(\d{2})(\d{2})(\d{2})\s*$")
# Permissive time separators: colon, dot, comma, dash, slash, space, "ч"/"h"
TIME_RE: Final[re.Pattern[str]] = re.compile(r"^\s*(\d{1,2})\s*[:.,\-/\sчh]\s*(\d{2})\s*$")
# 3 digits: HMM (e.g. 955 → 9:55). 4 digits: HHMM (e.g. 2355 → 23:55).
TIME_PACKED_RE: Final[re.Pattern[str]] = re.compile(r"^\s*(\d{3,4})\s*$")
HOUR_ONLY_RE: Final[re.Pattern[str]] = re.compile(r"^\s*(\d{1,2})\s*[чh]?\s*$")
MIN_YEAR: Final = 1900

# Pre-delete pause for `_swallow_user_message`. Long enough that the
# user reads the bot's "Принято: ..." reply before their own message
# fades, short enough that the chat doesn't feel laggy. Telegram itself
# animates the deletion, this just shifts the trigger so the animation
# isn't competing with the bot reply rendering for the user's eye.
SWALLOW_FADE_DELAY_MS: Final = 450

DATE_PROMPT = (
    "Назовите дату вашего рождения.\n\n"
    "Можно цифрами (15.07.1990, 1990-07-15, 15071990) или словами (15 июля 1990)."
)
# Wave 2 — smart entry. Encourages the «one-line» path; the «Пошагово»
# button drops to the classic FSM (date → time → city → gender).
SMART_INTRO_PROMPT = (
    "Напишите данные рождения в одной строке — например:\n\n"
    "<i>27.04.1988 Севастополь 07:03 утра, мужчина</i>\n\n"
    "Я разберу что вы написали и спрошу только про то, чего не хватит."
)
SMART_EXTRACT_FAILED = (
    "Не разобрала текст автоматически — давайте по шагам. Назовите дату рождения."
)
SMART_EXTRACT_PARTIAL = "Записала что смогла. Уточните, пожалуйста, недостающее."
PARTNER_DATE_PROMPT = (
    "Чтобы сравнить вашу карту с картой партнёра, мне нужны его данные.\n\n" + DATE_PROMPT
)
PARTNER_SAVED_MSG = (
    "Карта партнёра сохранена. Я подключила её к вашему вопросу — "
    "сейчас отвечу с учётом обеих карт."
)
DATE_INVALID = (
    "Не разобрала «{text}». Можно цифрами (15.07.1990), словами (15 июля 1990), "
    "ISO (1990-07-15) или сплошным числом (15071990). Главное — год должен быть."
)
DATE_FUTURE = "«{text}» — дата в будущем. Нужна ваша дата рождения."
DATE_TOO_OLD = (
    f"«{{text}}» раньше {MIN_YEAR} года — я с такими датами не работаю. "
    "Проверьте, правильно ли указан год."
)
DATE_ACCEPTED = (
    "Принято: {formatted}.\n\n"
    "Теперь время рождения — час и минуты, например 14:30. "
    "Если время неизвестно — нажмите кнопку ниже."
)

TIME_INVALID = (
    "Не разобрала «{text}». Можно так: 14:30, 14.30, 14,30, 14-30, 1430, или просто час: 14."
)
TIME_ACCEPTED = "Принято: {formatted}.\n\nНапишите ваш город рождения:"
TIME_SKIPPED = (
    "Хорошо. Без точного часа я анализирую только три столпа из четырёх — год, месяц "
    "и день. Столп часа в анализе не появится.\n\n"
    "Напишите ваш город рождения:"
)

CITY_PROMPT = "Напишите ваш город рождения:"
CITY_NOT_FOUND = (
    "Не нашла «{query}». Похоже на опечатку — проверьте написание и попробуйте ещё раз. "
    "Можно с уточнением региона: «Тверь, Тверская область»."
)
CITY_CHOICES = "Нашла несколько вариантов — выберите свой:"
CITY_ACCEPTED = "Принято: {name}.\n\nПоследний шаг — ваш пол."

GENDER_PROMPT = "Выберите пол:"
SUMMARY_TEMPLATE = (
    "Проверьте данные:\n\n"
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
    "Хотите дать карте имя? Можно написать своё (например, «Я» или «Маша») "
    "или нажать «Пропустить» — тогда карта будет показываться как "
    "{day_master} {date}."
)
NAME_SAVED = "Сохранила: «{name}»."
NAME_SKIPPED = "Хорошо, оставлю по умолчанию."

EDIT_MENU_PROMPT = "Что хотите поправить?"
EDIT_PROMPTS = {
    "date": DATE_PROMPT,
    "time": "Назовите время рождения — например 14:30. Если не помните — нажмите кнопку.",
    "city": CITY_PROMPT,
    "gender": "Выберите пол:",
}

_chart_repo = ChartRepository()


async def _consume_buttons(callback: CallbackQuery) -> None:
    """Strip the inline keyboard from the message that triggered this callback
    so the chat doesn't accumulate stale FSM-step buttons. Used as a fallback
    when _step can't edit the original message."""
    if not isinstance(callback.message, Message):
        return
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception as exc:
        logger.debug("consume_buttons.skip", error=str(exc), exc_type=type(exc).__name__)


async def _swallow_user_message(message: Message) -> None:
    """Delete the user's text input so the chat shows only the bot's
    edit-in-place anchor. Telegram silently rejects deletes older than 48h
    or without delete-message permission — those failures are logged at
    debug level and ignored.

    A short pre-delete pause (``SWALLOW_FADE_DELAY_MS``) gives the user
    a beat to see their input was accepted before it disappears, and lets
    Telegram's natural fade-out animation be more noticeable instead of
    feeling like an abrupt vanish."""
    await asyncio.sleep(SWALLOW_FADE_DELAY_MS / 1000)
    try:
        await message.delete()
    except Exception as exc:
        logger.debug(
            "swallow_user_message.skip",
            error=str(exc),
            exc_type=type(exc).__name__,
        )


async def _step(
    *,
    bot: Bot,
    chat_id: int,
    state: FSMContext,
    text: str,
    kb: InlineKeyboardMarkup | None = None,
) -> None:
    """Edit the FSM-tracked message in place; fall back to a fresh message
    when the tracked message no longer exists or can't be edited (Telegram
    rejects edits older than 48h or with identical content). Either way the
    new message id is saved as the next anchor."""
    data = await state.get_data()
    raw_id = data.get("fsm_msg_id")
    if isinstance(raw_id, int):
        try:
            await bot.edit_message_text(
                chat_id=chat_id,
                message_id=raw_id,
                text=text,
                reply_markup=kb,
            )
            return
        except Exception as exc:
            logger.debug("step.edit_failed", error=str(exc), exc_type=type(exc).__name__)
    sent = await bot.send_message(chat_id=chat_id, text=text, reply_markup=kb)
    await state.update_data(fsm_msg_id=sent.message_id)


def _expand_2digit_year(yy: int) -> int:
    """Map 2-digit year to 4-digit (cutoff 30):
    - 00-29 → 2000-2029 (modern births / kids)
    - 30-99 → 1930-1999 (adults — overwhelming majority of Bazi clients)

    The cutoff is fixed (not «relative to today») so the mapping stays
    stable across years — moving with today would silently reshuffle
    old chart inputs on Dec 31."""
    return 2000 + yy if yy < 30 else 1900 + yy


def _parse_birth_date(text: str) -> date | None:
    """Parse a birth date from free-form text.

    Recognised formats (checked in order):
    1. ISO YYYY-MM-DD (1990-05-15) — picked off first because YEAR_RE
       hits but dateparser DATE_ORDER=DMY mis-parses
    2. Packed DDMMYYYY (12091999) — 8 digits
    3. Packed DDMMYY (270488) — 6 digits, applies 2-digit-year expansion
    4. Dotted/dashed/slashed DD.MM.YY (27.04.88 / 27/04/88)
    5. Anything else with a 4-digit year — handed to dateparser DMY
    """
    iso = ISO_DATE_RE.match(text)
    if iso is not None:
        try:
            return date(int(iso.group(1)), int(iso.group(2)), int(iso.group(3)))
        except ValueError:
            return None

    packed = PACKED_DATE_RE.match(text)
    if packed is not None:
        try:
            return date(int(packed.group(3)), int(packed.group(2)), int(packed.group(1)))
        except ValueError:
            return None

    short_packed = SHORT_YEAR_PACKED_RE.match(text)
    if short_packed is not None:
        try:
            return date(
                _expand_2digit_year(int(short_packed.group(3))),
                int(short_packed.group(2)),
                int(short_packed.group(1)),
            )
        except ValueError:
            return None

    short_dot = SHORT_YEAR_DOT_RE.match(text)
    if short_dot is not None:
        try:
            return date(
                _expand_2digit_year(int(short_dot.group(3))),
                int(short_dot.group(2)),
                int(short_dot.group(1)),
            )
        except ValueError:
            return None

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
async def handle_calc(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Smart-entry start (Wave 2): prompt for a one-liner; user may
    drop to stepwise mode via «Пошагово» button.

    Old «date first» behaviour preserved as the explicit stepwise
    fallback below (`calc:stepwise`)."""
    await state.set_state(BirthDataForm.waiting_full_text)
    if isinstance(callback.message, Message):
        await _step(
            bot=bot,
            chat_id=callback.message.chat.id,
            state=state,
            text=SMART_INTRO_PROMPT,
            kb=calc_intro_kb(),
        )
    await callback.answer()


@birth_data_router.callback_query(BirthDataForm.waiting_full_text, F.data == "calc:stepwise")
async def handle_calc_stepwise(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Escape hatch from smart-entry → classic FSM with date prompt."""
    await state.set_state(BirthDataForm.waiting_date)
    if isinstance(callback.message, Message):
        await _step(bot=bot, chat_id=callback.message.chat.id, state=state, text=DATE_PROMPT)
    await callback.answer()


@birth_data_router.message(BirthDataForm.waiting_full_text, F.text)
async def handle_full_text(message: Message, state: FSMContext, bot: Bot) -> None:
    """User pasted a free-form one-liner. LLM extract → fill FSM with
    whatever fields the model could read → route to the first missing
    step (or straight to confirm if nothing's missing)."""
    text = message.text or ""
    await _swallow_user_message(message)

    if not text.strip():
        return

    extract = await extract_birth_data(text)
    await _apply_extracted_to_fsm(extract, state)
    await _route_to_first_missing_step(state, bot, message.chat.id, extract)


async def _apply_extracted_to_fsm(extract: ExtractedBirthData, state: FSMContext) -> None:
    """Take whatever the LLM gave us and stage it into FSM data so the
    fallback FSM steps see it as «already entered». Validation happens
    later in the per-step handlers — bad inputs naturally re-prompt."""
    fsm_updates: dict[str, Any] = {}
    if extract.date_iso:
        fsm_updates["birth_date"] = extract.date_iso
    if extract.has_birth_time and extract.time_iso:
        fsm_updates["birth_time"] = extract.time_iso
        fsm_updates["has_birth_time"] = True
    elif extract.confidence >= 0.5 and extract.time_iso is None:
        # The LLM was confident the user said «без времени» — pre-skip
        # the time step. Low-confidence extractions don't pre-skip; the
        # FSM will still ask, so we don't silently lose the hour pillar.
        fsm_updates["has_birth_time"] = False
    if extract.gender:
        fsm_updates["gender"] = extract.gender
    if fsm_updates:
        await state.update_data(**fsm_updates)


async def _route_to_first_missing_step(
    state: FSMContext,
    bot: Bot,
    chat_id: int,
    extract: ExtractedBirthData,
) -> None:
    """Pick the next FSM state based on what's still missing.

    Priority order matches the linear FSM: date → time → city →
    gender → confirm. Time is skipped when the LLM confidently
    reported «без времени» (``has_birth_time=False`` set above)."""
    data = await state.get_data()

    has_date = bool(data.get("birth_date"))
    has_time_or_skipped = "has_birth_time" in data
    has_city = bool(data.get("city_name"))
    has_gender = bool(data.get("gender"))

    if not has_date:
        await state.set_state(BirthDataForm.waiting_date)
        await _step(
            bot=bot,
            chat_id=chat_id,
            state=state,
            text=(
                SMART_EXTRACT_FAILED
                if extract.confidence < 0.4
                else SMART_EXTRACT_PARTIAL + "\n\n" + DATE_PROMPT
            ),
        )
        return

    if not has_time_or_skipped:
        await state.set_state(BirthDataForm.waiting_time)
        await _step(
            bot=bot,
            chat_id=chat_id,
            state=state,
            text=SMART_EXTRACT_PARTIAL + "\n\nТеперь время рождения.",
            kb=time_step_kb(),
        )
        return

    if not has_city:
        await state.set_state(BirthDataForm.waiting_city)
        prompt = SMART_EXTRACT_PARTIAL + "\n\n" + CITY_PROMPT
        # If extract.city is set but geocoder wasn't run yet, prepopulate
        # the question so the user can correct it instead of re-typing.
        if extract.city:
            prompt = (
                SMART_EXTRACT_PARTIAL
                + f"\n\nЯ услышала «{extract.city}» — напишите ровно, "
                + "если правильно (или поправьте):"
            )
        await _step(bot=bot, chat_id=chat_id, state=state, text=prompt)
        return

    if not has_gender:
        await state.set_state(BirthDataForm.waiting_gender)
        await _step(
            bot=bot,
            chat_id=chat_id,
            state=state,
            text=SMART_EXTRACT_PARTIAL + "\n\n" + GENDER_PROMPT,
            kb=gender_kb(),
        )
        return

    # All four fields present → jump to confirm summary.
    await _back_to_confirm(bot, chat_id, state)


@birth_data_router.callback_query(F.data == "partner:add")
async def handle_add_partner_chart(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    """Entry point for the «Add partner chart» flow (Wave 6 / ADR-010).

    Triggered from the consultation handler when the skill-router
    flags ``needs_partner_chart=True`` and the user's main chart has
    no ``partner_chart_id`` yet. We reuse ``BirthDataForm`` for the
    actual data collection — the only difference is FSM data:
    ``mode="partner"``, ``owner_chart_id``, ``pending_question``.

    After the user confirms and the partner chart is calculated,
    ``_calculate_and_persist`` reads ``mode`` and calls
    ``ChartRepository.set_partner`` to link it to the owner chart.
    """
    data = await state.get_data()
    owner_chart_id = data.get("chart_id")
    pending_question = data.get("pending_question")

    chat_id = callback.message.chat.id if isinstance(callback.message, Message) else None
    if chat_id is None:
        await callback.answer()
        return

    # Reset FSM bubble — fresh anchor for the partner-chart prompt.
    await state.clear()
    await state.update_data(
        mode="partner",
        owner_chart_id=owner_chart_id,
        pending_question=pending_question,
    )
    await state.set_state(BirthDataForm.waiting_date)
    await _step(bot=bot, chat_id=chat_id, state=state, text=PARTNER_DATE_PROMPT)
    await callback.answer()


@birth_data_router.message(BirthDataForm.waiting_date, F.text)
async def handle_date(message: Message, state: FSMContext, bot: Bot) -> None:
    text = message.text or ""
    await _swallow_user_message(message)
    parsed = _parse_birth_date(text)
    if parsed is None:
        await _step(
            bot=bot, chat_id=message.chat.id, state=state, text=DATE_INVALID.format(text=text)
        )
        return

    today = datetime.now().date()
    if parsed > today:
        await _step(
            bot=bot, chat_id=message.chat.id, state=state, text=DATE_FUTURE.format(text=text)
        )
        return
    if parsed.year < MIN_YEAR:
        await _step(
            bot=bot, chat_id=message.chat.id, state=state, text=DATE_TOO_OLD.format(text=text)
        )
        return

    await state.update_data(birth_date=parsed.isoformat())
    logger.info(
        "birth_data.date_accepted",
        telegram_id=message.from_user.id if message.from_user else None,
        date=parsed.isoformat(),
    )
    if await _is_edit_mode(state):
        await _back_to_confirm(bot, message.chat.id, state)
        return
    await state.set_state(BirthDataForm.waiting_time)
    await _step(
        bot=bot,
        chat_id=message.chat.id,
        state=state,
        text=DATE_ACCEPTED.format(formatted=parsed.strftime("%d.%m.%Y")),
        kb=time_step_kb(),
    )


@birth_data_router.message(BirthDataForm.waiting_time, F.text)
async def handle_time(message: Message, state: FSMContext, bot: Bot) -> None:
    text = message.text or ""
    await _swallow_user_message(message)
    parsed = _parse_birth_time(text)
    if parsed is None:
        await _step(
            bot=bot,
            chat_id=message.chat.id,
            state=state,
            text=TIME_INVALID.format(text=text),
            kb=time_step_kb(),
        )
        return

    await state.update_data(birth_time=parsed.isoformat(), has_birth_time=True)
    logger.info(
        "birth_data.time_accepted",
        telegram_id=message.from_user.id if message.from_user else None,
        time=parsed.isoformat(),
    )
    if await _is_edit_mode(state):
        await _back_to_confirm(bot, message.chat.id, state)
        return
    await state.set_state(BirthDataForm.waiting_city)
    await _step(
        bot=bot,
        chat_id=message.chat.id,
        state=state,
        text=TIME_ACCEPTED.format(formatted=parsed.strftime("%H:%M")),
        kb=back_to_time_kb(),
    )


@birth_data_router.callback_query(BirthDataForm.waiting_time, F.data == "time:skip")
async def handle_time_skip(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await state.update_data(birth_time=None, has_birth_time=False)
    logger.info(
        "birth_data.time_skipped",
        telegram_id=callback.from_user.id if callback.from_user else None,
    )
    chat_id = callback.message.chat.id if isinstance(callback.message, Message) else None
    if chat_id is None:
        await callback.answer()
        return
    if await _is_edit_mode(state):
        await _back_to_confirm(bot, chat_id, state)
        await callback.answer()
        return
    await state.set_state(BirthDataForm.waiting_city)
    await _step(bot=bot, chat_id=chat_id, state=state, text=TIME_SKIPPED, kb=back_to_time_kb())
    await callback.answer()


@birth_data_router.message(BirthDataForm.waiting_city, F.text)
async def handle_city(message: Message, state: FSMContext, bot: Bot) -> None:
    query = (message.text or "").strip()
    await _swallow_user_message(message)
    candidates = await search_cities(query, limit=3)
    if not candidates:
        await _step(
            bot=bot,
            chat_id=message.chat.id,
            state=state,
            text=CITY_NOT_FOUND.format(query=query),
            kb=back_to_time_kb(),
        )
        return

    await state.update_data(city_candidates=[c.to_dict() for c in candidates])
    options = [(c.short_label(), f"city:{i}") for i, c in enumerate(candidates)]
    await _step(
        bot=bot,
        chat_id=message.chat.id,
        state=state,
        text=CITY_CHOICES,
        kb=city_choice_kb(options),
    )


@birth_data_router.callback_query(BirthDataForm.waiting_city, F.data == "city:retry")
async def handle_city_retry(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await state.update_data(city_candidates=None)
    if isinstance(callback.message, Message):
        await _step(bot=bot, chat_id=callback.message.chat.id, state=state, text=CITY_PROMPT)
    await callback.answer()


@birth_data_router.callback_query(BirthDataForm.waiting_city, F.data.startswith("city:"))
async def handle_city_choice(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
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
        await callback.answer("Этот вариант устарел, введите город заново.", show_alert=True)
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
    chat_id = callback.message.chat.id if isinstance(callback.message, Message) else None
    if chat_id is None:
        await callback.answer()
        return
    if await _is_edit_mode(state):
        await _back_to_confirm(bot, chat_id, state)
        await callback.answer()
        return
    await state.set_state(BirthDataForm.waiting_gender)
    await _step(
        bot=bot,
        chat_id=chat_id,
        state=state,
        text=CITY_ACCEPTED.format(name=chosen["display_name"]),
        kb=gender_kb(),
    )
    await callback.answer()


@birth_data_router.callback_query(BirthDataForm.waiting_gender, F.data.startswith("gender:"))
async def handle_gender(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
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
        await _back_to_confirm(bot, callback.message.chat.id, state)
    await callback.answer()


async def _is_edit_mode(state: FSMContext) -> bool:
    """gender is the last field set in the linear flow — its presence in
    FSM data uniquely identifies "user came from the edit menu, every other
    field is already valid". Used by date/time/city handlers to decide
    whether to advance to the next step or jump back to the summary."""
    data = await state.get_data()
    return bool(data.get("gender")) and bool(data.get("city_name"))


async def _back_to_confirm(bot: Bot, chat_id: int, state: FSMContext) -> None:
    await state.set_state(BirthDataForm.confirm)
    data = await state.get_data()
    await _step(
        bot=bot,
        chat_id=chat_id,
        state=state,
        text=_format_summary(data),
        kb=confirm_kb(),
    )


@birth_data_router.callback_query(BirthDataForm.confirm, F.data == "edit:menu")
async def handle_edit_menu(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    if isinstance(callback.message, Message):
        await _step(
            bot=bot,
            chat_id=callback.message.chat.id,
            state=state,
            text=EDIT_MENU_PROMPT,
            kb=edit_menu_kb(),
        )
    await callback.answer()


@birth_data_router.callback_query(BirthDataForm.confirm, F.data == "edit:cancel")
async def handle_edit_cancel(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    if isinstance(callback.message, Message):
        await _back_to_confirm(bot, callback.message.chat.id, state)
    await callback.answer()


@birth_data_router.callback_query(BirthDataForm.confirm, F.data == "edit:date")
async def handle_edit_date(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await state.set_state(BirthDataForm.waiting_date)
    if isinstance(callback.message, Message):
        await _step(
            bot=bot, chat_id=callback.message.chat.id, state=state, text=EDIT_PROMPTS["date"]
        )
    await callback.answer()


@birth_data_router.callback_query(BirthDataForm.confirm, F.data == "edit:time")
async def handle_edit_time(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await state.set_state(BirthDataForm.waiting_time)
    if isinstance(callback.message, Message):
        await _step(
            bot=bot,
            chat_id=callback.message.chat.id,
            state=state,
            text=EDIT_PROMPTS["time"],
            kb=time_step_kb(),
        )
    await callback.answer()


@birth_data_router.callback_query(BirthDataForm.confirm, F.data == "edit:city")
async def handle_edit_city(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await state.set_state(BirthDataForm.waiting_city)
    if isinstance(callback.message, Message):
        await _step(
            bot=bot, chat_id=callback.message.chat.id, state=state, text=EDIT_PROMPTS["city"]
        )
    await callback.answer()


@birth_data_router.callback_query(BirthDataForm.confirm, F.data == "edit:gender")
async def handle_edit_gender(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    await state.set_state(BirthDataForm.waiting_gender)
    if isinstance(callback.message, Message):
        await _step(
            bot=bot,
            chat_id=callback.message.chat.id,
            state=state,
            text=EDIT_PROMPTS["gender"],
            kb=gender_kb(),
        )
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
async def handle_fsm_restart(callback: CallbackQuery, state: FSMContext, bot: Bot) -> None:
    chat_id = callback.message.chat.id if isinstance(callback.message, Message) else None
    if chat_id is None:
        await callback.answer()
        return
    # Preserve fsm_msg_id across the clear so _step can keep editing the same
    # bot bubble. State clear wipes everything else.
    data = await state.get_data()
    msg_id = data.get("fsm_msg_id")
    await state.clear()
    if isinstance(msg_id, int):
        await state.update_data(fsm_msg_id=msg_id)
    await state.set_state(BirthDataForm.waiting_date)
    await _step(bot=bot, chat_id=chat_id, state=state, text=RESTART_PROMPT)
    await callback.answer()


@birth_data_router.callback_query(BirthDataForm.confirm, F.data == "confirm:calc")
async def handle_confirm_calc(
    callback: CallbackQuery,
    state: FSMContext,
    user: User,
    session: AsyncSession,
    bot: Bot,
) -> None:
    await _consume_buttons(callback)  # last edit before we leave the FSM bubble
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
    chart_output = result["chart_output"]
    has_birth_time = bool(result["has_birth_time"])
    city_label = str(result["city_label"])
    assert isinstance(day_master, str)
    assert isinstance(date_str, str)
    assert isinstance(chart_output, ChartOutput)

    mode = result.get("mode")  # "partner" or None
    if isinstance(callback.message, Message):
        png = await render_chart_png(
            RenderRequest(
                chart=chart_output,
                title=date_str,
                subtitle=city_label,
                has_birth_time=has_birth_time,
            )
        )
        caption = (
            f"Карта партнёра рассчитана. Господин дня: <b>{day_master}</b>."
            if mode == "partner"
            else f"Карта рассчитана. Господин дня: <b>{day_master}</b>."
        )
        await callback.message.answer_photo(
            BufferedInputFile(png, "chart.png"),
            caption=caption,
        )

        if mode == "partner":
            # Skip the naming step for partner charts (we already saved
            # name="Партнёр"). Clear FSM and show a confirmation; Phase 6
            # will hook this into auto-resume of the pending question.
            await state.clear()
            await callback.message.answer(PARTNER_SAVED_MSG)
        else:
            await state.set_state(BirthDataForm.naming)
            await state.update_data(chart_id=str(chart_id), fsm_msg_id=None)
            # Naming prompt is a fresh bubble (photo above can't be text-edited);
            # _step starts a new anchor here.
            await _step(
                bot=bot,
                chat_id=callback.message.chat.id,
                state=state,
                text=NAME_PROMPT.format(day_master=day_master, date=date_str),
                kb=name_skip_kb(),
            )
    await callback.answer()


@birth_data_router.message(BirthDataForm.naming, F.text)
async def handle_naming_input(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    bot: Bot,
) -> None:
    name = (message.text or "").strip()
    await _swallow_user_message(message)
    if not name:
        return
    data = await state.get_data()
    raw_id = data.get("chart_id")
    if not isinstance(raw_id, str):
        await state.clear()
        return
    import uuid as _uuid

    await _chart_repo.update_name(session, _uuid.UUID(raw_id), name)
    await _step(bot=bot, chat_id=message.chat.id, state=state, text=NAME_SAVED.format(name=name))
    await state.clear()
    await send_main_menu(message, user, session, state=state, greeting=GREETING_AFTER_NAMING)


@birth_data_router.callback_query(BirthDataForm.naming, F.data == "name:skip")
async def handle_naming_skip(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    bot: Bot,
) -> None:
    if isinstance(callback.message, Message):
        await _step(bot=bot, chat_id=callback.message.chat.id, state=state, text=NAME_SKIPPED)
        await state.clear()
        await send_main_menu(
            callback.message, user, session, state=state, greeting=GREETING_AFTER_NAMING
        )
    await callback.answer()


async def _calculate_and_persist(
    data: dict[str, str | float | bool | None],
    *,
    user: User,
    session: AsyncSession,
) -> dict[str, object]:
    """Run the calculator, save Chart, and (if ``mode=='partner'``)
    link it to ``owner_chart_id`` via ChartRepository.set_partner."""
    raw_date = data["birth_date"]
    raw_time = data.get("birth_time")
    has_time = bool(data.get("has_birth_time"))
    tz_iana = data["timezone"]
    lat = data["latitude"]
    lon = data["longitude"]
    gender = data["gender"]
    city_name = data["city_name"]
    mode = data.get("mode")  # None (default) or "partner"
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
        name="Партнёр" if mode == "partner" else None,
        has_birth_time=has_time,
    )

    # Link partner chart to its owner. ``owner_chart_id`` was stashed in
    # FSM data when the user pressed «Add partner chart» in consultation.
    if mode == "partner":
        import uuid as _uuid

        owner_raw = data.get("owner_chart_id")
        if isinstance(owner_raw, str):
            try:
                owner_uuid = _uuid.UUID(owner_raw)
            except ValueError:
                logger.warning("partner_link.invalid_owner_id", raw=owner_raw)
            else:
                await _chart_repo.set_partner(
                    session,
                    owner_chart_id=owner_uuid,
                    partner_chart_id=chart.id,
                )
                logger.info(
                    "partner_link.set",
                    owner_chart_id=str(owner_uuid),
                    partner_chart_id=str(chart.id),
                )

    short_city = city_name.split(",")[0].strip() if "," in city_name else city_name
    time_part = resolved.naive_local.strftime("%H:%M") if has_time else "без часа"
    return {
        "chart_id": chart.id,
        "date_str": resolved.naive_local.strftime("%d.%m.%Y"),
        "city_label": f"{short_city} · {time_part}",
        "day_master": chart_data["day_master"],
        "has_birth_time": has_time,
        "chart_output": chart_output,
        "mode": mode,
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
