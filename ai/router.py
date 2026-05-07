"""Lightweight semantic router for incoming user questions.

Decides three things up front, before the LLM call leaves our process:
1. **Intent class** — simple, normal, or complex. Keeps trivial questions
   from spending big-model latency, and lets the temporal context (1.8.6)
   skip the time-aware lookup when the user is asking about personality.
2. **Model hint** — non-thinking K2-0905 by default; thinking K2.6 only
   for explicitly complex questions (and even then via 1.13's opt-in,
   not blanket).
3. **Generation knobs** — temperature + max_tokens tuned per class so
   the orchestrator (1.8.1) doesn't have to know about persona policy.

This is a deliberately simple rule-based classifier. A learned router
is overkill for an MVP and harder to debug; the rules below cover ~95%
of the FAQ patterns we see in [doc/product_idea.md](../doc/product_idea.md).
Refine as we collect real Consultations from production.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, Literal

from bot.config import get_settings

IntentClass = Literal["simple", "normal", "complex"]


# ── Lexicon ────────────────────────────────────────────────────────────────
#
# Lower-case Russian keywords. Patterns use word boundaries (\b) so we
# don't false-match "годом" when looking for "год", and they're applied
# to the user's text after .lower() and Russian "ё" → "е" normalisation.

_TEMPORAL_KEYWORDS: Final = (
    "сейчас",
    "когда",
    "будущ",
    "прошл",
    "год",
    "месяц",
    "период",
    "ближайш",
    "предстоящ",
    "следующ",
    "текущ",
    "сегодня",
    "завтра",
    "лет назад",
    "в этом году",
    "в следующем году",
)

_COMPLEX_KEYWORDS: Final = (
    # Multi-step reasoning, contradictions, planning
    "почему",
    "противореч",
    "одновременно",
    "конфликт",
    "сравни",
    "несмотря",
    "при этом",
    "однако",
    "если",
    "что если",
    # Career / relationship deep-dive — usually triggers comparison logic
    "работ",
    "карьер",
    "профессия",
    "отношения",
    "брак",
    "партнёр",
    "развод",
    "ребёно",
    "дет",
    "здоров",
    "болезн",
    # Multi-pillar interaction questions
    "столкнов",
    "взаимодейств",
    "наказа",
    "вред",
    "комбинац",
)

_SIMPLE_KEYWORDS: Final = (
    "что такое",
    "что значит",
    "кто я",
    "какой у меня",
    "где",
    "сколько",
    "помощь",
    "помоги мне понять",
)


def _normalise(text: str) -> str:
    """Cyrillic-aware lowercasing for keyword matching. Replaces ё with е
    so the keyword list doesn't have to enumerate both forms."""
    return text.lower().replace("ё", "е").strip()


def _has_any(text: str, keywords: tuple[str, ...]) -> bool:
    """Match each keyword at a word boundary (start of word), so
    inflected forms still hit (`дет` → `дети`, `детей`) but stems
    don't false-match inside unrelated words (`дет` should NOT match
    `ждет`). Multi-word keywords with internal spaces match as-is."""
    for kw in keywords:
        if " " in kw:
            if kw in text:
                return True
            continue
        if re.search(rf"\b{re.escape(kw)}", text):
            return True
    return False


def _temporal_in(text: str) -> bool:
    return _has_any(text, _TEMPORAL_KEYWORDS)


# ── Decision ───────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class RouteDecision:
    """All policy choices for one user turn.

    The orchestrator (1.8.1) reads `model`, `temperature`, `max_tokens`.
    The temporal context builder (1.8.6) reads `needs_temporal_context`
    so it can skip the *current* Bazi lookup when the question is purely
    about personality.
    """

    intent: IntentClass
    model: str
    temperature: float
    max_tokens: int
    needs_temporal_context: bool
    reason: str  # Human-readable explanation, useful in /admin debugging


def route(text: str) -> RouteDecision:
    """Classify a single user message and return a routing decision.

    Pure function — no side effects, no external state apart from
    settings (for default model id). Safe to call from any layer.
    """
    settings = get_settings()
    raw = text or ""
    norm = _normalise(raw)
    word_count = len(re.findall(r"\b\w+\b", norm))
    has_temporal = _temporal_in(norm)
    has_complex = _has_any(norm, _COMPLEX_KEYWORDS)
    has_simple = _has_any(norm, _SIMPLE_KEYWORDS)

    # ── Decision tree ─────────────────────────────────────────────
    # Priority order: complex > temporal > simple > normal.
    # Complex wins because a question can be both temporal and complex
    # (e.g. "почему карьера в этом году не идёт") — we want the
    # heavier model with temporal context attached.
    # Token budgets sized for K2.6 thinking with the full Anastasia
    # system prompt (~39k chars / ~12k tokens). A real run with
    # max_tokens=4000 truncated on reasoning at 4 minutes of latency,
    # so floors must be much higher: simple ≥4000, normal ≥8000,
    # complex ≥12000. settings.max_output_tokens=8192 is the cap on
    # any single intent except complex.
    cap = settings.max_output_tokens
    if has_complex:
        return RouteDecision(
            intent="complex",
            model=settings.default_llm_model,
            temperature=0.55,
            max_tokens=max(cap, 12000),
            needs_temporal_context=has_temporal,
            reason="complex keyword match",
        )
    if has_temporal:
        return RouteDecision(
            intent="normal",
            model=settings.default_llm_model,
            temperature=0.6,
            max_tokens=cap,
            needs_temporal_context=True,
            reason="temporal keyword match",
        )
    if has_simple and word_count <= 12:
        return RouteDecision(
            intent="simple",
            model=settings.default_llm_model,
            temperature=0.45,
            max_tokens=min(cap, 4000),
            needs_temporal_context=False,
            reason="short factual question",
        )
    return RouteDecision(
        intent="normal",
        model=settings.default_llm_model,
        temperature=0.6,
        max_tokens=cap,
        needs_temporal_context=False,
        reason="default conversational",
    )
