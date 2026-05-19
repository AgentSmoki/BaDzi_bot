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
import uuid as _uuid
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
from ai.prompts import load_base_prompt, load_system_prompt
from ai.router import route
from ai.skill_router import select_skill
from ai.skills import SkillSpec, load_skill
from ai.skills.loader import SkillFileError
from ai.temporal_context import compose_messages, get_current_bazi
from bot.config import get_settings
from bot.keyboards import add_partner_chart_kb, pricing_kb
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

# Wave 6 / Phase 6: confidence threshold for skill_router below which we
# fall back to the universal «default» skill. Routers occasionally emit
# low-confidence guesses on ambiguous questions — better to give a
# generic-but-correct answer than a specialised-and-wrong one.
_SKILL_ROUTER_CONFIDENCE_FLOOR: float = 0.4

_PARTNER_REQUEST_MSG = (
    "Похоже, вы спрашиваете про конкретного человека. Чтобы я сравнила "
    "ваши карты по столпам дня и месяца — добавьте, пожалуйста, "
    "карту партнёра. Без неё отвечу в общем виде."
)


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
    session: AsyncSession,
    user: User,
    history_store: HistoryStore,
) -> None:
    """Collect one clarifying-question answer at a time.

    FSM data shape (set by handle_question when the skill-router returns
    clarifying_questions): clarifying_questions, answers, skill,
    concept_hints, original_question, plus chart_id from the previous
    handle_ask_pressed.

    Loop logic:
    - On every text turn append to ``answers``.
    - If there are more unanswered questions → send the next one, stay.
    - Once all are collected → reload chart + skill_spec + partner_chart
      and delegate to ``_continue_consultation_with_skill``.
    """
    if not message.text or message.text.startswith("/"):
        return
    answer = message.text.strip()
    if not answer:
        return

    data = await state.get_data()
    questions = data.get("clarifying_questions") or []
    answers = list(data.get("answers") or [])
    if not isinstance(questions, list) or not questions:
        logger.warning(
            "clarifications.lost_state",
            user_id=str(message.from_user.id) if message.from_user else None,
        )
        await state.set_state(None)
        return

    answers.append(answer)

    if len(answers) < len(questions):
        await state.update_data(answers=answers)
        await message.answer(questions[len(answers)])
        return

    # All answers collected — resume the consultation with skill context.
    original_question = str(data.get("original_question") or "")
    skill_name = data.get("skill") or "default"
    concept_hints_raw = data.get("concept_hints") or []
    concept_hints = (
        [str(h) for h in concept_hints_raw] if isinstance(concept_hints_raw, list) else []
    )
    clarifications = [(str(q), str(a)) for q, a in zip(questions, answers, strict=True)]

    chart = await _resolve_active_chart(state, session, user)
    if chart is None or message.bot is None:
        await message.answer(
            "Не нашла карту — вернитесь в меню и постройте её заново.",
            reply_markup=_no_chart_kb(),
        )
        await state.set_state(None)
        return

    logger.info(
        "clarifications.collected",
        skill=skill_name,
        question_count=len(questions),
        original_question=original_question[:80],
    )
    await state.set_state(None)

    chart_data = ChartOutput.model_validate(chart.chart_data)
    skill_spec = _safe_load_skill(skill_name)
    partner_chart_data = await _load_partner_chart_data(session, chart)

    await _continue_consultation_with_skill(
        message,
        chart=chart,
        chart_data=chart_data,
        user=user,
        session=session,
        history_store=history_store,
        original_question=original_question,
        skill_spec=skill_spec,
        partner_chart=partner_chart_data,
        clarifications=clarifications,
        concept_hints=concept_hints,
    )


@consultation_router.callback_query(F.data == "partner:skip")
async def handle_partner_skip(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    history_store: HistoryStore,
) -> None:
    """User chose «Ответить без карты партнёра» — continue the
    consultation in generic mode (skill stays but partner_chart=None)."""
    if not isinstance(callback.message, Message):
        await callback.answer()
        return

    data = await state.get_data()
    original_question = str(data.get("pending_question") or "")
    skill_name = data.get("pending_skill") or "relationships"
    concept_hints_raw = data.get("pending_concept_hints") or []
    concept_hints = (
        [str(h) for h in concept_hints_raw] if isinstance(concept_hints_raw, list) else []
    )

    chart = await _resolve_active_chart(state, session, user)
    if chart is None or not original_question:
        await callback.message.answer(
            "Не нашла исходный вопрос — задайте его заново через меню.",
            reply_markup=_no_chart_kb(),
        )
        await state.set_state(None)
        await callback.answer()
        return

    chart_data = ChartOutput.model_validate(chart.chart_data)
    skill_spec = _safe_load_skill(skill_name)
    await state.set_state(None)

    await _continue_consultation_with_skill(
        callback.message,
        chart=chart,
        chart_data=chart_data,
        user=user,
        session=session,
        history_store=history_store,
        original_question=original_question,
        skill_spec=skill_spec,
        partner_chart=None,
        clarifications=None,
        concept_hints=concept_hints,
    )
    await callback.answer()


def _safe_load_skill(name: str) -> SkillSpec | None:
    """Resolve a SkillName-string into a SkillSpec, falling back to
    ``default`` on file errors. Returns ``None`` only if even ``default``
    won't load (catastrophic — caller treats as legacy flow)."""
    if name not in {"work", "relationships", "health", "time", "default"}:
        name = "default"
    try:
        return load_skill(name)
    except SkillFileError:
        logger.warning("skill.load_failed", skill=name)
        if name != "default":
            try:
                return load_skill("default")
            except SkillFileError:
                pass
        return None


async def _load_partner_chart_data(session: AsyncSession, chart: Chart) -> ChartOutput | None:
    """If ``chart.partner_chart_id`` is set, load the partner Chart and
    parse its JSONB into a ChartOutput. Returns None on miss."""
    if chart.partner_chart_id is None:
        return None
    partner = await _chart_repo.get_by_id(session, chart.partner_chart_id)
    if partner is None:
        return None
    return ChartOutput.model_validate(partner.chart_data)


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
    """Entry point for one consultation turn.

    Two routing paths gated by ``settings.skill_router_enabled``:

    1. **Skill-router (default)** — fast LLM picks a skill, may request
       clarifying questions or a partner chart, then resumes via
       ``_continue_consultation_with_skill`` with skill_spec injected.
    2. **Legacy** — direct call to ``_continue_consultation_with_skill``
       without skill_spec, using the full 39 KB Anastasia system prompt.

    Guards (free-question, no-chart, slash-command) are identical in
    both paths."""
    if not message.text or message.text.startswith("/"):
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

    # Free-question guard (task 1.12.0).
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
    settings = get_settings()

    if not settings.skill_router_enabled:
        # Legacy path — no skill router, full Anastasia prompt as before.
        await _continue_consultation_with_skill(
            message,
            chart=chart,
            chart_data=chart_data,
            user=user,
            session=session,
            history_store=history_store,
            original_question=question,
            skill_spec=None,
            partner_chart=None,
            clarifications=None,
            concept_hints=None,
        )
        return

    # ── Skill-router path (Wave 6 / ADR-010) ─────────────────────────
    history = await history_store.get(user.telegram_id)
    skill_sel = await select_skill(question=question, chart=chart_data, history=history)

    # Downgrade weak picks to default so we don't ship a wrong-specialised reply.
    if skill_sel.confidence < _SKILL_ROUTER_CONFIDENCE_FLOOR and skill_sel.skill != "default":
        logger.info(
            "skill_router.low_confidence_downgrade",
            from_skill=skill_sel.skill,
            confidence=skill_sel.confidence,
        )
        effective_skill: str = "default"
    else:
        effective_skill = skill_sel.skill

    # Branch 1: router wants clarifying questions before answering.
    if skill_sel.clarifying_questions:
        await state.set_state(ConsultationState.collecting_clarifications)
        await state.update_data(
            clarifying_questions=skill_sel.clarifying_questions,
            answers=[],
            skill=effective_skill,
            concept_hints=list(skill_sel.concept_hints),
            original_question=question,
            chart_id=str(chart.id),
        )
        await message.answer(skill_sel.clarifying_questions[0])
        logger.info(
            "consultation.clarifications_requested",
            skill=effective_skill,
            confidence=skill_sel.confidence,
            count=len(skill_sel.clarifying_questions),
        )
        return

    # Branch 2: relationships skill needs a partner chart we don't have.
    if skill_sel.needs_partner_chart and chart.partner_chart_id is None:
        await state.update_data(
            pending_question=question,
            pending_skill=effective_skill,
            pending_concept_hints=list(skill_sel.concept_hints),
            chart_id=str(chart.id),
        )
        await message.answer(_PARTNER_REQUEST_MSG, reply_markup=add_partner_chart_kb())
        logger.info(
            "consultation.partner_chart_requested",
            skill=effective_skill,
            confidence=skill_sel.confidence,
        )
        return

    # Branch 3: straight through to the main LLM with skill body injected.
    skill_spec = _safe_load_skill(effective_skill)
    partner_chart_data = await _load_partner_chart_data(session, chart)

    await _continue_consultation_with_skill(
        message,
        chart=chart,
        chart_data=chart_data,
        user=user,
        session=session,
        history_store=history_store,
        original_question=question,
        skill_spec=skill_spec,
        partner_chart=partner_chart_data,
        clarifications=None,
        concept_hints=list(skill_sel.concept_hints),
    )


# ── Shared consultation continuation ─────────────────────────────────────


async def _continue_consultation_with_skill(
    message: Message,
    *,
    chart: Chart,
    chart_data: ChartOutput,
    user: User,
    session: AsyncSession,
    history_store: HistoryStore,
    original_question: str,
    skill_spec: SkillSpec | None,
    partner_chart: ChartOutput | None,
    clarifications: list[tuple[str, str]] | None,
    concept_hints: list[str] | None,
) -> None:
    """Compose the prompt, call the main LLM, persist, reply.

    Shared between the skill-router happy path, the clarifications
    completion path, the partner-skip path, and the legacy path.
    ``skill_spec is None`` → legacy system prompt (anastasia_system.md);
    non-None → base prompt + injected [SKILL] section.
    """
    if message.bot is None:
        # Defensive — every aiogram Message has .bot in production, but
        # tests sometimes hand us a bare MagicMock.
        return

    decision = route(original_question)

    # Calendar selection (择日) detection.
    cal_request = detect_calendar_request(original_question, now=_today())
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
    needs_temporal = decision.needs_temporal_context or calendar_top is not None
    now_chart = get_current_bazi() if needs_temporal else None

    system_prompt = load_base_prompt() if skill_spec is not None else load_system_prompt()
    messages = compose_messages(
        system_prompt=system_prompt,
        chart=chart_data,
        question=original_question,
        history=history,
        include_temporal=needs_temporal,
        now_chart=now_chart,
        calendar_top=calendar_top,
        calendar_bottom=calendar_bottom,
        calendar_event_type=cal_event_label,
        calendar_start_iso=cal_start_iso,
        calendar_end_iso=cal_end_iso,
        skill_spec=skill_spec,
        partner_chart=partner_chart,
        clarifications=clarifications,
        concept_hints=concept_hints,
    )

    typing_task = asyncio.create_task(_keep_typing(message))
    try:
        answer = await chat_with_fallback(
            messages=messages,
            temperature=decision.temperature,
            intent=decision.intent,
        )
    except OrchestratorError:
        logger.exception("consultation.llm_failed", question=original_question[:80])
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

    await _user_repo.mark_free_question_used(session, user.id)

    await history_store.append(
        user.telegram_id, ChatMessage(role="user", content=original_question)
    )
    await history_store.append(user.telegram_id, ChatMessage(role="assistant", content=text))
    await _consultation_repo.create(
        session,
        user_id=user.id,
        chart_id=chart.id,
        topic=skill_spec.name if skill_spec is not None else decision.intent,
        user_message=original_question,
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
        skill=skill_spec.name if skill_spec is not None else None,
        had_clarifications=bool(clarifications),
        had_partner_chart=partner_chart is not None,
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
