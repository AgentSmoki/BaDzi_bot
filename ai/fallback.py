"""2-tier fallback chain: Yandex AI Studio (Qwen3.6) → OpenRouter Claude (ADR-009).

``chat_with_fallback`` runs the request against Tier 1 (Qwen3.6-35B-A3B
on Yandex AI Studio) and, on transient failures, retries once against
Tier 2 (Claude 3.5 Sonnet via OpenRouter). The two tiers live on
*independent clouds* — different infrastructure, different auth,
different upstream chain — so a Yandex regional incident or folder
quota lockout doesn't take Claude down with it.

Per-tier ``max_tokens`` is recomputed via ``ai.budget.compute_max_tokens``
because the two models have different context windows (Qwen3.6 native
262k vs Claude 3.5 Sonnet 200k). The same intent ratio yields a
different absolute output cap depending on which tier answers.

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
            provider="yc",
            model_short=s.yc_primary_model,
            context_window=s.yc_qwen36_context,
        ),
        _TierConfig(
            tier=2,
            provider="openrouter",
            model_short=s.openrouter_emergency_model,
            context_window=s.openrouter_claude_context,
        ),
    ]


def _build_model_id(cfg: _TierConfig, folder_id: str) -> str:
    """YC needs the full ``gpt://<folder>/<short>/latest`` URI;
    OpenRouter accepts the short name as-is."""
    if cfg.provider == "yc":
        return f"gpt://{folder_id}/{cfg.model_short}/latest"
    return cfg.model_short


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
    """Try Tier 1 (YC Qwen3.6) → Tier 2 (OpenRouter Claude) with
    dynamic per-tier ``max_tokens``.

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
                model=_build_model_id(cfg, settings.yc_ai_folder_id),
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
