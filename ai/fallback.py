"""2-tier fallback через OpenRouter: Qwen3.7-Plus → Gemini 2.5 Pro (ADR-012).

``chat_with_fallback`` runs the request against Tier 1 (Qwen3.7-Plus)
and, on transient failures, retries once against Tier 2 (Gemini 2.5
Pro). Оба тира идут через OpenRouter, но это *разные семьи моделей*
(Qwen vs Gemini) — сбой одной модели/апстрима не кладёт обе ступени;
OpenRouter сам роутит между нижележащими провайдерами.

Per-tier ``max_tokens`` is recomputed via ``ai.budget.compute_max_tokens``
because the two models have different context windows. The same intent
ratio yields a different absolute output cap depending on which tier
answers.

Why retry only on RateLimit (429) and Upstream (5xx/timeout/empty)
and not on other 4xx:
- 4xx-other = our request is wrong (bad model id, missing key, malformed
  prompt). Retrying on the next tier just hides the bug. Raise instead.
- 429 = quota on the current provider, unrelated to the next one.
- 5xx / network = upstream had an issue; next provider is independent.

The returned ``FallbackResult`` carries ``tier`` (1 or 2) and
``provider`` (yc/openrouter) so consumers (consultation router,
Langfuse telemetry, /admin debug) can record which infrastructure
actually answered.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

import structlog

from ai.budget import IntentClass, compute_max_tokens
from ai.orchestrator import (
    ChatMessage,
    ChatResult,
    OrchestratorError,
    Provider,
    RateLimitError,
    UpstreamError,
    chat,
)
from bot.config import get_settings

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class FallbackResult:
    """Wraps the chosen ChatResult with tier/provider so callers can
    record which infrastructure actually answered (telemetry, billing,
    /admin model-status endpoint)."""

    result: ChatResult
    tier: int
    provider: Provider
    used_fallback: bool

    @property
    def model(self) -> str:
        """Convenience accessor — same as ``result.model``."""
        return self.result.model


@dataclass(frozen=True)
class _TierConfig:
    """Static config for one tier in the fallback chain. Resolved once
    per call from ``Settings``; cheap to recompute (no I/O)."""

    tier: int
    provider: Provider
    model_short: str
    context_window: int


def _resolve_tiers() -> list[_TierConfig]:
    s = get_settings()
    return [
        _TierConfig(
            tier=1,
            provider="openrouter",
            model_short=s.primary_model,
            context_window=s.primary_context,
        ),
        _TierConfig(
            tier=2,
            provider="openrouter",
            model_short=s.emergency_model,
            context_window=s.emergency_context,
        ),
    ]


# Below this floor a tier is skipped (input too big for context).
# 500 tokens = roughly two short paragraphs — anything smaller and
# the answer would be useless anyway, so we cut over to the next tier
# (which may have a larger context window).
_MIN_USEFUL_BUDGET: Final[int] = 500


async def chat_with_fallback(
    *,
    messages: list[ChatMessage],
    temperature: float,
    intent: IntentClass = "normal",
    trace_id: str | None = None,
    ceiling: int | None = None,
) -> FallbackResult:
    """Try Tier 1 (Qwen3.7-Plus) → Tier 2 (Gemini 2.5 Pro) on OpenRouter
    with dynamic per-tier ``max_tokens``.

    Args:
        messages: prompt for the model.
        temperature: sampling temperature, passed through verbatim.
        intent: routing class (simple/normal/complex/interpretation),
            sizes ``max_tokens`` via ``ai.budget``.
        trace_id: optional trace id; auto-generated if missing.
        ceiling: hard cap on ``max_tokens`` regardless of context
            window. Defaults to ``Settings.max_output_tokens_ceiling``.

    Raises:
        OrchestratorError: 4xx other than 429 on Tier 1 (bug in our
            request, not a fallback candidate).
        RateLimitError/UpstreamError: both tiers failed — the last
            tier's exception is re-raised; the earlier failure is
            in the structured log.
    """
    settings = get_settings()
    effective_ceiling = ceiling or settings.max_output_tokens_ceiling
    last_exc: OrchestratorError | None = None

    for cfg in _resolve_tiers():
        max_tok = compute_max_tokens(
            messages=messages,
            model_context_window=cfg.context_window,
            intent=intent,
            ceiling=effective_ceiling,
        )
        if max_tok < _MIN_USEFUL_BUDGET:
            logger.warning(
                "fallback.budget_too_low_for_tier",
                tier=cfg.tier,
                provider=cfg.provider,
                model=cfg.model_short,
                max_tokens=max_tok,
                trace_id=trace_id,
            )
            continue
        try:
            result = await chat(
                provider=cfg.provider,
                model=cfg.model_short,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tok,
                trace_id=trace_id,
            )
            return FallbackResult(
                result=result,
                tier=cfg.tier,
                provider=cfg.provider,
                used_fallback=cfg.tier > 1,
            )
        except (RateLimitError, UpstreamError) as exc:
            last_exc = exc
            logger.warning(
                "fallback.tier_failed",
                tier=cfg.tier,
                provider=cfg.provider,
                model=cfg.model_short,
                error_class=type(exc).__name__,
                error=str(exc)[:200],
                trace_id=trace_id,
            )
            continue
        except OrchestratorError:
            # 4xx-other = our bug. Don't waste the next tier on it —
            # raise so the consultation handler can log and message
            # the user.
            raise

    logger.error("fallback.all_tiers_failed", trace_id=trace_id)
    if last_exc is None:
        # Every tier was skipped via budget_too_low — input larger
        # than the biggest context window we have.
        raise UpstreamError("input exceeds context windows of all configured tiers")
    raise last_exc
