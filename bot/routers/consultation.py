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
from datetime import date
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

from ai.calendar_parse import detect_calendar_request
from ai.context import HistoryStore
from ai.fallback import chat_with_fallback
from ai.orchestrator import ChatMessage, OrchestratorError
from ai.prompts import load_system_prompt
from ai.router import route
from ai.temporal_context import compose_messages, get_current_bazi
from bot.config import get_settings
from bot.keyboards import pricing_kb
from bot.states import ConsultationState
from calculator.calendar_select import EVENT_TYPE_RU, pick_best_dates
from calculator.models import ChartOutput
from db.models import Chart, User
from db.repositories.chart_repo import ChartRepository
from db.repositories.consultation_repo import ConsultationRepository
from db.repositories.user_repo import UserRepository

logger = structlog.get_logger(__name__)

consultation_router = Router(name="consultation")

_chart_repo = ChartRepository()
_consultation_repo = ConsultationRepository()
_user_repo = UserRepository()


_FREE_QUESTION_USED_MSG = (
    "У вас был один бесплатный вопрос. Чтобы продолжить диалог с Анастасией, выберите тариф ниже."
)

# Wave 6 / Phase 4: placeholder used by the clarifying-questions FSM
# loop when all answers have been collected. Phase 6 replaces this with
# a real call to ``_continue_consultation_with_skill`` that uses the
# accumulated clarifications + skill_name + concept_hints in the LLM
# prompt. Until Phase 6 lands, the handler just acknowledges and clears
# state so the FSM scaffolding can be tested in isolation.
_CLARIFICATIONS_DONE_MSG = "Спасибо, я учла ваши уточнения. Минуту, готовлю ответ."


def _today() -> date:
    """Indirection so tests can pin "today" without freezegun."""
    return date.today()


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

    await callback.message.answer("Напишите ваш вопрос:")
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


@consultation_router.message(ConsultationState.collecting_clarifications, F.text)
async def handle_clarification_answer(
    message: Message,
    state: FSMContext,
) -> None:
    """Collect one clarifying-question answer at a time.

    FSM data shape (set by handle_question in Phase 6 when the skill
    router returns clarifying_questions):
    - ``clarifying_questions: list[str]``  — original 1-3 questions
    - ``answers: list[str]``               — what the user has said so far
    - ``skill: str``                       — selected skill name
    - ``concept_hints: list[str]``         — RAG hints from the router
    - ``original_question: str``           — the user's first turn

    Loop logic:
    - On every text turn append to ``answers``.
    - If there are more unanswered questions → send the next one, stay.
    - Once ``len(answers) == len(clarifying_questions)`` → exit clarifications,
      delegate to ``_continue_consultation_with_skill`` (Phase 6) which will
      build the prompt with [CLARIFICATIONS] section and call the main LLM.

    Phase 4 (this commit): the «all collected» branch posts a placeholder
    message and clears state. Phase 6 wires it into the real consultation
    flow. The FSM mechanics are exercised by tests regardless.
    """
    if not message.text or message.text.startswith("/"):
        # Slash commands fall through to their own handlers; bail.
        return
    answer = message.text.strip()
    if not answer:
        return

    data = await state.get_data()
    questions = data.get("clarifying_questions") or []
    answers = list(data.get("answers") or [])
    if not isinstance(questions, list) or not questions:
        # FSM data lost — graceful exit so the user isn't stuck.
        logger.warning(
            "clarifications.lost_state",
            user_id=str(message.from_user.id) if message.from_user else None,
        )
        await state.set_state(None)
        return

    answers.append(answer)

    if len(answers) < len(questions):
        # Ask the next one, persist progress.
        await state.update_data(answers=answers)
        await message.answer(questions[len(answers)])
        return

    # All answers collected — Phase 6 will call the real continuation here.
    await state.update_data(answers=answers)
    logger.info(
        "clarifications.collected",
        skill=data.get("skill"),
        question_count=len(questions),
        original_question=str(data.get("original_question"))[:80],
    )
    await message.answer(_CLARIFICATIONS_DONE_MSG)
    await state.set_state(None)


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


# ── pricing:skip — admin testing aid ─────────────────────────────────────


@consultation_router.callback_query(F.data == "pricing:skip")
async def handle_pricing_skip(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    state: FSMContext,
) -> None:
    """Admin-only: reset the free-question flag so the same user can
    keep asking. Used during pre-release testing — we need to ask many
    questions in one session without paying. Hardened: the button is
    only added to ``pricing_kb`` for admin (see consultation guard),
    but we still re-check ``user.telegram_id == admin_telegram_id``
    here in case the callback_data ever leaks (no-op on non-admin).
    """
    settings = get_settings()
    if user.telegram_id != settings.admin_telegram_id:
        # Non-admin clicked a leaked admin callback — silently dismiss.
        await callback.answer()
        return

    await _user_repo.reset_free_question(session, user.id)
    user.free_question_used = False
    await callback.answer("Сброшено — задавайте следующий вопрос")
    if isinstance(callback.message, Message):
        await callback.message.answer(
            "🔧 Тестовый режим: лимит сброшен. Нажмите «Задать вопрос» и продолжайте.",
        )
    logger.info("pricing.admin_skip", user_id=str(user.id), telegram_id=user.telegram_id)


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

    # Free-question guard (task 1.12.0): new users get one free dialogue
    # turn; the second attempt is gated behind pricing. Without this,
    # an unsubscribed user could hammer OpenRouter tokens indefinitely.
    if user.free_question_used:
        settings = get_settings()
        is_admin = user.telegram_id == settings.admin_telegram_id
        await message.answer(
            _FREE_QUESTION_USED_MSG,
            reply_markup=pricing_kb(allow_skip=is_admin),
        )
        await state.set_state(None)
        logger.info(
            "consultation.blocked_by_free_question_guard",
            user_id=str(user.id),
            telegram_id=user.telegram_id,
            admin_skip_offered=is_admin,
        )
        return

    chart_data = ChartOutput.model_validate(chart.chart_data)
    decision = route(question)

    # Calendar selection (择日) detection — runs *before* the regular
    # LLM call. If the user asks "лучшие даты для свадьбы в июне",
    # we pre-score every day in the range against their natal chart
    # and pass the table to the LLM. Without this, Anastasia would
    # have to invent dates from her training data (= hallucination).
    cal_request = detect_calendar_request(question, now=_today())
    calendar_top = None
    calendar_bottom = None
    cal_event_label = None
    cal_start_iso = None
    cal_end_iso = None
    if cal_request is not None and cal_request.event_type is not None:
        cal_start_iso = cal_request.start.isoformat()
        cal_end_iso = cal_request.end.isoformat()
        cal_event_label = EVENT_TYPE_RU[cal_request.event_type]
        try:
            calendar_top, calendar_bottom = pick_best_dates(
                chart_data,
                cal_request.start,
                cal_request.end,
                cal_request.event_type,
            )
            logger.info(
                "consultation.calendar_select_attached",
                event_type=cal_request.event_type,
                horizon_days=cal_request.horizon_days,
                top_count=len(calendar_top),
                bottom_count=len(calendar_bottom),
            )
        except Exception:
            logger.exception("consultation.calendar_select_failed")
            calendar_top = None
            calendar_bottom = None

    history = await history_store.get(user.telegram_id)
    # Temporal context is needed both when the router flags it AND
    # when calendar block is attached (for resonance computation).
    needs_temporal = decision.needs_temporal_context or calendar_top is not None
    now_chart = get_current_bazi() if needs_temporal else None
    messages = compose_messages(
        system_prompt=load_system_prompt(),
        chart=chart_data,
        question=question,
        history=history,
        include_temporal=needs_temporal,
        now_chart=now_chart,
        calendar_top=calendar_top,
        calendar_bottom=calendar_bottom,
        calendar_event_type=cal_event_label,
        calendar_start_iso=cal_start_iso,
        calendar_end_iso=cal_end_iso,
    )

    typing_task = asyncio.create_task(_keep_typing(message))
    try:
        answer = await chat_with_fallback(
            messages=messages,
            temperature=decision.temperature,
            intent=decision.intent,
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

    # Free-question is now consumed — next question goes to pricing.
    # Done after a successful LLM answer so a failed turn doesn't burn
    # the user's one free try.
    await _user_repo.mark_free_question_used(session, user.id)

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
        tier=answer.tier,
        provider=answer.provider,
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
