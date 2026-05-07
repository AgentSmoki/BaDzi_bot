"""Kimi → Claude fallback chain.

`chat_with_fallback` runs the orchestrator against the configured
primary model and, on transient failures, retries once against the
fallback model. The router (1.8.3) decides *what* to ask; this module
just decides *which model handles it* under failure.

Why retry only on rate-limit/upstream-5xx and not on other 4xx:
- 4xx = our request was wrong (bad model id, missing key, malformed
  prompt). Retrying with a different model just hides the bug.
- 429 = OpenRouter quota for the primary upstream provider only;
  switching to Claude reaches a different provider and usually
  succeeds.
- 5xx / network = upstream had an issue; second model is a different
  upstream with its own uptime.

Returns a ``FallbackResult`` so callers can record which model
actually answered (telemetry, billing, /admin debug).
"""

from __future__ import annotations

from dataclasses import dataclass

import structlog

from ai.orchestrator import (
    ChatMessage,
    ChatResult,
    OrchestratorError,
    RateLimitError,
    UpstreamError,
    chat,
)
from bot.config import get_settings

logger = structlog.get_logger(__name__)


@dataclass(frozen=True)
class FallbackResult:
    """Wraps the chosen ChatResult with a flag noting whether the
    answer came from the primary or the fallback model — handy for
    metrics and the /admin model-status endpoint."""

    result: ChatResult
    used_fallback: bool


async def chat_with_fallback(
    *,
    messages: list[ChatMessage],
    temperature: float,
    max_tokens: int,
    primary_model: str | None = None,
    fallback_model: str | None = None,
    trace_id: str | None = None,
) -> FallbackResult:
    """Try ``primary_model`` first; on RateLimit/Upstream errors,
    retry with ``fallback_model`` once. Both default to the values
    in ``Settings`` (``moonshotai/kimi-k2.6`` and
    ``anthropic/claude-3.5-sonnet`` out of the box)."""
    settings = get_settings()
    primary = primary_model or settings.default_llm_model
    fallback = fallback_model or settings.fallback_llm_model

    try:
        result = await chat(
            model=primary,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
            trace_id=trace_id,
        )
        return FallbackResult(result=result, used_fallback=False)
    except (RateLimitError, UpstreamError) as primary_exc:
        logger.warning(
            "fallback.switching_models",
            primary=primary,
            fallback=fallback,
            error_class=type(primary_exc).__name__,
            error=str(primary_exc)[:200],
            trace_id=trace_id,
        )
        try:
            result = await chat(
                model=fallback,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                trace_id=trace_id,
            )
        except OrchestratorError as fb_exc:
            # Both models failed — re-raise the *fallback* error so
            # the caller has the most recent context. Primary error
            # is in the log above for forensics.
            logger.error(
                "fallback.both_failed",
                primary_error=str(primary_exc)[:200],
                fallback_error=str(fb_exc)[:200],
                trace_id=trace_id,
            )
            raise
        return FallbackResult(result=result, used_fallback=True)
