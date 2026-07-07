"""Fast skill-router LLM call (Wave 6, ADR-010).

Two-stage AI flow for consultation handler:

1. ``select_skill(question, chart, history)`` — this module, fast LLM
   call on ``settings.fast_model`` (Gemini Flash via OpenRouter).
   Returns ``SkillSelection`` with skill name, clarifying questions,
   partner-chart hint, and concept hints for RAG.

2. ``chat_with_fallback`` — main LLM call with the selected skill
   body injected into ``[SKILL]`` section of the prompt.

Failure mode: parse / network / 4xx returns ``SkillSelection(skill="default",
confidence=0.0, ...)`` rather than raising, so the consultation
handler always has a routing decision even when the router is broken.

Cost note: router cost is small (output ~150-300 tokens of JSON);
total cost-per-turn overhead is ~5-10% on top of the main answer.
"""

from __future__ import annotations

import json
import re
from typing import Final

import structlog
from pydantic import ValidationError

from ai.orchestrator import ChatMessage, OrchestratorError, chat
from ai.prompts import load_skill_router_prompt
from ai.skills import SkillSelection, list_skills
from bot.config import get_settings
from calculator.models import ChartOutput

logger = structlog.get_logger(__name__)

# Regex to pull JSON out of LLM output that wrapped it in ```json fences
# or added preamble. Greedy match between first '{' and last '}'.
_JSON_FENCE_RE: Final = re.compile(r"\{.*\}", re.DOTALL)

# How many history turns the router sees. The router doesn't need the
# whole history — last 2-3 turns are usually enough to disambiguate
# follow-up questions ("а если..." / "продолжи").
_ROUTER_HISTORY_TAIL: Final = 4


def _render_catalog() -> str:
    """Render the static skill catalog as bullet lines for the router
    system prompt. Cached implicitly via ``list_skills``'s lru_cache."""
    lines = []
    for spec in list_skills():
        lines.append(f"- **{spec.name}**: {spec.description}")
    return "\n".join(lines)


def _brief_chart(chart: ChartOutput) -> str:
    """Compact chart summary (~250 chars) for the router.

    Full ``[BAZI_DATA]`` block is reserved for the main LLM; the
    router only needs the day master + pillars + nearest luck pillar
    to disambiguate questions like «как мне сейчас в работе?».
    """
    pillars = " · ".join(f"{p.stem}{p.branch}" for p in chart.pillars)
    parts = [
        f"Дневной Мастер: {chart.day_master}",
        f"Столпы (Y·M·D·H): {pillars}",
    ]
    if chart.luck_pillars and chart.luck_pillars.pillars:
        lp = chart.luck_pillars.pillars[0]
        parts.append(
            f"Текущий такт: {lp.stem}{lp.branch} "
            f"({lp.start_age:.1f} лет, {lp.start_datetime.year}–{lp.end_datetime.year})"
        )
    return "\n".join(parts)


def _extract_json(text: str) -> str:
    """Pull the first ``{...}`` blob out of LLM output.

    Models sometimes ignore the «no markdown» rule and wrap the JSON
    in ``` ```json ... ``` ``` fences or add a preamble like
    "Конечно, вот ответ:". Greedy regex from first `{` to last `}` is
    enough for our schema (no nested arrays of objects that could
    confuse it). Raises ``ValueError`` if no braces present.
    """
    match = _JSON_FENCE_RE.search(text)
    if match is None:
        raise ValueError("no JSON object found in router output")
    return match.group(0)


def _fallback_selection(reason: str) -> SkillSelection:
    """Graceful fallback when the router fails for any reason —
    parse error, validation error, network, 4xx.

    Returns ``skill="default"`` so the consultation handler can still
    produce an answer using the universal skill. ``confidence=0.0``
    signals downstream that this is a fallback (handler can choose to
    log louder or surface to admin)."""
    return SkillSelection(
        skill="default",
        confidence=0.0,
        clarifying_questions=[],
        needs_partner_chart=False,
        concept_hints=[],
        reason=f"router fallback: {reason}",
    )


async def select_skill(
    *,
    question: str,
    chart: ChartOutput,
    history: list[ChatMessage] | None = None,
    trace_id: str | None = None,
) -> SkillSelection:
    """Run the fast router LLM and return a routing decision.

    Pure async function — no side effects beyond the LLM call and
    structured logging. Always returns a ``SkillSelection``; failures
    are converted into ``skill="default", confidence=0.0`` so the
    caller never needs a try/except around this.
    """
    settings = get_settings()
    catalog = _render_catalog()
    system_prompt = load_skill_router_prompt().format(catalog=catalog)

    chart_brief = _brief_chart(chart)
    user_payload = f"Вопрос клиента:\n{question}\n\nКраткая карта:\n{chart_brief}"

    messages: list[ChatMessage] = [ChatMessage(role="system", content=system_prompt)]
    if history:
        # Pass only the tail — the router doesn't need long context, and
        # short message lists keep the cache prefix small.
        messages.extend(history[-_ROUTER_HISTORY_TAIL:])
    messages.append(ChatMessage(role="user", content=user_payload))

    log = logger.bind(trace_id=trace_id or "skill-router", model=settings.fast_model)

    try:
        result = await chat(
            provider="openrouter",
            model=settings.fast_model,
            messages=messages,
            temperature=0.1,
            max_tokens=settings.fast_max_tokens,
            trace_id=trace_id,
        )
    except OrchestratorError as exc:
        log.warning("skill_router.upstream_error", error=str(exc))
        return _fallback_selection(f"{type(exc).__name__}")

    try:
        json_blob = _extract_json(result.text)
    except ValueError as exc:
        log.warning(
            "skill_router.no_json_in_output", text_preview=result.text[:200], error=str(exc)
        )
        return _fallback_selection("no_json")

    try:
        parsed_dict = json.loads(json_blob)
    except json.JSONDecodeError as exc:
        log.warning("skill_router.json_decode_error", text_preview=json_blob[:200], error=str(exc))
        return _fallback_selection("json_decode_error")

    try:
        selection = SkillSelection.model_validate(parsed_dict)
    except ValidationError as exc:
        log.warning("skill_router.validation_error", error=str(exc))
        return _fallback_selection("validation_error")

    log.info(
        "skill_router.selected",
        skill=selection.skill,
        confidence=selection.confidence,
        clarifying_count=len(selection.clarifying_questions),
        needs_partner_chart=selection.needs_partner_chart,
        concept_hints_count=len(selection.concept_hints),
        latency_ms=result.latency_ms,
        completion_tokens=result.usage.completion_tokens,
    )
    return selection
