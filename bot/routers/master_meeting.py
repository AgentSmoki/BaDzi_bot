"""Wave 5 — master-meeting upload + list + delete handlers.

UI:
    meeting:show:<chart_id>          intro + active list + add button
    meeting:add:<chart_id>           explainer → FSM waiting_url
    <user pastes URL>                enqueue TaskIQ → «принимаю в работу»
    meeting:cancel_add:<chart_id>    abort upload FSM
    meeting:view:<meeting_id>:<chart_id>     show summary inline
    meeting:delete:<meeting_id>:<chart_id>   confirm dialog
    meeting:delete_confirm:<m>:<c>   repo.delete + back to list

Background work happens in `tasks/master_meeting.py` via TaskIQ. The
handler only enqueues + writes the «queued» row; the user gets a
Telegram message when the worker finishes.
"""

from __future__ import annotations

import contextlib
import uuid

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

_NOT_YOUR_CHART = "Эта карта не ваша или удалена."

_EXPLAINER = (
    "<b>🎓 Встречи с мастером</b>\n\n"
    "Когда вы проходите живую сессию с мастером — пришлите мне ссылку "
    "на запись (Google Drive, Yandex Disk, Cloud Mail, YouTube, Zoom). "
    "Я расшифрую и сделаю выжимку — потом буду учитывать глубинные "
    "аспекты из этих встреч, когда вы задаёте вопросы.\n\n"
    "Чтобы добавить встречу — нажмите «Добавить ссылку» и пришлите URL "
    "одним сообщением."
)
_URL_PROMPT = (
    "Пришлите ссылку на запись встречи. Я приму её и расшифрую в "
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
        [InlineKeyboardButton(text="➕ Добавить ссылку", callback_data=f"meeting:add:{chart_id}")]
    ]
    for m in meetings[:8]:  # cap UI; older meetings paginated later if needed
        rows.append(
            [
                InlineKeyboardButton(
                    text=_meeting_short_label(m),
                    callback_data=f"meeting:view:{m.id}:{chart_id}",
                )
            ]
        )
    rows.append(
        [InlineKeyboardButton(text="↩ Назад к карте", callback_data=f"chart:open:{chart_id}")]
    )
    return InlineKeyboardMarkup(inline_keyboard=rows)


# ── meeting:show ─────────────────────────────────────────────────────────


@master_meeting_router.callback_query(F.data.startswith("meeting:show:"))
async def handle_show(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
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

    meetings = await _meeting_repo.list_by_chart(session, chart_id)
    if isinstance(callback.message, Message):
        await callback.message.answer(_EXPLAINER, reply_markup=_menu_kb(chart_id, meetings))
    await callback.answer()


# ── meeting:add → FSM ────────────────────────────────────────────────────


@master_meeting_router.callback_query(F.data.startswith("meeting:add:"))
async def handle_add_start(
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

    await state.set_state(MasterMeetingState.waiting_url)
    await state.update_data(meeting_chart_id=str(chart_id))
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

    data = await state.get_data()
    raw = data.get("meeting_chart_id")
    if not isinstance(raw, str):
        await state.clear()
        return
    chart_id = uuid.UUID(raw)
    chart = await _load_chart_for_user(session, chart_id=chart_id, user_id=user.id)
    if chart is None:
        await state.clear()
        await message.answer(_NOT_YOUR_CHART)
        return

    source_type = MasterMeetingSource(detect_source_type(text))
    meeting = await _meeting_repo.create_queued(
        session,
        user_id=user.id,
        chart_id=chart_id,
        source_url=text,
        source_type=source_type,
    )
    await session.commit()
    await state.clear()

    # Enqueue background transcribe — TaskIQ persists to Redis, worker
    # picks it up. ``meeting_id_str`` mirrors the task signature.
    await transcribe_master_meeting.kiq(str(meeting.id))

    logger.info(
        "master_meeting.queued",
        meeting_id=str(meeting.id),
        chart_id=str(chart_id),
        user_id=str(user.id),
        source_type=source_type.value,
        url_prefix=text[:60],
    )
    await message.answer(_QUEUED_MSG)


# ── view / delete ────────────────────────────────────────────────────────


@master_meeting_router.callback_query(F.data.startswith("meeting:view:"))
async def handle_view(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    if not callback.data:
        await callback.answer()
        return
    parts = callback.data.split(":")
    meeting_id = _parse_uuid(parts, 2)
    chart_id = _parse_uuid(parts, 3)
    if meeting_id is None or chart_id is None:
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
                    callback_data=f"meeting:delete:{meeting_id}:{chart_id}",
                )
            ],
            [InlineKeyboardButton(text="↩ Назад", callback_data=f"meeting:show:{chart_id}")],
        ]
    )
    if isinstance(callback.message, Message):
        await callback.message.answer(body, reply_markup=kb)
    await callback.answer()


@master_meeting_router.callback_query(F.data.startswith("meeting:delete:"))
async def handle_delete_request(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    if not callback.data:
        await callback.answer()
        return
    parts = callback.data.split(":")
    meeting_id = _parse_uuid(parts, 2)
    chart_id = _parse_uuid(parts, 3)
    if meeting_id is None or chart_id is None:
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
                    callback_data=f"meeting:delete_confirm:{meeting_id}:{chart_id}",
                )
            ],
            [
                InlineKeyboardButton(
                    text="Отмена",
                    callback_data=f"meeting:view:{meeting_id}:{chart_id}",
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


@master_meeting_router.callback_query(F.data.startswith("meeting:delete_confirm:"))
async def handle_delete_confirm(callback: CallbackQuery, session: AsyncSession, user: User) -> None:
    if not callback.data:
        await callback.answer()
        return
    parts = callback.data.split(":")
    meeting_id = _parse_uuid(parts, 2)
    chart_id = _parse_uuid(parts, 3)
    if meeting_id is None or chart_id is None:
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
    if isinstance(callback.message, Message):
        with contextlib.suppress(Exception):
            await callback.message.edit_text("Встреча удалена.")
        meetings = await _meeting_repo.list_by_chart(session, chart_id)
        await callback.message.answer(_EXPLAINER, reply_markup=_menu_kb(chart_id, meetings))
    await callback.answer()
