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
import io
import re
import uuid as _uuid
from datetime import date
from decimal import Decimal
from typing import get_args

import structlog
from aiogram import Bot, F, Router
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
from ai.prompts import SchoolName, load_base_prompt, load_system_prompt
from ai.rag.llm_extract import extract_concepts_llm
from ai.router import route
from ai.skill_router import select_skill
from ai.skills import SkillSpec, load_skill
from ai.skills.loader import SkillFileError
from ai.skills.models import SkillName
from ai.temporal_context import compose_messages, get_current_bazi
from bot.config import get_settings
from bot.keyboards import (
    add_partner_chart_kb,
    partner_chart_selector_kb,
    pricing_kb,
    school_selector_kb,
)
from bot.services.menu import format_chart_label
from bot.services.teletranscribe import TeleTranscribeError, transcribe_voice
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


def _free_questions_used_msg(limit: int) -> str:
    """Сообщение когда исчерпан лимит бесплатных вопросов. Wave 7 UX
    (2026-05-24): динамическое — раньше было «у вас был ОДИН бесплатный
    вопрос», сейчас лимит ≥ 3."""
    return (
        f"Вы использовали все {limit} бесплатных вопросов. Чтобы продолжить "
        "диалог с Анастасией, выберите тариф ниже — или продолжите бесплатно "
        "(пока подключаем оплату)."
    )


def _remaining_footer(remaining: int, limit: int) -> str:
    """Wave 7 UX footer показывающий сколько бесплатных вопросов
    осталось. Показываем ПОСЛЕ каждого ответа пока ``remaining > 0``.
    Если оплата подключена (или вопросы безлимитны) — не показываем."""
    return f"\n———\n🎁 Осталось бесплатных вопросов: {remaining} из {limit}"


# Wave 6 / Phase 6: confidence threshold for skill_router below which we
# fall back to the universal «default» skill. Routers occasionally emit
# low-confidence guesses on ambiguous questions — better to give a
# generic-but-correct answer than a specialised-and-wrong one.
_SKILL_ROUTER_CONFIDENCE_FLOOR: float = 0.4

# Wave 7 Phase 2 — valid callback values for the school selector.
# Kept in sync with ai/prompts.SchoolName via a small parser below.
_VALID_SCHOOLS: frozenset[str] = frozenset({"classic", "edoha", "modern"})


def _parse_school(raw: str | None) -> SchoolName | None:
    """Narrow FSM-data ``chosen_school`` (Any) to ``SchoolName | None``.
    Unknown values silently fall back to ``None`` — that path drops the
    school overlay and uses the universal ``base.md`` alone."""
    if isinstance(raw, str) and raw in _VALID_SCHOOLS:
        return raw  # type: ignore[return-value]
    return None


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
    # Wave 7 Phase 2 (ADR-011) — before each question the user picks
    # an interpretation school. handle_school_chosen then advances to
    # waiting_question and persists chosen_school in FSM data so every
    # entry-point downstream (handle_question / clarifications / partner
    # skip / resume_after_partner_added) can thread it into the
    # load_base_prompt call that builds the system prompt.
    await state.set_state(ConsultationState.choosing_school)
    await callback.message.answer(
        "Какой подход вам ближе? Выберите школу — от этого зависит стиль и методология ответа.",
        reply_markup=school_selector_kb(),
    )
    await callback.answer()


# Wave 7 Phase 2 — school selector callback. Catches all three buttons
# (school:classic / school:edoha / school:modern) from school_selector_kb.
@consultation_router.callback_query(ConsultationState.choosing_school, F.data.startswith("school:"))
async def handle_school_chosen(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Persist chosen_school in FSM data and advance to waiting_question.

    Wave 7 / ADR-011: the three coexisting schools (classic / edoha /
    modern) live as methodology overlays on top of ``base.md``. Selection
    here is read later by every consultation entry-point (handle_question,
    clarifications collector, partner-skip, partner-add resume) and
    threaded into ``load_base_prompt(school=...)``.
    """
    if not isinstance(callback.message, Message) or not callback.data:
        await callback.answer()
        return

    raw_school = callback.data.removeprefix("school:")
    school = _parse_school(raw_school)
    if school is None:
        # Defensive — UI only exposes the 3 valid options, so a non-match
        # here means a stale callback from an old keyboard build. Surface
        # gently and stay in selector state.
        await callback.answer("Школа не распознана. Выберите вариант с кнопок.", show_alert=False)
        return

    await state.update_data(chosen_school=school)
    await state.set_state(ConsultationState.waiting_question)

    # Friendly confirmation per school so the user feels the switch.
    confirmations = {
        "classic": (
            "Школа 🎓 Классическая — отвечу через 10 Богов, Структуру "
            "и Полезное Божество. Напишите вопрос:"
        ),
        "edoha": (
            "Школа 🌀 Мастер ЭдоХа — отвечу через накопленные силы "
            "и метафоры поля. Напишите вопрос:"
        ),
        "modern": (
            "Школа 🧬 Современная — отвечу через архетипы "
            "и психологические паттерны. Напишите вопрос:"
        ),
    }
    await callback.message.answer(confirmations[school])
    await callback.answer()
    logger.info("consultation.school_chosen", school=school)


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
    """Text answer to a clarifying question. Slash commands are ignored.
    Delegates the FSM bookkeeping to `_process_clarification_text` so
    the voice handler (`handle_voice_clarification`) can reuse the
    same logic with a transcript.
    """
    if not message.text or message.text.startswith("/"):
        return
    answer = message.text.strip()
    if not answer:
        return
    await _process_clarification_text(
        message,
        state=state,
        session=session,
        user=user,
        history_store=history_store,
        answer=answer,
    )


async def _process_clarification_text(
    message: Message,
    *,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    history_store: HistoryStore,
    answer: str,
) -> None:
    """Append one clarifying-question answer to FSM data and either
    ask the next question or, when all are collected, hand off to the
    main consultation pipeline (partner-chart prompt or skill answer).

    Extracted so both text (`handle_clarification_answer`) and voice
    (`handle_voice_clarification`) paths share the same state logic.
    """
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

    # 1.17.9a fix (2026-05-20): if the router originally flagged
    # needs_partner_chart=True and the chart still has no partner
    # linked, show the partner-chart prompt now instead of falling
    # through to the main LLM. We carry the already-collected
    # clarifications across via `pending_clarifications` so neither
    # partner:skip nor (future) partner:add lose them.
    needs_partner = bool(data.get("needs_partner_chart"))
    if needs_partner and chart.partner_chart_id is None:
        await state.update_data(
            pending_question=original_question,
            pending_skill=skill_name,
            pending_concept_hints=concept_hints,
            pending_clarifications=[list(pair) for pair in clarifications],
            chart_id=str(chart.id),
        )
        await state.set_state(None)
        partner_kb = await _partner_kb_for_user(session, user=user, exclude_chart_id=chart.id)
        await message.answer(_PARTNER_REQUEST_MSG, reply_markup=partner_kb)
        logger.info(
            "consultation.partner_chart_requested_after_clarifications",
            skill=skill_name,
            clarifications_count=len(clarifications),
        )
        return

    await state.set_state(None)

    chart_data = ChartOutput.model_validate(chart.chart_data)
    skill_spec = _safe_load_skill(skill_name)
    partner_chart_data = await _load_partner_chart_data(session, chart)
    chosen_school = _parse_school(data.get("chosen_school"))

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
        chosen_school=chosen_school,
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
    # 1.17.9a fix (2026-05-20): clarifications collected before the
    # partner-chart prompt are preserved across the skip — otherwise
    # users who answered 3 clarifying questions would silently lose
    # that context when they tap «без партнёра».
    clarifications_raw = data.get("pending_clarifications") or []
    clarifications = (
        [(str(q), str(a)) for q, a in clarifications_raw]
        if isinstance(clarifications_raw, list) and clarifications_raw
        else None
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
    chosen_school = _parse_school(data.get("chosen_school"))
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
        clarifications=clarifications,
        concept_hints=concept_hints,
        chosen_school=chosen_school,
    )
    await callback.answer()


# Telegram caps text messages at 4096 chars; 4000 leaves headroom
# for HTML tags and edge-of-paragraph splits.
_TG_MAX_CHARS = 4000


_MD_BOLD_RE = re.compile(r"\*\*(.+?)\*\*", re.DOTALL)


def _markdown_to_html(text: str) -> str:
    """Convert the small subset of Markdown that LLMs reliably emit
    into the HTML tags Telegram understands (the bot ships with
    parse_mode=HTML globally).

    Currently handles: **bold** → <b>bold</b>. Single-asterisk italic
    is left alone because LLMs often use `*` as bullet markers and
    accidentally italicising chunks of a list reads worse than the
    raw star. Backticks and underscores are also left alone for the
    same reason — Telegram tolerates them as text. HTML special
    chars (`<`, `>`, `&`) inside the LLM output are extremely rare
    and the bot accepts loose HTML anyway, so we don't escape them.

    Live regression: ответ Анастасии в Telegram показывал «1. **Кратко**»
    с буквальными звёздочками (2026-05-22). Этот хелпер закрывает gap
    между LLM-форматом и parse_mode=HTML.
    """
    return _MD_BOLD_RE.sub(r"<b>\1</b>", text)


def _split_for_telegram(text: str, max_len: int) -> list[str]:
    """Split a long LLM answer into chunks that fit Telegram's 4096-
    char message limit.

    Prefers paragraph boundaries (double newline), falls back to
    single newlines, then to hard char-slice if a paragraph itself
    is longer than `max_len`. Empty chunks are dropped.
    """
    if len(text) <= max_len:
        return [text]

    out: list[str] = []
    current = ""
    for paragraph in text.split("\n\n"):
        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if len(candidate) <= max_len:
            current = candidate
            continue
        if current:
            out.append(current)
            current = ""
        if len(paragraph) <= max_len:
            current = paragraph
            continue
        # One paragraph alone is bigger than max_len — split on lines,
        # then char-slice as the last resort.
        for line in paragraph.split("\n"):
            line_candidate = line if not current else f"{current}\n{line}"
            if len(line_candidate) <= max_len:
                current = line_candidate
                continue
            if current:
                out.append(current)
                current = ""
            if len(line) <= max_len:
                current = line
            else:
                for i in range(0, len(line), max_len):
                    piece = line[i : i + max_len]
                    if current:
                        out.append(current)
                        current = ""
                    if i + max_len < len(line):
                        out.append(piece)
                    else:
                        current = piece
    if current:
        out.append(current)
    return [c for c in out if c]


async def _partner_kb_for_user(
    session: AsyncSession,
    *,
    user: User,
    exclude_chart_id: _uuid.UUID,
) -> InlineKeyboardMarkup:
    """Pick the right partner-chart keyboard for `user`.

    If they already have OTHER charts in their library (anything other
    than the current owner chart), show a selector so they can re-use
    one as the partner with a single tap. Otherwise fall back to the
    simple add/skip kb — no point listing nothing.

    1.17.11 (2026-05-21) — добавлено по запросу Богдана для UX
    «может карта партнёра уже есть в моих картах».
    """
    all_charts = await _chart_repo.list_unique_by_user(session, user.id)
    candidates: list[tuple[_uuid.UUID, str]] = [
        (c.id, format_chart_label(c)) for c in all_charts if c.id != exclude_chart_id
    ]
    if not candidates:
        return add_partner_chart_kb()
    return partner_chart_selector_kb(candidates)


@consultation_router.callback_query(F.data.startswith("partner:use:"))
async def handle_partner_use_existing(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    history_store: HistoryStore,
) -> None:
    """User picked an existing chart to use as their partner (1.17.11).

    Verifies ownership, calls `ChartRepository.set_partner`, then
    resumes the consultation in the same shape as `partner:skip` but
    with the freshly-linked partner chart loaded into the prompt.
    """
    if not callback.data or not isinstance(callback.message, Message):
        await callback.answer()
        return
    try:
        partner_chart_id = _uuid.UUID(callback.data.split(":", 2)[2])
    except (ValueError, IndexError):
        await callback.answer("Неверная карта", show_alert=True)
        return

    partner_chart = await _chart_repo.get_by_id(session, partner_chart_id)
    if partner_chart is None or partner_chart.user_id != user.id:
        await callback.answer("Карта не найдена", show_alert=True)
        return

    data = await state.get_data()
    original_question = str(data.get("pending_question") or "")
    skill_name = str(data.get("pending_skill") or "relationships")
    concept_hints_raw = data.get("pending_concept_hints") or []
    concept_hints = (
        [str(h) for h in concept_hints_raw] if isinstance(concept_hints_raw, list) else []
    )
    clar_raw = data.get("pending_clarifications") or []
    clarifications = (
        [(str(q), str(a)) for q, a in clar_raw] if isinstance(clar_raw, list) and clar_raw else None
    )
    owner_chart_id_raw = data.get("chart_id")

    if not original_question or not owner_chart_id_raw:
        await callback.message.answer(
            "Не нашла исходный вопрос — задайте его заново через меню.",
            reply_markup=_no_chart_kb(),
        )
        await state.set_state(None)
        await callback.answer()
        return

    try:
        owner_chart_id = _uuid.UUID(str(owner_chart_id_raw))
    except (ValueError, TypeError):
        await callback.answer("Карта не найдена", show_alert=True)
        return

    owner_chart = await _chart_repo.get_by_id(session, owner_chart_id)
    if owner_chart is None or owner_chart.user_id != user.id:
        await callback.answer("Карта не найдена", show_alert=True)
        return
    if owner_chart.id == partner_chart.id:
        await callback.answer("Нельзя выбрать ту же карту партнёром", show_alert=True)
        return

    # ACK callback ASAP — `set_partner` is cheap but the resumed LLM
    # turn that follows runs ~15s; Telegram invalidates queries after
    # a few seconds.
    await callback.answer()

    await _chart_repo.set_partner(
        session, owner_chart_id=owner_chart.id, partner_chart_id=partner_chart.id
    )
    await session.flush()
    # Refresh owner_chart to pick up the new partner_chart_id link.
    owner_chart.partner_chart_id = partner_chart.id
    partner_chart_data = ChartOutput.model_validate(partner_chart.chart_data)

    logger.info(
        "consultation.partner_chart_linked_from_existing",
        owner_chart_id=str(owner_chart.id),
        partner_chart_id=str(partner_chart.id),
        skill=skill_name,
        had_clarifications=bool(clarifications),
    )
    await state.set_state(None)

    chart_data = ChartOutput.model_validate(owner_chart.chart_data)
    skill_spec = _safe_load_skill(skill_name)

    await _continue_consultation_with_skill(
        callback.message,
        chart=owner_chart,
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


def _safe_load_skill(name: str) -> SkillSpec | None:
    """Resolve a SkillName-string into a SkillSpec, falling back to
    ``default`` on file errors. Returns ``None`` only if even ``default``
    won't load (catastrophic — caller treats as legacy flow).

    The whitelist is derived from ``SkillName`` via ``get_args`` so
    adding a new skill (Wave 7 added ``risk``) only requires updating
    the Literal in one place. Previously hardcoded — and Wave 7's
    ``risk`` was silently downgraded to ``default`` (live regression
    found 2026-05-23 during Phase 2+5 verify)."""
    valid = set(get_args(SkillName))
    if name not in valid:
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


async def _load_master_meeting_summaries(
    session: AsyncSession, chart_id: _uuid.UUID, *, limit: int = 3
) -> list[str]:
    """W5e-MVP — fetch the most recent master-meeting summaries for a
    chart so they can be injected into ``[PERSONAL_MASTER_NOTES]``.

    Capped at 3 by default — the LLM context budget can carry that
    without crowding the chart/skill/knowledge blocks. Older notes
    fade out naturally as the user uploads new meetings. Returns an
    empty list when the user hasn't uploaded any meetings.
    """
    from db.repositories.master_meeting_repo import MasterMeetingRepository

    repo = MasterMeetingRepository()
    meetings = await repo.list_ready_summaries(session, chart_id, limit=limit)
    return [m.summary for m in meetings if m.summary]


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


# ── pricing:skip — продолжить бесплатно (пока ЮКасса не подключена) ──────


@consultation_router.callback_query(F.data == "pricing:skip")
async def handle_pricing_skip(
    callback: CallbackQuery,
    session: AsyncSession,
    user: User,
    state: FSMContext,
    history_store: HistoryStore,
) -> None:
    """Сбрасывает счётчик бесплатных вопросов в 0 и продолжает разговор.

    Wave 7 UX rework (2026-05-24): раньше admin-only (testing aid). Теперь
    **доступно всем** — пока ЮКасса не подключена (1.12.3 в backlog),
    это единственный способ продолжить за лимитом 3 бесплатных. При
    подключении оплаты — удалить (или скрыть через ``allow_skip=False``
    в pricing_kb).

    Auto-resume (1.17.12 fix, доработано 2026-05-24): если в FSM был
    pending_free_question — запускаем consultation сразу, не заставляем
    пользователя вводить вопрос заново.
    """
    await _user_repo.reset_free_questions(session, user.id)
    user.free_questions_used = 0
    await callback.answer("Лимит сброшен")
    logger.info(
        "pricing.skip_used",
        user_id=str(user.id),
        telegram_id=user.telegram_id,
        is_admin=(user.telegram_id == get_settings().admin_telegram_id),
    )

    if not isinstance(callback.message, Message):
        return

    # Check if there is a stashed question to replay.
    data = await state.get_data()
    pending_question = (data.get("pending_free_question") or "").strip()

    if not pending_question:
        await callback.message.answer(
            "Лимит сброшен. Нажмите «Задать вопрос» и продолжайте.",
        )
        return

    chart = await _resolve_active_chart(state, session, user)
    if chart is None:
        await callback.message.answer(
            "Лимит сброшен, но карта не найдена. "
            "Откройте карту через меню и задайте вопрос заново.",
            reply_markup=_no_chart_kb(),
        )
        await state.set_state(None)
        return

    # Drop the stash so a future guard hit doesn't replay an old question,
    # and clear the FSM bubble — the pipeline manages its own state.
    await state.update_data(pending_free_question=None)
    await state.set_state(None)
    logger.info(
        "consultation.pricing_skip_resumes_pending",
        user_id=str(user.id),
        question_preview=pending_question[:80],
    )
    await _process_question_after_guards(
        callback.message,
        state=state,
        session=session,
        user=user,
        history_store=history_store,
        question=pending_question,
        chart=chart,
    )


# ── pay:disabled:* — все 3 тарифа пока неактивны ─────────────────────────


@consultation_router.callback_query(F.data.startswith("pay:disabled:"))
async def handle_payment_disabled(callback: CallbackQuery) -> None:
    """Wave 7 UX (2026-05-24): тарифные кнопки в pricing_kb помечены
    «(скоро)» и шлют этот callback. Показываем alert чтобы клиент знал
    что оплата в процессе подключения. При запуске ЮКассы — заменить
    handler'ом активной оплаты + удалить «(скоро)» из labels."""
    await callback.answer(
        "💳 Подключение оплаты в процессе. Пока используйте «Продолжить бесплатно».",
        show_alert=True,
    )


# ── Question handler ─────────────────────────────────────────────────────


async def _voice_to_text(message: Message, bot: Bot) -> str | None:
    """Download a Telegram voice message and transcribe it via
    TeleTranscribe. Returns the transcript text on success, or None
    on download/transcription failure (after telling the user)."""
    if message.voice is None:
        return None
    notice = await message.answer("Расшифровываю голосовое — секунду…")
    try:
        buf = io.BytesIO()
        await bot.download(message.voice.file_id, destination=buf)
        audio_bytes = buf.getvalue()
    except Exception as exc:
        logger.warning("consultation.voice_download_failed", error=str(exc))
        await message.answer(
            "Не получилось скачать голосовое из Telegram. Попробуйте текстом или запишите ещё раз."
        )
        return None
    try:
        transcript = await transcribe_voice(audio_bytes=audio_bytes)
    except TeleTranscribeError as exc:
        logger.warning("consultation.transcribe_failed", error=str(exc))
        await message.answer(
            "Сервис расшифровки сейчас не отвечает. Напишите вопрос текстом — отвечу сразу."
        )
        return None
    # Best-effort tidy: drop the "transcribing..." notice so the chat
    # isn't cluttered. Silently ignored if Telegram refuses.
    with contextlib.suppress(TelegramBadRequest):
        await notice.delete()
    return transcript.strip() or None


@consultation_router.message(ConsultationState.waiting_question, F.voice)
async def handle_voice_question(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    history_store: HistoryStore,
    bot: Bot,
) -> None:
    """Voice equivalent of `handle_question`. Transcribes the audio
    via TeleTranscribe (same service used by the journal voice flow)
    and pipes the transcript through the regular text pipeline so all
    guards (free-question, no-chart) and the skill router still apply.
    """
    transcript = await _voice_to_text(message, bot)
    if transcript is None:
        return

    chart = await _resolve_active_chart(state, session, user)
    if chart is None or message.bot is None:
        await message.answer(
            "Не нашла карту — постройте её через меню и повторите вопрос.",
            reply_markup=_no_chart_kb(),
        )
        await state.set_state(None)
        return

    settings = get_settings()
    remaining = settings.free_questions_limit - user.free_questions_used
    if remaining <= 0:
        await state.update_data(pending_free_question=transcript)
        # Wave 7 UX: allow_skip=True по умолчанию (доступно всем пока
        # ЮКасса не подключена). При запуске оплаты — поменять на
        # ``allow_skip=False`` или удалить параметр совсем.
        await message.answer(
            _free_questions_used_msg(settings.free_questions_limit),
            reply_markup=pricing_kb(),
        )
        logger.info(
            "consultation.blocked_by_free_question_guard",
            user_id=str(user.id),
            telegram_id=user.telegram_id,
            used=user.free_questions_used,
            limit=settings.free_questions_limit,
            source="voice",
        )
        return

    logger.info(
        "consultation.voice_question_accepted",
        user_id=str(user.id),
        transcript_preview=transcript[:80],
    )
    await _process_question_after_guards(
        message,
        state=state,
        session=session,
        user=user,
        history_store=history_store,
        question=transcript,
        chart=chart,
    )


@consultation_router.message(ConsultationState.collecting_clarifications, F.voice)
async def handle_voice_clarification(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    history_store: HistoryStore,
    bot: Bot,
) -> None:
    """Voice answer to a clarifying question. Transcribes via
    TeleTranscribe, sets `message.text` semantics through a delegating
    call into `handle_clarification_answer`. We don't have a clean
    way to mutate `message.text` in-place, so we shape the call by
    using the same state machinery — append the transcript as if the
    user typed it.
    """
    transcript = await _voice_to_text(message, bot)
    if transcript is None:
        return

    # Mirror the storage logic from handle_clarification_answer: append
    # to `answers`, advance or finish. Reusing the existing handler is
    # not practical (it reads `message.text`), so we duplicate the few
    # lines of FSM bookkeeping here and delegate to a small helper.
    logger.info(
        "consultation.voice_clarification_accepted",
        user_id=str(user.id),
        transcript_preview=transcript[:80],
    )
    await _process_clarification_text(
        message,
        state=state,
        session=session,
        user=user,
        history_store=history_store,
        answer=transcript,
    )


@consultation_router.message(ConsultationState.waiting_question, F.text)
async def handle_question(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    history_store: HistoryStore,
) -> None:
    """Entry point for one consultation turn.

    Two routing paths gated by ``settings.skill_router_enabled`` —
    skill-router (default) and legacy. Both share guards (free-question,
    no-chart, slash-command); the actual pipeline runs in
    `_process_question_after_guards` so that pricing-skip can replay
    a stashed question without forcing the user to retype it.
    """
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

    # Free-questions guard (Wave 7 UX rework 2026-05-24, бывш. 1.12.0).
    settings = get_settings()
    remaining = settings.free_questions_limit - user.free_questions_used
    if remaining <= 0:
        # 1.17.12 stash сохраняем: handle_pricing_skip → auto-resume
        # без повторного ввода вопроса.
        await state.update_data(pending_free_question=question)
        await message.answer(
            _free_questions_used_msg(settings.free_questions_limit),
            reply_markup=pricing_kb(),
        )
        # Keep FSM state as `waiting_question` so the pending data
        # survives until handle_pricing_skip clears it.
        logger.info(
            "consultation.blocked_by_free_question_guard",
            user_id=str(user.id),
            telegram_id=user.telegram_id,
            used=user.free_questions_used,
            limit=settings.free_questions_limit,
        )
        return

    await _process_question_after_guards(
        message,
        state=state,
        session=session,
        user=user,
        history_store=history_store,
        question=question,
        chart=chart,
    )


async def _process_question_after_guards(
    message: Message,
    *,
    state: FSMContext,
    session: AsyncSession,
    user: User,
    history_store: HistoryStore,
    question: str,
    chart: Chart,
) -> None:
    """Run the skill-router / continuation pipeline for a single
    question once all up-front guards (chart, free-question,
    slash-command) have already passed.

    Exists as a separate function so `handle_pricing_skip` can replay
    a pending free-question right after resetting the limit, without
    forcing the user to retype it (1.17.12 UX fix 2026-05-21).
    """
    chart_data = ChartOutput.model_validate(chart.chart_data)
    settings = get_settings()

    # Wave 7 Phase 2 — pick up the school chosen by the user before the
    # question (FSM data, set by handle_school_chosen). Threaded through
    # every downstream entry-point into load_base_prompt.
    fsm_data = await state.get_data()
    chosen_school = _parse_school(fsm_data.get("chosen_school"))

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
            chosen_school=chosen_school,
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
            # Preserve partner-chart hint so handle_clarification_answer
            # can offer the partner-chart prompt once all clarifications
            # are collected (1.17.9a regression fix 2026-05-20).
            needs_partner_chart=bool(skill_sel.needs_partner_chart),
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
        partner_kb = await _partner_kb_for_user(session, user=user, exclude_chart_id=chart.id)
        await message.answer(_PARTNER_REQUEST_MSG, reply_markup=partner_kb)
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
        chosen_school=chosen_school,
    )


# ── Public helper: resume after partner chart added (1.17.9b) ────────────


async def resume_after_partner_added(
    message: Message,
    *,
    owner_chart: Chart,
    partner_chart_output: ChartOutput,
    pending_question: str,
    pending_skill: str,
    pending_concept_hints: list[str],
    pending_clarifications: list[tuple[str, str]] | None,
    user: User,
    session: AsyncSession,
    history_store: HistoryStore,
    chosen_school: SchoolName | None = None,
) -> None:
    """Called from `bot.routers.birth_data` right after a partner chart
    is calculated, persisted and linked to the owner chart.

    Picks up the consultation where the original question left off —
    same skill, the freshly-built partner chart injected into the
    `[PARTNER_CHART]` block, and any clarifications carried across
    from the clarifying FSM loop.

    Without this hook the bot would just say «Карта партнёра рассчитана»
    and the user would have to manually re-ask the question. See
    1.17.9b in tasks.md.
    """
    chart_data = ChartOutput.model_validate(owner_chart.chart_data)
    skill_spec = _safe_load_skill(pending_skill)
    partner_id = owner_chart.partner_chart_id
    logger.info(
        "consultation.resumed_after_partner_added",
        skill=pending_skill,
        had_clarifications=bool(pending_clarifications),
        owner_chart_id=str(owner_chart.id),
        partner_chart_id=str(partner_id) if partner_id else None,
    )
    await _continue_consultation_with_skill(
        message,
        chart=owner_chart,
        chart_data=chart_data,
        user=user,
        session=session,
        history_store=history_store,
        original_question=pending_question,
        skill_spec=skill_spec,
        partner_chart=partner_chart_output,
        clarifications=pending_clarifications,
        concept_hints=pending_concept_hints,
        chosen_school=chosen_school,
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
    chosen_school: SchoolName | None = None,
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

    # W5e-MVP (2026-05-21) — pull the most recent master-meeting
    # summaries for this chart and inject them as a high-authority
    # block. Bigger KuzuDB integration (Node-level L8_personal_master
    # + RAG filter by chart_id) is parked as W5e-full in tasks.md;
    # this MVP at least surfaces the notes immediately.
    master_summaries = await _load_master_meeting_summaries(session, chart.id)

    # Phase 3.5 (2026-05-23) — LLM concept extraction. Qwen3.6 fast tier
    # extracts implied Chinese terms (e.g. "ругаюсь с женой" → 夫妻宫 /
    # 六冲) that the deterministic vocab+stem extractors in
    # ai/rag/extract.py would miss. Result is UNION'd with the
    # skill_router's concept_hints — both feed retrieve_nodes' Cypher
    # join. Redis-cached by sha256(question) TTL 24h, ~0.05 ₽
    # amortised on cache hit. Returns [] on any failure → retrieval
    # gracefully falls back to vocab+stem only.
    llm_concepts = await extract_concepts_llm(original_question)
    if llm_concepts:
        existing = set(concept_hints or [])
        # Preserve router hints order (they were chosen with more context);
        # LLM-extracted novelties appended at the end.
        merged: list[str] = list(concept_hints or [])
        for c in llm_concepts:
            if c not in existing:
                merged.append(c)
                existing.add(c)
        concept_hints = merged

    # Wave 7 Phase 2 (ADR-011): when skill-router path is active and the
    # user picked a school, layer base.md + base_<school>.md as system
    # prompt. ``chosen_school=None`` falls back to bare base.md so legacy
    # callers (forecast, base_interpretation) and users who haven't yet
    # selected a school keep the prior behaviour.
    if skill_spec is not None:
        system_prompt = load_base_prompt(school=chosen_school)
    else:
        system_prompt = load_system_prompt()
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
        master_meeting_summaries=master_summaries,
        # Wave 7 Phase 5 — propagate the user's chosen school so RAG
        # only surfaces docs tagged ``universal`` + ``<school>``.
        school=chosen_school,
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
    # Bot ships with parse_mode=HTML globally, but the LLM almost
    # always uses Markdown `**bold**`. Convert to <b>…</b> so users
    # don't see literal asterisks (live regression 2026-05-22).
    text = _markdown_to_html(text)
    # Telegram caps text messages at 4096 chars. Partner-comparison
    # answers with clarifications can break that (~5000+ chars).
    # Split on paragraph boundaries and attach the keyboard only to
    # the LAST chunk so the user has one clear «Ещё вопрос / В меню»
    # control. Without this split the whole turn raises
    # `TelegramBadRequest: message is too long` and the surrounding
    # session_scope rolls back any pending writes (e.g. set_partner).
    chunks = _split_for_telegram(text, _TG_MAX_CHARS)
    for chunk in chunks[:-1]:
        await message.answer(chunk)
    await message.answer(chunks[-1], reply_markup=_after_answer_kb())

    # Wave 7 UX rework (2026-05-24): счётчик вместо bool. Возвращает
    # обновлённое значение — используем для footer «осталось N/3».
    new_used = await _user_repo.increment_free_questions(session, user.id)
    user.free_questions_used = new_used

    # Footer с остатком бесплатных вопросов — только пока ЮКасса не
    # подключена. При активной оплате (settings.payments_enabled и
    # подписка купленa) footer лишний; пока показываем всем без
    # подписки.
    settings = get_settings()
    remaining = max(0, settings.free_questions_limit - new_used)
    if remaining > 0:
        await message.answer(_remaining_footer(remaining, settings.free_questions_limit))

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
