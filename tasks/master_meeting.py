"""Wave 5 — background TaskIQ task for master-meeting transcription.

The handler enqueues ``transcribe_master_meeting`` immediately after the
user supplies the URL; the worker process picks it up, calls TT URL
endpoint, generates LLM summary, and flips the meeting status to
``ready``/``failed``. The user gets a Telegram notification at the end
of the chain.
"""

from __future__ import annotations

import uuid
from typing import cast

import structlog
from aiogram import Bot
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ai.orchestrator import ChatMessage, OrchestratorError, chat
from bot.config import get_settings
from bot.services.teletranscribe import TeleTranscribeError, transcribe_url
from db.engine import get_engine
from db.models import MasterMeetingStatus, User
from db.repositories.master_meeting_repo import MasterMeetingRepository
from tasks.broker import broker

logger = structlog.get_logger(__name__)


_SUMMARY_SYSTEM_PROMPT = (
    "Ты делаешь выжимку из расшифровки сессии с мастером Бацзы. "
    "Верни структурированный markdown с тремя разделами:\n\n"
    "## Темы\nкороткий список основных тем, по 5-12 слов на пункт.\n\n"
    "## Рекомендации мастера\nконкретные советы и техники, которые "
    "мастер дал клиенту, дословно цитируй ключевые формулировки.\n\n"
    "## Глубинные аспекты карты\nособенности карты рождения, которые "
    "мастер выделил — звёзды, столпы, такты.\n\n"
    "Не выдумывай — опирайся только на текст расшифровки. Стиль — деловой, "
    "без воды. Максимум 2000 символов на всю выжимку."
)


async def _generate_summary(transcript: str) -> str | None:
    """Run the fast LLM on the transcript to extract a structured
    summary. Returns ``None`` on LLM failure so the meeting still
    lands as ``ready`` with the raw transcript only."""
    settings = get_settings()
    # Truncate very long transcripts before the LLM call — fast model
    # has a smaller useful window than the main tier.
    truncated = transcript if len(transcript) < 60_000 else transcript[:60_000] + "\n[…обрезано]"
    try:
        result = await chat(
            provider="openrouter",
            model=settings.fast_model,
            messages=[
                ChatMessage(role="system", content=_SUMMARY_SYSTEM_PROMPT),
                ChatMessage(role="user", content=f"Расшифровка:\n\n{truncated}"),
            ],
            temperature=0.3,
            max_tokens=settings.fast_max_tokens,
        )
    except OrchestratorError as exc:
        logger.warning("master_meeting.summary_failed", error=str(exc))
        return None
    return result.text.strip() or None


@broker.task
async def transcribe_master_meeting(meeting_id_str: str) -> None:
    """Background task: TT-URL transcribe → LLM summary → update row +
    notify user.

    Receives ``meeting_id`` as a string because TaskIQ serialises
    arguments via JSON (UUID isn't native)."""
    meeting_id = uuid.UUID(meeting_id_str)
    settings = get_settings()
    engine = get_engine()
    session_factory = async_sessionmaker(engine, expire_on_commit=False)
    meeting_repo = MasterMeetingRepository()

    # Step 1: mark as transcribing.
    async with session_factory() as session:
        meeting = await meeting_repo.get_by_id(session, meeting_id)
        if meeting is None:
            logger.warning("master_meeting.task.row_missing", meeting_id=meeting_id_str)
            return
        await meeting_repo.update_status(
            session, meeting_id=meeting_id, status=MasterMeetingStatus.transcribing
        )
        await session.commit()
        source_url = meeting.source_url
        chart_id = meeting.chart_id
        user_id = meeting.user_id

    # Step 2: transcribe (long, no DB session held).
    try:
        transcribe_result = await transcribe_url(url=source_url)
    except TeleTranscribeError as exc:
        async with session_factory() as session:
            await meeting_repo.update_status(
                session,
                meeting_id=meeting_id,
                status=MasterMeetingStatus.failed,
                error=str(exc),
            )
            await session.commit()
        await _notify_user(
            user_id=user_id,
            text=(
                "Не получилось расшифровать встречу. Возможные причины: "
                "ссылка приватная, файл слишком большой, или сервис "
                "сейчас недоступен. Попробуйте ещё раз позже или дайте "
                "другую ссылку."
            ),
            session_factory=session_factory,
        )
        return

    transcript = cast(str, transcribe_result["text"])
    duration = cast("int | None", transcribe_result.get("duration_seconds"))

    # Step 3: LLM summary (optional).
    summary = await _generate_summary(transcript)

    # Step 4: persist ready state.
    async with session_factory() as session:
        await meeting_repo.update_status(
            session,
            meeting_id=meeting_id,
            status=MasterMeetingStatus.ready,
            transcript=transcript,
            summary=summary,
            duration_seconds=duration,
        )
        await session.commit()

    # Step 5: notify the user.
    notify_text = (
        "<b>🎓 Встреча с мастером расшифрована</b>\n\n"
        + (f"Длительность: {duration // 60} мин\n" if duration else "")
        + "Я уже подключила её к карте — теперь буду учитывать глубинные "
        + "аспекты из встречи в ответах. Текст и выжимку можно посмотреть "
        + "в меню «🎓 Встречи с мастером» на карте."
    )
    await _notify_user(user_id=user_id, text=notify_text, session_factory=session_factory)
    logger.info(
        "master_meeting.task.ready",
        meeting_id=meeting_id_str,
        chart_id=str(chart_id),
        duration_seconds=duration,
        summary_chars=len(summary or ""),
        free_bypass=settings.forecast_free_bypass,
    )


async def _notify_user(
    *,
    user_id: uuid.UUID,
    text: str,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Telegram-send to a user by user_id. Mirrors the pattern in
    scheduler.jobs._send_or_record_error but without the delivery row."""
    settings = get_settings()
    async with session_factory() as session:
        user = await session.get(User, user_id)
        telegram_id = getattr(user, "telegram_id", None) if user is not None else None
    if telegram_id is None:
        logger.warning("master_meeting.notify.user_missing", user_id=str(user_id))
        return
    bot = Bot(token=settings.bot_token.get_secret_value())
    try:
        await bot.send_message(chat_id=telegram_id, text=text, parse_mode="HTML")
    except (TelegramBadRequest, TelegramForbiddenError) as exc:
        logger.warning(
            "master_meeting.notify.failed",
            user_id=str(user_id),
            error=str(exc),
            exc_type=type(exc).__name__,
        )
    finally:
        await bot.session.close()
