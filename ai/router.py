"""Lightweight semantic router for incoming user questions (ADR-009).

Decides two things up front, before the LLM call leaves our process:
1. **Intent class** — simple, normal, or complex. Used by ``ai.budget``
   to size ``max_tokens`` proportionally to the model's context window
   (different per tier — Qwen3.6 native 262k vs Claude 200k).
2. **Generation knobs** — temperature + temporal-context flag.

Model selection lives in ``ai.fallback`` now (tier 1/2 chain), not
here. The router classifies the question's *shape*; the fallback
layer picks which infrastructure answers.

This is a deliberately simple rule-based classifier. A learned router
is overkill for an MVP and harder to debug; the rules below cover ~95%
of the FAQ patterns we see in [doc/product_idea.md](../doc/product_idea.md).
Refine as we collect real Consultations from production.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

from ai.budget import IntentClass

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
    """Policy choices for one user turn.

    ``intent`` feeds into ``ai.budget.compute_max_tokens`` which sizes
    the output cap proportionally to the chosen tier's context window.
    ``needs_temporal_context`` toggles the *current* Bazi block append
    in ``ai.temporal_context.compose_messages``.
    """

    intent: IntentClass
    temperature: float
    needs_temporal_context: bool
    reason: str  # Human-readable explanation, useful in /admin debugging


def route(text: str) -> RouteDecision:
    """Classify a single user message and return a routing decision.

    Pure function — no side effects, no external state. Safe to call
    from any layer.
    """
    raw = text or ""
    norm = _normalise(raw)
    word_count = len(re.findall(r"\b\w+\b", norm))
    has_temporal = _temporal_in(norm)
    has_complex = _has_any(norm, _COMPLEX_KEYWORDS)
    has_simple = _has_any(norm, _SIMPLE_KEYWORDS)

    # ── Decision tree ─────────────────────────────────────────────
    # Priority order: complex > temporal > simple > normal.
    # Complex wins because a question can be both temporal and complex
    # (e.g. "почему карьера в этом году не идёт") — we want the deeper
    # output budget plus temporal context attached.
    if has_complex:
        return RouteDecision(
            intent="complex",
            temperature=0.55,
            needs_temporal_context=has_temporal,
            reason="complex keyword match",
        )
    if has_temporal:
        return RouteDecision(
            intent="normal",
            temperature=0.6,
            needs_temporal_context=True,
            reason="temporal keyword match",
        )
    if has_simple and word_count <= 12:
        return RouteDecision(
            intent="simple",
            temperature=0.45,
            needs_temporal_context=False,
            reason="short factual question",
        )
    return RouteDecision(
        intent="normal",
        temperature=0.6,
        needs_temporal_context=False,
        reason="default conversational",
    )
