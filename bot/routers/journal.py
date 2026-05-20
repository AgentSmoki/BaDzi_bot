"""Wave 4 — reflection journal handlers.

UI flow:
    journal:show:<chart_id>            settings/menu screen
    journal:enable_pick:<chart_id>     show hour picker
    journal:enable_set:<chart_id>:<h>  save settings + activate scheduler
    journal:disable:<chart_id>         flip enabled=false
    journal:write:<chart_id>           FSM → wait text/voice
    journal:export:<chart_id>          collect all entries → .md document

Voice flow (Wave 4c):
    journal:write — F.voice → bot.download → TeleTranscribe HTTP →
      show transcript with «✅ Добавить» / «✏ Изменить» buttons
    journal:confirm_voice → save JournalEntry(source=voice)
    journal:correct_voice → FSM correction text → LLM edit-pass → confirm again
"""

from __future__ import annotations

import contextlib
import io
import uuid
from datetime import date, datetime

import structlog
from aiogram import Bot, F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    BufferedInputFile,
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.teletranscribe import TeleTranscribeError, transcribe_voice
from bot.states import JournalState
from db.models import Chart, JournalEntry, JournalEntrySource, User
from db.repositories.chart_repo import ChartRepository
from db.repositories.journal_repo import (
    ChartJournalSettingsRepository,
    JournalEntryRepository,
)

logger = structlog.get_logger(__name__)

journal_router = Router(name="journal")
_chart_repo = ChartRepository()
_settings_repo = ChartJournalSettingsRepository()
_entry_repo = JournalEntryRepository()

_NOT_YOUR_CHART = "Эта карта не ваша или удалена."


def _parse_uuid(parts: list[str], index: int) -> uuid.UUID | None:
    try:
        return uuid.UUID(parts[index])
    except (ValueError, IndexError):
        return None


def _hour_local_to_utc(hour_local: int, tz_offset_hours: float) -> int:
    return int(hour_local - tz_offset_hours) % 24


def _journal_menu_kb(
    chart_id: uuid.UUID, *, enabled: bool, hour_local: int
) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    if enabled:
        rows.append(
            [
                InlineKeyboardButton(
                    text="📝 Записать сегодня",
                    callback_data=f"journal:write:{chart_id}",
                )
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"🕐 Изменить время (сейчас {hour_local:02d}:00)",
                    callback_data=f"journal:enable_pick:{chart_id}",
                )
            ]
        )
        rows.append(
            [
                InlineKeyboardButton(
                    text="⏸ Выключить дневник",
                    callback_data=f"journal:disable:{chart_id}",
                )
            ]
        )
    else:
        rows.append(
            [
                InlineKeyboardButton(
                    text="▶ Включить дневник",
                    callback_data=f"journal:enable_pick:{chart_id}",
                )
            ]
        )
    rows.append(
        [
            InlineKeyboardButton(
                text="📤 Скачать дневник (.md)",
                callback_data=f"journal:export:{chart_id}",
            )
        ]
    )
    rows.append(
        [InlineKeyboardButton(text="↩ Назад к карте", callback_data=f"chart:open:{chart_id}")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _hour_picker_kb(chart_id: uuid.UUID) -> InlineKeyboardMarkup:
    builder_rows: list[list[InlineKeyboardButton]] = []
    for hour in (7, 12, 19, 21, 22):
        builder_rows.append(
            [
                InlineKeyboardButton(
                    text=f"{hour:02d}:00 моего времени",
                    callback_data=f"journal:enable_set:{chart_id}:{hour}",
                )
            ]
        )
    builder_rows.append(
        [InlineKeyboardButton(text="↩ Назад", callback_data=f"journal:show:{chart_id}")]
    )
    return InlineKeyboardMarkup(inline_keyboard=builder_rows)


def _voice_confirm_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Добавить запись", callback_data="journal:confirm_voice"
                )
            ],
            [
                InlineKeyboardButton(
                    text="✏ Внести корректировки", callback_data="journal:correct_voice"
                )
            ],
        ]
    )


async def _load_chart_for_user(
    session: AsyncSession, *, chart_id: uuid.UUID, user_id: uuid.UUID
) -> Chart | None:
    chart = await _chart_repo.get_by_id(session, chart_id)
    if chart is None or chart.user_id != user_id:
        return None
    return chart


# ── journal:show — main screen ───────────────────────────────────────────


@journal_router.callback_query(F.data.startswith("journal:show:"))
async def handle_journal_show(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    if not callback.data:
        await callback.answer()
        return
    chart_id = _parse_uuid(callback.data.split(":"), 2)
    if chart_id is None:
        await callback.answer("Неверная карта", show_alert=True)
        return
    chart = await _load_chart_for_user(session, chart_id=chart_id, user_id=user.id)
    if chart is None:
        await callback.answer(_NOT_YOUR_CHART, show_alert=True)
        return

    settings = await _settings_repo.get_or_create(session, chart_id=chart_id)
    await session.commit()
    status = (
        (
            f"<b>📔 Дневник</b>\n\nВключён, напоминание в "
            f"{settings.reminder_hour_local:02d}:00 вашего времени.\n\n"
            "Каждый вечер я буду спрашивать — как прошёл день. Можно отвечать "
            "текстом или голосовым — расшифрую и сохраню в дневник этой карты."
        )
        if settings.enabled
        else (
            "<b>📔 Дневник</b>\n\nСейчас выключен.\n\n"
            "Включите — каждый вечер пришлю напоминание записать рефлексию по карте. "
            "Можно отвечать текстом или голосовым (я расшифровываю)."
        )
    )
    if isinstance(callback.message, Message):
        await callback.message.answer(
            status,
            reply_markup=_journal_menu_kb(
                chart_id, enabled=settings.enabled, hour_local=settings.reminder_hour_local
            ),
        )
    await callback.answer()


# ── Enable / hour pick / disable ─────────────────────────────────────────


@journal_router.callback_query(F.data.startswith("journal:enable_pick:"))
async def handle_enable_pick(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    if not callback.data:
        await callback.answer()
        return
    chart_id = _parse_uuid(callback.data.split(":"), 2)
    if chart_id is None:
        await callback.answer("Неверная карта", show_alert=True)
        return
    chart = await _load_chart_for_user(session, chart_id=chart_id, user_id=user.id)
    if chart is None:
        await callback.answer(_NOT_YOUR_CHART, show_alert=True)
        return

    if isinstance(callback.message, Message):
        await callback.message.answer(
            "В какое время вашего дня присылать напоминание?",
            reply_markup=_hour_picker_kb(chart_id),
        )
    await callback.answer()


@journal_router.callback_query(F.data.startswith("journal:enable_set:"))
async def handle_enable_set(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    if not callback.data:
        await callback.answer()
        return
    parts = callback.data.split(":")
    chart_id = _parse_uuid(parts, 2)
    try:
        hour_local = int(parts[3])
    except (ValueError, IndexError):
        await callback.answer("Неверный час", show_alert=True)
        return
    if chart_id is None or not (0 <= hour_local <= 23):
        await callback.answer("Неверный выбор", show_alert=True)
        return
    chart = await _load_chart_for_user(session, chart_id=chart_id, user_id=user.id)
    if chart is None:
        await callback.answer(_NOT_YOUR_CHART, show_alert=True)
        return

    hour_utc = _hour_local_to_utc(hour_local, chart.tz_offset)
    await _settings_repo.update_schedule(
        session,
        chart_id=chart_id,
        enabled=True,
        reminder_hour_local=hour_local,
        reminder_hour_utc=hour_utc,
    )
    await session.commit()
    logger.info(
        "journal.enabled",
        chart_id=str(chart_id),
        user_id=str(user.id),
        hour_local=hour_local,
        hour_utc=hour_utc,
    )

    if isinstance(callback.message, Message):
        await callback.message.answer(
            f"Дневник включён. Напоминание в {hour_local:02d}:00 вашего времени.",
            reply_markup=_journal_menu_kb(chart_id, enabled=True, hour_local=hour_local),
        )
    await callback.answer()


@journal_router.callback_query(F.data.startswith("journal:disable:"))
async def handle_disable(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    if not callback.data:
        await callback.answer()
        return
    chart_id = _parse_uuid(callback.data.split(":"), 2)
    if chart_id is None:
        await callback.answer("Неверная карта", show_alert=True)
        return
    chart = await _load_chart_for_user(session, chart_id=chart_id, user_id=user.id)
    if chart is None:
        await callback.answer(_NOT_YOUR_CHART, show_alert=True)
        return

    settings = await _settings_repo.get_or_create(session, chart_id=chart_id)
    await _settings_repo.update_schedule(
        session,
        chart_id=chart_id,
        enabled=False,
        reminder_hour_local=settings.reminder_hour_local,
        reminder_hour_utc=settings.reminder_hour_utc,
    )
    await session.commit()

    if isinstance(callback.message, Message):
        await callback.message.answer(
            "Дневник выключен. Записи сохранены, можно скачать.",
            reply_markup=_journal_menu_kb(
                chart_id, enabled=False, hour_local=settings.reminder_hour_local
            ),
        )
    await callback.answer()


# ── Write a reflection ───────────────────────────────────────────────────


@journal_router.callback_query(F.data.startswith("journal:write:"))
async def handle_write_start(
    callback: CallbackQuery, session: AsyncSession, user: User, state: FSMContext
) -> None:
    if not callback.data:
        await callback.answer()
        return
    chart_id = _parse_uuid(callback.data.split(":"), 2)
    if chart_id is None:
        await callback.answer("Неверная карта", show_alert=True)
        return
    chart = await _load_chart_for_user(session, chart_id=chart_id, user_id=user.id)
    if chart is None:
        await callback.answer(_NOT_YOUR_CHART, show_alert=True)
        return

    await state.set_state(JournalState.waiting_reflection)
    await state.update_data(journal_chart_id=str(chart_id))
    if isinstance(callback.message, Message):
        await callback.message.answer(
            "Как прошёл этот день? Опишите своими словами текстом или "
            "запишите голосовое — я расшифрую и сохраню.",
        )
    await callback.answer()


@journal_router.message(JournalState.waiting_reflection, F.text)
async def handle_text_reflection(
    message: Message, session: AsyncSession, state: FSMContext, user: User
) -> None:
    text = (message.text or "").strip()
    if not text:
        return
    data = await state.get_data()
    chart_id_raw = data.get("journal_chart_id")
    if not isinstance(chart_id_raw, str):
        await state.clear()
        return
    chart_id = uuid.UUID(chart_id_raw)
    chart = await _load_chart_for_user(session, chart_id=chart_id, user_id=user.id)
    if chart is None:
        await state.clear()
        await message.answer(_NOT_YOUR_CHART)
        return

    summary = _build_energies_summary(chart, target_day=date.today())
    await _entry_repo.upsert(
        session,
        chart_id=chart_id,
        entry_date=date.today(),
        energies_summary=summary,
        user_reflection=text,
        source=JournalEntrySource.text,
    )
    await session.commit()
    await state.clear()

    await message.answer(
        "Записала в дневник. Если захотите перезаписать — просто откройте "
        "«📔 Дневник» и нажмите «Записать сегодня» снова.",
        reply_markup=_journal_menu_kb(chart_id, enabled=True, hour_local=21),
    )


@journal_router.message(JournalState.waiting_reflection, F.voice)
async def handle_voice_reflection(
    message: Message, session: AsyncSession, state: FSMContext, user: User, bot: Bot
) -> None:
    data = await state.get_data()
    chart_id_raw = data.get("journal_chart_id")
    if not isinstance(chart_id_raw, str):
        await state.clear()
        return
    chart_id = uuid.UUID(chart_id_raw)
    chart = await _load_chart_for_user(session, chart_id=chart_id, user_id=user.id)
    if chart is None or message.voice is None:
        await state.clear()
        return

    await message.answer("Расшифровываю голосовое — секунду…")

    # Download voice from Telegram.
    try:
        buf = io.BytesIO()
        await bot.download(message.voice.file_id, destination=buf)
        audio_bytes = buf.getvalue()
    except Exception as exc:
        logger.warning("journal.voice_download_failed", error=str(exc))
        await message.answer(
            "Не получилось скачать голосовое из Telegram. Попробуйте текстом или запишите ещё раз."
        )
        return

    try:
        transcript = await transcribe_voice(audio_bytes=audio_bytes)
    except TeleTranscribeError as exc:
        logger.warning("journal.transcribe_failed", error=str(exc))
        await message.answer(
            "Сервис расшифровки сейчас не отвечает. Напишите текстом, пожалуйста — сохраню сразу."
        )
        return

    await state.set_state(JournalState.confirming_voice_transcript)
    await state.update_data(
        journal_chart_id=chart_id_raw,
        journal_transcript=transcript,
    )
    await message.answer(
        "<b>Расшифровка</b>\n\n" + transcript + "\n\n"
        "Если всё ок — нажмите «Добавить запись». Если хотите исправить — "
        "нажмите «Внести корректировки» и опишите что поправить.",
        reply_markup=_voice_confirm_kb(),
    )


@journal_router.callback_query(
    JournalState.confirming_voice_transcript, F.data == "journal:confirm_voice"
)
async def handle_confirm_voice(
    callback: CallbackQuery,
    session: AsyncSession,
    state: FSMContext,
    user: User,
) -> None:
    data = await state.get_data()
    chart_id_raw = data.get("journal_chart_id")
    transcript = data.get("journal_transcript")
    if not isinstance(chart_id_raw, str) or not isinstance(transcript, str):
        await state.clear()
        await callback.answer()
        return
    chart_id = uuid.UUID(chart_id_raw)
    chart = await _load_chart_for_user(session, chart_id=chart_id, user_id=user.id)
    if chart is None:
        await state.clear()
        await callback.answer(_NOT_YOUR_CHART, show_alert=True)
        return

    summary = _build_energies_summary(chart, target_day=date.today())
    await _entry_repo.upsert(
        session,
        chart_id=chart_id,
        entry_date=date.today(),
        energies_summary=summary,
        user_reflection=transcript,
        source=JournalEntrySource.voice,
    )
    await session.commit()
    await state.clear()

    if isinstance(callback.message, Message):
        with contextlib.suppress(Exception):
            await callback.message.edit_text("Запись добавлена в дневник.")
    await callback.answer()


@journal_router.callback_query(
    JournalState.confirming_voice_transcript, F.data == "journal:correct_voice"
)
async def handle_correct_voice(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(JournalState.waiting_correction_instruction)
    if isinstance(callback.message, Message):
        await callback.message.answer(
            "Что исправить? Опишите своими словами — например, «исправь имя», "
            "«удали последнюю фразу», «добавь что я был в парке»."
        )
    await callback.answer()


@journal_router.message(JournalState.waiting_correction_instruction, F.text)
async def handle_correction_instruction(
    message: Message, session: AsyncSession, state: FSMContext, user: User
) -> None:
    instruction = (message.text or "").strip()
    if not instruction:
        return
    data = await state.get_data()
    chart_id_raw = data.get("journal_chart_id")
    original = data.get("journal_transcript")
    if not isinstance(chart_id_raw, str) or not isinstance(original, str):
        await state.clear()
        return

    edited = await _apply_correction(original=original, instruction=instruction)
    await state.set_state(JournalState.confirming_voice_transcript)
    await state.update_data(journal_transcript=edited)
    await message.answer(
        "<b>Исправленная версия</b>\n\n" + edited + "\n\n"
        "Так лучше? Если да — «Добавить запись», если ещё что-то — «Внести корректировки».",
        reply_markup=_voice_confirm_kb(),
    )


async def _apply_correction(*, original: str, instruction: str) -> str:
    """Second LLM pass — applies the user's correction to the transcript.
    Uses the fast YC model (same one skill-router uses) to stay cheap."""
    from ai.orchestrator import ChatMessage, OrchestratorError, chat
    from bot.config import get_settings

    settings = get_settings()
    system = (
        "Ты редактор записи дневника. Тебе дают исходный текст и "
        "одно короткое указание пользователя — что исправить. Внеси "
        "точечную правку и верни ТОЛЬКО исправленный текст, без преамбулы, "
        "без объяснений. Не добавляй ничего от себя."
    )
    user_payload = (
        f"Исходный текст:\n{original}\n\n"
        f"Указание пользователя:\n{instruction}\n\n"
        "Верни исправленный текст:"
    )
    try:
        result = await chat(
            provider="yc",
            model=settings.yc_fast_model,
            messages=[
                ChatMessage(role="system", content=system),
                ChatMessage(role="user", content=user_payload),
            ],
            temperature=0.2,
            max_tokens=settings.yc_fast_max_tokens,
        )
    except OrchestratorError as exc:
        logger.warning("journal.correction_llm_failed", error=str(exc))
        return original  # fall back: keep original on LLM failure
    return result.text.strip() or original


# ── Export ───────────────────────────────────────────────────────────────


@journal_router.callback_query(F.data.startswith("journal:export:"))
async def handle_export(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    if not callback.data:
        await callback.answer()
        return
    chart_id = _parse_uuid(callback.data.split(":"), 2)
    if chart_id is None:
        await callback.answer("Неверная карта", show_alert=True)
        return
    chart = await _load_chart_for_user(session, chart_id=chart_id, user_id=user.id)
    if chart is None:
        await callback.answer(_NOT_YOUR_CHART, show_alert=True)
        return

    entries = await _entry_repo.list_by_chart(session, chart_id)
    if not entries:
        await callback.answer(
            "Дневник пуст — записать что-то и попробовать снова.", show_alert=True
        )
        return

    md = _render_export_md(chart_label=chart.name or "Без имени", entries=entries)
    filename = f"journal_{(chart.name or 'chart').lower().replace(' ', '_')}.md"
    if isinstance(callback.message, Message):
        await callback.message.answer_document(
            BufferedInputFile(md.encode("utf-8"), filename),
            caption=f"Дневник по карте «{chart.name or 'Без имени'}», {len(entries)} записей.",
        )
    await callback.answer()


def _render_export_md(*, chart_label: str, entries: list[JournalEntry]) -> str:
    lines = [
        f"# Дневник рефлексии — {chart_label}",
        "",
        f"Экспорт от {datetime.now().strftime('%d.%m.%Y %H:%M')}. Всего записей: {len(entries)}.",
        "",
    ]
    for entry in entries:
        lines.append(f"## {entry.entry_date.strftime('%d.%m.%Y')}")
        lines.append("")
        lines.append("**Энергии дня:**")
        lines.append("")
        lines.append(entry.energies_summary)
        lines.append("")
        if entry.user_reflection:
            label = "Голосовая рефлексия" if entry.source.value == "voice" else "Рефлексия"
            lines.append(f"**{label}:**")
            lines.append("")
            lines.append(entry.user_reflection)
            lines.append("")
        elif entry.source.value == "auto":
            lines.append("_(автоматическая запись — рефлексии не было)_")
            lines.append("")
    return "\n".join(lines)


def _build_energies_summary(chart: Chart, target_day: date) -> str:
    """Compact «energies of the day» string written into JournalEntry.

    Uses the calculator to compute the day's pillars at noon and
    formats Year/Month/Day pillars together with the natal Day Master.
    """
    from calculator import calculate_chart
    from calculator.models import ChartInput

    target_chart = calculate_chart(
        ChartInput(
            birth_datetime=datetime.combine(target_day, datetime.min.time().replace(hour=12)),
            latitude=0.0,
            longitude=0.0,
            tz_offset=0.0,
            gender="male",
        )
    )
    day_pillars = " · ".join(f"{p.stem}{p.branch}" for p in target_chart.pillars[:3])
    chart_data = chart.chart_data or {}
    natal_dm = chart_data.get("day_master", "?")
    return (
        f"Дата: {target_day.strftime('%d.%m.%Y')}\n"
        f"Натальный Дневной Мастер: {natal_dm}\n"
        f"Столпы дня (Y·M·D): {day_pillars}"
    )
