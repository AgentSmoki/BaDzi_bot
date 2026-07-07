"""Wave 5 — master-meeting upload + list + delete handlers.

UI (hotfix 2026-05-20 — callbacks укорочены под Telegram-лимит 64 bytes):
    meeting:show:<chart_id>     entry; stashes chart_id in FSM
    mm:add                       explainer → FSM waiting_url
    mm:v:<meeting_id>            show summary inline
    mm:d:<meeting_id>            confirm dialog
    mm:dc:<meeting_id>           repo.delete + back to list

chart_id живёт в FSM data под ключом ``_FSM_MEETING_CHART`` — handlers
читают его оттуда. Старая схема ``meeting:view:{meeting_id}:{chart_id}``
выходила за 64 байта (36+36+13 = 85) и Telegram бросал
BUTTON_DATA_INVALID.

Background work happens in `tasks/master_meeting.py` via TaskIQ. The
handler only enqueues + writes the «queued» row; the user gets a
Telegram message when the worker finishes.
"""

from __future__ import annotations

import contextlib
import uuid
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

from bot.services.teletranscribe import detect_source_type
from bot.states import MasterMeetingState
from db.models import (
    Chart,
    MasterMeeting,
    MasterMeetingSource,
    MasterMeetingStatus,
    User,
)
from db.repositories.chart_repo import ChartRepository
from db.repositories.master_meeting_repo import MasterMeetingRepository
from tasks.master_meeting import transcribe_master_meeting

logger = structlog.get_logger(__name__)

master_meeting_router = Router(name="master_meeting")
_chart_repo = ChartRepository()
_meeting_repo = MasterMeetingRepository()

# Wave 5 hotfix: same as forecast.py — stash chart_id in FSM for short
# callback_data. Key separate from forecast's to avoid cross-flow leaks.
_FSM_MEETING_CHART = "meeting_chart_id"

_NOT_YOUR_CHART = "Эта карта не ваша или удалена."
_SESSION_LOST = (
    "Сессия истекла — откройте карту заново и нажмите «🎓 Загрузить Встречу с Мастером»."
)

_EXPLAINER = (
    "<b>🎓 Загрузить Встречу с Мастером</b>\n\n"
    "Когда вы проходите живую сессию с мастером — пришлите мне ссылку "
    "на запись (Google Drive, Yandex Disk, Cloud Mail, YouTube, Zoom). "
    "Я расшифрую запись, выжму из неё ключевые мысли и буду учитывать "
    "глубинные аспекты вашей карты, когда вы задаёте вопросы.\n\n"
    "Чтобы добавить встречу — нажмите «Добавить ссылку» и пришлите URL "
    "одним сообщением."
)
_URL_PROMPT = (
    "Пришлите мне ссылку на запись встречи. Я приму её и расшифрую в "
    "фоне — на это уйдёт пара минут для коротких записей и до получаса "
    "для длинных. Напишу когда будет готово."
)
_QUEUED_MSG = (
    "Запись принята в работу. Я расшифрую её в фоне и пришлю уведомление, "
    "когда выжимка будет готова. Можете в это время продолжать общение."
)
_INVALID_URL = "Это не похоже на URL. Пришлите полную ссылку, начинающуюся с http:// или https://"


def _parse_uuid(parts: list[str], index: int) -> uuid.UUID | None:
    try:
        return uuid.UUID(parts[index])
    except (ValueError, IndexError):
        return None


def _is_valid_url(text: str) -> bool:
    return text.startswith(("http://", "https://")) and " " not in text.strip()


async def _load_chart_for_user(
    session: AsyncSession, *, chart_id: uuid.UUID, user_id: uuid.UUID
) -> Chart | None:
    chart = await _chart_repo.get_by_id(session, chart_id)
    if chart is None or chart.user_id != user_id:
        return None
    return chart


async def _stash_chart_id(state: FSMContext, chart_id: uuid.UUID) -> None:
    payload: dict[str, Any] = {_FSM_MEETING_CHART: str(chart_id)}
    await state.update_data(**payload)


async def _resolve_chart_from_state(
    state: FSMContext, session: AsyncSession, user_id: uuid.UUID
) -> Chart | None:
    data = await state.get_data()
    raw = data.get(_FSM_MEETING_CHART)
    if not isinstance(raw, str):
        return None
    try:
        chart_id = uuid.UUID(raw)
    except ValueError:
        return None
    return await _load_chart_for_user(session, chart_id=chart_id, user_id=user_id)


def _status_label(status: MasterMeetingStatus) -> str:
    return {
        MasterMeetingStatus.queued: "⏳ в очереди",
        MasterMeetingStatus.transcribing: "🔄 расшифровывается",
        MasterMeetingStatus.ready: "✅ готова",
        MasterMeetingStatus.failed: "⚠ ошибка",
    }[status]


def _meeting_short_label(meeting: MasterMeeting) -> str:
    when = meeting.uploaded_at.strftime("%d.%m.%Y")
    src = meeting.source_type.value
    return f"{when} · {src} · {_status_label(meeting.status)}"


def _menu_kb(chart_id: uuid.UUID, meetings: list[MasterMeeting]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = [
        [InlineKeyboardButton(text="➕ Добавить ссылку", callback_data="mm:add")]
    ]
    for m in meetings[:8]:
        rows.append(
            [
                InlineKeyboardButton(
                    text=_meeting_short_label(m),
                    callback_data=f"mm:v:{m.id}",
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton(text="↩ Назад к карте", callback_data=f"chart:open:{chart_id}")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── meeting:show (sets FSM) ──────────────────────────────────────────────


@master_meeting_router.callback_query(F.data.startswith("meeting:show:"))
async def handle_show(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    state: FSMContext,
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

    await _stash_chart_id(state, chart_id)
    meetings = await _meeting_repo.list_by_chart(session, chart_id)
    if isinstance(callback.message, Message):
        await callback.message.answer(_EXPLAINER, reply_markup=_menu_kb(chart_id, meetings))
    await callback.answer()


# ── mm:add → FSM ─────────────────────────────────────────────────────────


@master_meeting_router.callback_query(F.data == "mm:add")
async def handle_add_start(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    state: FSMContext,
) -> None:
    chart = await _resolve_chart_from_state(state, session, user.id)
    if chart is None:
        await callback.answer(_SESSION_LOST, show_alert=True)
        return

    await state.set_state(MasterMeetingState.waiting_url)
    if isinstance(callback.message, Message):
        await callback.message.answer(_URL_PROMPT)
    await callback.answer()


@master_meeting_router.message(MasterMeetingState.waiting_url, F.text)
async def handle_url_input(
    message: Message,
    session: AsyncSession,
    state: FSMContext,
    user: User,
) -> None:
    text = (message.text or "").strip()
    if not _is_valid_url(text):
        await message.answer(_INVALID_URL)
        return

    chart = await _resolve_chart_from_state(state, session, user.id)
    if chart is None:
        await state.set_state(None)
        await message.answer(_NOT_YOUR_CHART)
        return

    source_type = MasterMeetingSource(detect_source_type(text))
    meeting = await _meeting_repo.create_queued(
        session,
        user_id=user.id,
        chart_id=chart.id,
        source_url=text,
        source_type=source_type,
    )
    await session.commit()
    # Exit upload FSM but keep _FSM_MEETING_CHART so subsequent menu
    # interactions (view/delete) keep working.
    await state.set_state(None)

    await transcribe_master_meeting.kiq(str(meeting.id))

    logger.info(
        "master_meeting.queued",
        meeting_id=str(meeting.id),
        chart_id=str(chart.id),
        user_id=str(user.id),
        source_type=source_type.value,
        url_prefix=text[:60],
    )
    await message.answer(_QUEUED_MSG)


# ── view / delete ────────────────────────────────────────────────────────


@master_meeting_router.callback_query(F.data.startswith("mm:v:"))
async def handle_view(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    if not callback.data:
        await callback.answer()
        return
    parts = callback.data.split(":")
    meeting_id = _parse_uuid(parts, 2)
    if meeting_id is None:
        await callback.answer("Неверная встреча", show_alert=True)
        return

    meeting = await _meeting_repo.get_by_id(session, meeting_id)
    if meeting is None or meeting.user_id != user.id:
        await callback.answer("Встреча не найдена", show_alert=True)
        return

    if meeting.status != MasterMeetingStatus.ready:
        status_text = _status_label(meeting.status)
        body = f"<b>Встреча от {meeting.uploaded_at.strftime('%d.%m.%Y')}</b>\n\n"
        body += f"Статус: {status_text}\n"
        if meeting.status == MasterMeetingStatus.failed and meeting.error:
            body += f"Причина: <i>{meeting.error[:300]}</i>"
    else:
        summary_block = meeting.summary or "<i>выжимка ещё не готова</i>"
        body = f"<b>Встреча от {meeting.uploaded_at.strftime('%d.%m.%Y')}</b>\n\n{summary_block}"

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🗑 Удалить встречу",
                    callback_data=f"mm:d:{meeting_id}",
                )
            ],
            [InlineKeyboardButton(text="↩ Назад", callback_data="mm:back")],
        ]
    )
    if isinstance(callback.message, Message):
        await callback.message.answer(body, reply_markup=kb)
    await callback.answer()


@master_meeting_router.callback_query(F.data == "mm:back")
async def handle_back_to_list(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    state: FSMContext,
) -> None:
    chart = await _resolve_chart_from_state(state, session, user.id)
    if chart is None:
        await callback.answer(_SESSION_LOST, show_alert=True)
        return
    meetings = await _meeting_repo.list_by_chart(session, chart.id)
    if isinstance(callback.message, Message):
        await callback.message.answer(_EXPLAINER, reply_markup=_menu_kb(chart.id, meetings))
    await callback.answer()


@master_meeting_router.callback_query(F.data.startswith("mm:d:"))
async def handle_delete_request(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    if not callback.data:
        await callback.answer()
        return
    parts = callback.data.split(":")
    meeting_id = _parse_uuid(parts, 2)
    if meeting_id is None:
        await callback.answer("Неверная встреча", show_alert=True)
        return
    meeting = await _meeting_repo.get_by_id(session, meeting_id)
    if meeting is None or meeting.user_id != user.id:
        await callback.answer("Встреча не найдена", show_alert=True)
        return

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🗑 Удалить навсегда",
                    callback_data=f"mm:dc:{meeting_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Отмена",
                    callback_data=f"mm:v:{meeting_id}",
                )
            ],
        ]
    )
    if isinstance(callback.message, Message):
        await callback.message.answer(
            "Удалить эту встречу? Расшифровка и выжимка будут стёрты безвозвратно.",
            reply_markup=kb,
        )
    await callback.answer()


@master_meeting_router.callback_query(F.data.startswith("mm:dc:"))
async def handle_delete_confirm(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    state: FSMContext,
) -> None:
    if not callback.data:
        await callback.answer()
        return
    parts = callback.data.split(":")
    meeting_id = _parse_uuid(parts, 2)
    if meeting_id is None:
        await callback.answer("Неверная встреча", show_alert=True)
        return

    meeting = await _meeting_repo.get_by_id(session, meeting_id)
    if meeting is None or meeting.user_id != user.id:
        await callback.answer("Встреча не найдена", show_alert=True)
        return

    deleted = await _meeting_repo.delete(session, meeting_id)
    await session.commit()
    if not deleted:
        await callback.answer("Уже удалена", show_alert=True)
        return

    logger.info(
        "master_meeting.deleted",
        meeting_id=str(meeting_id),
        user_id=str(user.id),
    )
    chart = await _resolve_chart_from_state(state, session, user.id)
    if isinstance(callback.message, Message):
        with contextlib.suppress(Exception):
            await callback.message.edit_text("Встреча удалена.")
        if chart is not None:
            meetings = await _meeting_repo.list_by_chart(session, chart.id)
            await callback.message.answer(_EXPLAINER, reply_markup=_menu_kb(chart.id, meetings))
    await callback.answer()
