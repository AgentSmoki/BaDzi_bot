"""Async consultation task — runs an LLM consultation in the worker.

Invoked from ``bot/routers/consultation.py`` when the LLM round-trip
is too slow to keep the aiogram handler alive (≥30s). The task:

1. Composes the LLM payload from the user's chart + question +
   history (same compose_messages pipeline as the in-handler flow).
2. Calls ``chat_with_fallback`` against Kimi K2.6 → Claude.
3. Persists ``Consultation`` and pushes the user's history forward.
4. Sends the final answer to the user via the bot's send_message —
   so the user gets a fresh message instead of a stale reply.

The bot only `kiq()`s the task; the worker does all the LLM work.
This means a TaskIQ worker process needs the same DB / Redis / bot
session bootstrapping as the main bot process, which is wired in
``tasks/__init__.py``.
"""

from __future__ import annotations

import uuid as _uuid
from decimal import Decimal

import structlog
from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from ai.context import HistoryStore
from ai.fallback import chat_with_fallback
from ai.orchestrator import ChatMessage, OrchestratorError
from ai.prompts import load_system_prompt
from ai.router import route
from ai.temporal_context import compose_messages, get_current_bazi
from bot.config import get_settings
from calculator.models import ChartOutput
from db.engine import session_scope
from db.repositories.chart_repo import ChartRepository
from db.repositories.consultation_repo import ConsultationRepository
from tasks.broker import broker

logger = structlog.get_logger(__name__)

_chart_repo = ChartRepository()
_consultation_repo = ConsultationRepository()


@broker.task
async def run_consultation(
    *,
    user_id: str,
    telegram_chat_id: int,
    telegram_user_id: int,
    chart_id: str,
    question: str,
) -> str:
    """Run one consultation turn end-to-end inside the worker.

    Returns the assistant's text on success. On LLM failure sends a
    Russian apology to the chat and returns an empty string — the
    caller (bot handler) can use a non-empty result to know the
    answer landed.
    """
    settings = get_settings()
    bot = Bot(
        token=settings.bot_token.get_secret_value(),
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    history_store = HistoryStore.from_settings()

    try:
        async with session_scope() as session:
            chart = await _chart_repo.get_by_id(session, _uuid.UUID(chart_id))
            if chart is None:
                logger.warning("consultation.task.chart_missing", chart_id=chart_id)
                await bot.send_message(
                    telegram_chat_id,
                    "Не нашла карту — постройте её через меню и повторите вопрос.",
                )
                return ""

            chart_data = ChartOutput.model_validate(chart.chart_data)
            decision = route(question)
            history = await history_store.get(telegram_user_id)
            now_chart = get_current_bazi() if decision.needs_temporal_context else None
            messages = compose_messages(
                system_prompt=load_system_prompt(),
                chart=chart_data,
                question=question,
                history=history,
                include_temporal=decision.needs_temporal_context,
                now_chart=now_chart,
            )

            try:
                # Wave 6: RouteDecision no longer carries max_tokens —
                # chat_with_fallback sizes the budget per-tier via
                # `intent`. Pass the intent from the routing decision.
                answer = await chat_with_fallback(
                    messages=messages,
                    temperature=decision.temperature,
                    intent=decision.intent,
                )
            except OrchestratorError:
                logger.exception("consultation.task.llm_failed")
                await bot.send_message(
                    telegram_chat_id,
                    "Анастасия не смогла ответить — попробуйте задать вопрос ещё раз.",
                )
                return ""

            text = answer.result.text.strip()
            await bot.send_message(telegram_chat_id, text)

            await history_store.append(telegram_user_id, ChatMessage(role="user", content=question))
            await history_store.append(
                telegram_user_id, ChatMessage(role="assistant", content=text)
            )
            await _consultation_repo.create(
                session,
                user_id=_uuid.UUID(user_id),
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
                "consultation.task.completed",
                intent=decision.intent,
                used_fallback=answer.used_fallback,
                latency_ms=answer.result.latency_ms,
                trace_id=answer.result.trace_id,
            )
            return text
    finally:
        await history_store.aclose()
        await bot.session.close()
