"""Tests for ai.fallback (2-tier OpenRouter: Qwen3.7-Plus → Gemini 2.5 Pro).

Mocks ``ai.orchestrator.chat`` so no real LLM call leaves the process.
Both tiers go through OpenRouter, so tiers are distinguished by *model*
(``settings.primary_model`` vs ``settings.emergency_model``) rather than
by provider. Each test sets up a handler that decides per-model what to
return, then asserts the right tier answered.
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
from bot.config import get_settings

_PRIMARY = get_settings().primary_model
_EMERGENCY = get_settings().emergency_model


def _result(model: str, provider: Provider = "openrouter", text: str = "ok") -> ChatResult:
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
    assert out.provider == "openrouter"
    assert out.used_fallback is False
    assert out.result.model == _PRIMARY
    assert len(calls) == 1


# ── tier 2 takes over on 429 / 5xx ───────────────────────────────────


@pytest.mark.asyncio
async def test_tier_2_used_on_rate_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    async def handler(**kwargs: Any) -> ChatResult:
        if kwargs["model"] == _PRIMARY:
            raise RateLimitError("primary 429")
        return _result(kwargs["model"], "openrouter", "emergency spoke")

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
    assert calls[0]["model"] == _PRIMARY
    assert calls[1]["model"] == _EMERGENCY


@pytest.mark.asyncio
async def test_tier_2_used_on_upstream_5xx(monkeypatch: pytest.MonkeyPatch) -> None:
    async def handler(**kwargs: Any) -> ChatResult:
        if kwargs["model"] == _PRIMARY:
            raise UpstreamError("primary 503")
        return _result(kwargs["model"], "openrouter")

    _patch_chat(monkeypatch, handler)
    out = await chat_with_fallback(
        messages=[ChatMessage(role="user", content="hi")],
        temperature=0.5,
        intent="normal",
    )
    assert out.tier == 2
    assert out.result.model == _EMERGENCY


# ── neither tier answers ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_both_tiers_fail_reraises_last(monkeypatch: pytest.MonkeyPatch) -> None:
    async def handler(**kwargs: Any) -> ChatResult:
        if kwargs["model"] == _PRIMARY:
            raise RateLimitError("primary down")
        raise UpstreamError("emergency also down")

    _patch_chat(monkeypatch, handler)
    with pytest.raises(UpstreamError) as exc:
        await chat_with_fallback(
            messages=[ChatMessage(role="user", content="hi")],
            temperature=0.5,
            intent="normal",
        )
    assert "emergency also down" in str(exc.value)


# ── 4xx-other on tier 1 must NOT fall through to tier 2 ──────────────


@pytest.mark.asyncio
async def test_orchestrator_error_does_not_trigger_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Bad model id / missing key = our bug, raise without burning the
    emergency tier on the same broken request."""

    async def handler(**kwargs: Any) -> ChatResult:
        if kwargs["model"] == _PRIMARY:
            raise OrchestratorError("400: bad model id")
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
    assert calls[0]["model"] == _PRIMARY


# ── max_tokens per tier ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_dynamic_max_tokens_equal_when_context_equal(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Both tiers (Qwen3.7-Plus and Gemini 2.5 Pro) have a 1M context
    window, so the same intent yields the same ``max_tokens`` budget on
    each tier. ai.budget.compute_max_tokens scales with ctx, so equal
    ctx → equal budget."""

    async def handler(**kwargs: Any) -> ChatResult:
        if kwargs["model"] == _PRIMARY:
            raise RateLimitError("force fallback")
        return _result(kwargs["model"], "openrouter")

    calls = _patch_chat(monkeypatch, handler)
    await chat_with_fallback(
        messages=[ChatMessage(role="user", content="hi")],
        temperature=0.5,
        intent="complex",
        ceiling=100_000,
    )
    assert calls[0]["max_tokens"] == calls[1]["max_tokens"]


@pytest.mark.asyncio
async def test_model_passed_through_per_tier(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Tier 1 gets ``settings.primary_model``; Tier 2 gets
    ``settings.emergency_model`` — short OpenRouter slugs, no URI."""
    seen_models: list[str] = []

    async def handler(**kwargs: Any) -> ChatResult:
        seen_models.append(kwargs["model"])
        if kwargs["model"] == _PRIMARY:
            raise RateLimitError("force fallback")
        return _result(kwargs["model"], "openrouter")

    _patch_chat(monkeypatch, handler)
    await chat_with_fallback(
        messages=[ChatMessage(role="user", content="hi")],
        temperature=0.5,
        intent="normal",
    )
    assert seen_models[0] == _PRIMARY
    assert seen_models[1] == _EMERGENCY
    assert not seen_models[0].startswith("gpt://")
