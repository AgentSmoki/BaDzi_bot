"""Consultation router — text Q&A with Anastasia (1.13).

Wires together everything from 1.8:
- ``ai.router.route`` decides intent / model / max_tokens
- ``ai.context.HistoryStore`` provides per-user dialogue history
- ``ai.temporal_context.compose_messages`` assembles the prompt
- ``ai.fallback.chat_with_fallback`` calls the LLM with retry-on-5xx
- ``db.repositories.consultation_repo.create`` persists the turn

User flow:
1. Pressing "Задать вопрос" (callback `menu:ask`) loads the user's
   most recent chart, parks the user in ``ConsultationState
   .waiting_question``, and prompts for a question.
2. The next text message is treated as the question. While the LLM
   is thinking we send periodic ``ChatAction.TYPING`` so the chat
   shows "Анастасия печатает..." up to ~60 sec.
3. The reply is rendered with HTML, history is appended, the
   ``Consultation`` row is written, and the user gets buttons to
   ask another question or return to menu.
4. ``/reset`` clears the user's dialogue history (per ADR-002 the
   chart itself is never reset — only the conversational memory).

Failure modes are surfaced gently — if the LLM/Redis/DB fails the
user gets a Russian message asking to retry, and the FSM state is
preserved so they can just resend the question.
"""

from __future__ import annotations

import asyncio
import contextlib
from decimal import Decimal

import structlog
from aiogram import F, Router
from aiogram.enums import ChatAction
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardMarkup,
    Message,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from sqlalchemy.ext.asyncio import AsyncSession

from ai.context import HistoryStore
from ai.fallback import chat_with_fallback
from ai.orchestrator import ChatMessage, OrchestratorError
from ai.prompts import load_system_prompt
from ai.router import route
from ai.temporal_context import compose_messages, get_current_bazi
from bot.states import ConsultationState
from calculator.models import ChartOutput
from db.models import Chart, User
from db.repositories.chart_repo import ChartRepository
from db.repositories.consultation_repo import ConsultationRepository

logger = structlog.get_logger(__name__)

consultation_router = Router(name="consultation")

_chart_repo = ChartRepository()
_consultation_repo = ConsultationRepository()


# ── Keyboards (local — small enough to colocate) ─────────────────────────


def _after_answer_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Ещё вопрос", callback_data="menu:ask")
    builder.button(text="В меню", callback_data="menu:back")
    builder.adjust(1)
    return builder.as_markup()


def _no_chart_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="Рассчитать карту", callback_data="menu:calc")
    builder.button(text="В меню", callback_data="menu:back")
    builder.adjust(1)
    return builder.as_markup()


# ── Entry: user pressed "Задать вопрос" ──────────────────────────────────


@consultation_router.callback_query(F.data == "menu:ask")
async def handle_ask_pressed(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: User,
) -> None:
    """Load the active chart and park the user in waiting_question.

    The kb is usually attached to a chart photo (`chart_actions_kb`), so
    we send the prompt as a *new* message instead of editing the photo —
    Telegram rejects edit_text on a photo with `Bad Request: there is no
    text in the message to edit`. New message also keeps the chart photo
    visible so the user can see what they're asking about.
    """
    if not isinstance(callback.message, Message):
        await callback.answer()
        return

    chart = await _resolve_active_chart(state, session, user)
    if chart is None:
        await callback.message.answer(
            "Сначала постройте карту — Анастасия отвечает только на её основе.",
            reply_markup=_no_chart_kb(),
        )
        await callback.answer()
        return

    await state.update_data(chart_id=str(chart.id))
    await state.set_state(ConsultationState.waiting_question)

    await callback.message.answer(
        "Напишите ваш вопрос Анастасии. Например:\n"
        "• «Расскажи про мою карту в общем»\n"
        "• «Что подсвечивает текущий столп удачи»\n"
        "• «Какие сильные стороны видно по карте»\n\n"
        "Можно отправить /reset чтобы очистить историю диалога.",
    )
    await callback.answer()


async def _resolve_active_chart(
    state: FSMContext, session: AsyncSession, user: User
) -> Chart | None:
    """Pick the chart this conversation is about. FSM `chart_id`
    wins (set when user just built or opened one); otherwise we fall
    back to the user's most recent chart."""
    import uuid as _uuid

    fsm_data = await state.get_data()
    raw_id = fsm_data.get("chart_id")
    if raw_id:
        try:
            return await _chart_repo.get_by_id(session, _uuid.UUID(str(raw_id)))
        except (ValueError, AttributeError):
            pass
    return await _chart_repo.get_latest_by_user(session, user.id)


# ── /reset — clear dialogue history ──────────────────────────────────────


@consultation_router.message(F.text == "/reset")
async def handle_reset(
    message: Message,
    user: User,
    history_store: HistoryStore,
    state: FSMContext,
) -> None:
    await history_store.clear(user.telegram_id)
    await state.set_state(None)
    await message.answer("История диалога очищена. Карта осталась.")


# ── Question handler ─────────────────────────────────────────────────────


@consultation_router.message(ConsultationState.waiting_question, F.text)
async def handle_question(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    history_store: HistoryStore,
) -> None:
    """Route the question, call LLM with typing indicator, persist
    the turn, and reply to the user."""
    if not message.text or message.text.startswith("/"):
        # Slash-commands fall through to other handlers; bail out
        # cleanly here so we don't double-process them.
        return
    question = message.text.strip()
    if not question:
        await message.answer("Пожалуйста, задайте вопрос текстом.")
        return

    chart = await _resolve_active_chart(state, session, user)
    if chart is None or message.bot is None:
        await message.answer(
            "Не нашла карту — постройте её через меню и повторите вопрос.",
            reply_markup=_no_chart_kb(),
        )
        await state.set_state(None)
        return

    chart_data = ChartOutput.model_validate(chart.chart_data)
    decision = route(question)

    history = await history_store.get(user.telegram_id)
    now_chart = get_current_bazi() if decision.needs_temporal_context else None
    messages = compose_messages(
        system_prompt=load_system_prompt(),
        chart=chart_data,
        question=question,
        history=history,
        include_temporal=decision.needs_temporal_context,
        now_chart=now_chart,
    )

    typing_task = asyncio.create_task(_keep_typing(message))
    try:
        answer = await chat_with_fallback(
            messages=messages,
            temperature=decision.temperature,
            max_tokens=decision.max_tokens,
        )
    except OrchestratorError:
        logger.exception("consultation.llm_failed", question=question[:80])
        await message.answer(
            "Анастасия не смогла ответить — попробуйте задать вопрос ещё раз.",
            reply_markup=_after_answer_kb(),
        )
        return
    finally:
        typing_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await typing_task

    text = answer.result.text.strip()
    await message.answer(text, reply_markup=_after_answer_kb())

    # Persist the turn — both sides — so future history requests have
    # the full transcript and so /admin export gets the row.
    await history_store.append(user.telegram_id, ChatMessage(role="user", content=question))
    await history_store.append(user.telegram_id, ChatMessage(role="assistant", content=text))
    await _consultation_repo.create(
        session,
        user_id=user.id,
        chart_id=chart.id,
        topic=decision.intent,
        user_message=question,
        ai_response=text,
        model_used=answer.result.model,
        prompt_tokens=answer.result.usage.prompt_tokens,
        completion_tokens=answer.result.usage.completion_tokens,
        cost_usd=Decimal(str(answer.result.usage.cost_usd)),
        latency_ms=answer.result.latency_ms,
        trace_id=answer.result.trace_id,
    )

    logger.info(
        "consultation.completed",
        intent=decision.intent,
        used_fallback=answer.used_fallback,
        latency_ms=answer.result.latency_ms,
        cost_usd=answer.result.usage.cost_usd,
        completion_tokens=answer.result.usage.completion_tokens,
        trace_id=answer.result.trace_id,
    )


async def _keep_typing(message: Message) -> None:
    """Send ``ChatAction.TYPING`` every 4 seconds while the LLM is
    thinking. Telegram's typing indicator decays after ~5 sec, so
    we have to refresh it. K2.6 thinking averages 30-60 sec, so this
    keeps the user reassured the bot is alive."""
    if message.bot is None:
        return
    while True:
        try:
            await message.bot.send_chat_action(chat_id=message.chat.id, action=ChatAction.TYPING)
        except TelegramBadRequest:
            # The chat closed or message can't carry an action — stop
            # quietly rather than crashing the consultation handler.
            return
        await asyncio.sleep(4)
