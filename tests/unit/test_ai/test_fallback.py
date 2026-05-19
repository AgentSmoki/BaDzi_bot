"""Tests for ai.fallback (2-tier: Yandex Qwen3.6 → OpenRouter Claude).

Mocks ``ai.orchestrator.chat`` so no real LLM call leaves the process.
Each test sets up a handler that decides per-provider what to return,
then asserts the right tier answered (or that an error was re-raised).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import pytest

from ai.fallback import chat_with_fallback
from ai.orchestrator import (
    ChatMessage,
    ChatResult,
    ChatUsage,
    OrchestratorError,
    Provider,
    RateLimitError,
    UpstreamError,
)


def _result(model: str, provider: Provider, text: str = "ok") -> ChatResult:
    return ChatResult(
        text=text,
        model=model,
        usage=ChatUsage(),
        latency_ms=10,
        trace_id="t1",
        provider=provider,
    )


def _patch_chat(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[..., Awaitable[ChatResult]],
) -> list[dict[str, Any]]:
    """Replace ``ai.fallback.chat`` with ``handler`` and return a list
    that accumulates kwargs of every call so tests can introspect."""
    calls: list[dict[str, Any]] = []

    async def stub(**kwargs: Any) -> ChatResult:
        calls.append(kwargs)
        return await handler(**kwargs)

    monkeypatch.setattr("ai.fallback.chat", stub)
    return calls


# ── happy path ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_tier_1_success_skips_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    async def primary_ok(**kwargs: Any) -> ChatResult:
        return _result(kwargs["model"], kwargs["provider"], "primary spoke")

    calls = _patch_chat(monkeypatch, primary_ok)
    out = await chat_with_fallback(
        messages=[ChatMessage(role="user", content="hi")],
        temperature=0.5,
        intent="normal",
    )
    assert out.tier == 1
    assert out.provider == "yc"
    assert out.used_fallback is False
    assert out.result.model.startswith("gpt://")
    assert len(calls) == 1


# ── tier 2 (OpenRouter) takes over on 429 / 5xx ──────────────────────


@pytest.mark.asyncio
async def test_tier_2_used_on_yc_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    async def handler(**kwargs: Any) -> ChatResult:
        if kwargs["provider"] == "yc":
            raise RateLimitError("yc 429")
        return _result(kwargs["model"], "openrouter", "claude spoke")

    calls = _patch_chat(monkeypatch, handler)
    out = await chat_with_fallback(
        messages=[ChatMessage(role="user", content="hi")],
        temperature=0.5,
        intent="normal",
    )
    assert out.tier == 2
    assert out.provider == "openrouter"
    assert out.used_fallback is True
    assert len(calls) == 2
    assert calls[0]["provider"] == "yc"
    assert calls[1]["provider"] == "openrouter"


@pytest.mark.asyncio
async def test_tier_2_used_on_yc_upstream_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    async def handler(**kwargs: Any) -> ChatResult:
        if kwargs["provider"] == "yc":
            raise UpstreamError("yc 503")
        return _result(kwargs["model"], "openrouter")

    _patch_chat(monkeypatch, handler)
    out = await chat_with_fallback(
        messages=[ChatMessage(role="user", content="hi")],
        temperature=0.5,
        intent="normal",
    )
    assert out.tier == 2
    assert out.provider == "openrouter"


# ── neither tier answers ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_both_tiers_fail_reraises_last(monkeypatch: pytest.MonkeyPatch) -> None:
    async def handler(**kwargs: Any) -> ChatResult:
        if kwargs["provider"] == "yc":
            raise RateLimitError("yc down")
        raise UpstreamError("openrouter also down")

    _patch_chat(monkeypatch, handler)
    with pytest.raises(UpstreamError) as exc:
        await chat_with_fallback(
            messages=[ChatMessage(role="user", content="hi")],
            temperature=0.5,
            intent="normal",
        )
    assert "openrouter also down" in str(exc.value)


# ── 4xx-other on tier 1 must NOT fall through to tier 2 ──────────────


@pytest.mark.asyncio
async def test_orchestrator_error_does_not_trigger_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bad model id / missing key = our bug, raise without burning
    Claude budget on the same broken request."""

    async def handler(**kwargs: Any) -> ChatResult:
        if kwargs["provider"] == "yc":
            raise OrchestratorError("yc 400: bad model id")
        # If this ever runs, fallback misbehaved
        return _result("should-not-run", "openrouter")

    calls = _patch_chat(monkeypatch, handler)
    with pytest.raises(OrchestratorError):
        await chat_with_fallback(
            messages=[ChatMessage(role="user", content="hi")],
            temperature=0.5,
            intent="normal",
        )
    # Only Tier 1 was called — Tier 2 was correctly skipped.
    assert len(calls) == 1
    assert calls[0]["provider"] == "yc"


# ── dynamic max_tokens per tier ──────────────────────────────────────


@pytest.mark.asyncio
async def test_dynamic_max_tokens_smaller_for_claude_tier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Same intent on Tier 1 (Qwen 262k ctx) vs Tier 2 (Claude 200k
    ctx) → smaller max_tokens on Tier 2 because its context window
    is smaller. ai.budget.compute_max_tokens scales linearly with
    ctx, so 200/262 ≈ 76% of the Tier 1 budget."""

    async def handler(**kwargs: Any) -> ChatResult:
        if kwargs["provider"] == "yc":
            raise RateLimitError("force fallback")
        return _result(kwargs["model"], "openrouter")

    calls = _patch_chat(monkeypatch, handler)
    await chat_with_fallback(
        messages=[ChatMessage(role="user", content="hi")],
        temperature=0.5,
        intent="complex",
        ceiling=100_000,
    )
    qwen_tokens = calls[0]["max_tokens"]
    claude_tokens = calls[1]["max_tokens"]
    # Both should be large (small input, complex intent), but Qwen wins
    # because its context window is larger.
    assert qwen_tokens > claude_tokens
    # Sanity: ratio close to ctx_window ratio (262k vs 200k ≈ 1.31)
    assert 1.2 <= qwen_tokens / claude_tokens <= 1.4


@pytest.mark.asyncio
async def test_model_id_assembled_per_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tier 1 (yc) must get a ``gpt://<folder>/<model>/latest`` URI;
    Tier 2 (openrouter) gets the short name as-is."""
    seen_models: list[str] = []

    async def handler(**kwargs: Any) -> ChatResult:
        seen_models.append(kwargs["model"])
        if kwargs["provider"] == "yc":
            raise RateLimitError("force fallback")
        return _result(kwargs["model"], "openrouter")

    _patch_chat(monkeypatch, handler)
    await chat_with_fallback(
        messages=[ChatMessage(role="user", content="hi")],
        temperature=0.5,
        intent="normal",
    )
    assert seen_models[0].startswith("gpt://")
    assert "/qwen3.6-35b-a3b/" in seen_models[0]
    # OpenRouter accepts the short name without prefix
    assert seen_models[1] == "anthropic/claude-3.5-sonnet"
