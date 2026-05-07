"""Tests for ai.fallback. Mocks ai.orchestrator.chat so no live calls."""

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
    RateLimitError,
    UpstreamError,
)


def _result(model: str, text: str = "ok") -> ChatResult:
    return ChatResult(text=text, model=model, usage=ChatUsage(), latency_ms=10, trace_id="t1")


def _patch_chat(
    monkeypatch: pytest.MonkeyPatch,
    handler: Callable[..., Awaitable[ChatResult]],
) -> list[dict[str, Any]]:
    """Replace ai.fallback.chat with `handler` and return a list that
    accumulates the kwargs of every call so tests can introspect."""
    calls: list[dict[str, Any]] = []

    async def stub(**kwargs: Any) -> ChatResult:
        calls.append(kwargs)
        return await handler(**kwargs)

    monkeypatch.setattr("ai.fallback.chat", stub)
    return calls


@pytest.mark.asyncio
async def test_primary_success_skips_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    async def primary_ok(**kwargs: Any) -> ChatResult:
        return _result(kwargs["model"], "primary spoke")

    calls = _patch_chat(monkeypatch, primary_ok)
    out = await chat_with_fallback(
        messages=[ChatMessage(role="user", content="hi")],
        temperature=0.5,
        max_tokens=500,
        primary_model="moonshotai/kimi-k2.6",
        fallback_model="anthropic/claude-3.5-sonnet",
    )
    assert out.used_fallback is False
    assert out.result.model == "moonshotai/kimi-k2.6"
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_rate_limit_triggers_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    async def handler(**kwargs: Any) -> ChatResult:
        if kwargs["model"] == "moonshotai/kimi-k2.6":
            raise RateLimitError("429 from primary")
        return _result(kwargs["model"], "fallback spoke")

    calls = _patch_chat(monkeypatch, handler)
    out = await chat_with_fallback(
        messages=[ChatMessage(role="user", content="hi")],
        temperature=0.5,
        max_tokens=500,
        primary_model="moonshotai/kimi-k2.6",
        fallback_model="anthropic/claude-3.5-sonnet",
    )
    assert out.used_fallback is True
    assert out.result.model == "anthropic/claude-3.5-sonnet"
    assert len(calls) == 2
    assert calls[0]["model"] == "moonshotai/kimi-k2.6"
    assert calls[1]["model"] == "anthropic/claude-3.5-sonnet"


@pytest.mark.asyncio
async def test_upstream_5xx_triggers_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    async def handler(**kwargs: Any) -> ChatResult:
        if kwargs["model"] == "moonshotai/kimi-k2.6":
            raise UpstreamError("502 from primary")
        return _result(kwargs["model"], "fallback spoke")

    _patch_chat(monkeypatch, handler)
    out = await chat_with_fallback(
        messages=[ChatMessage(role="user", content="hi")],
        temperature=0.5,
        max_tokens=500,
        primary_model="moonshotai/kimi-k2.6",
        fallback_model="anthropic/claude-3.5-sonnet",
    )
    assert out.used_fallback is True


@pytest.mark.asyncio
async def test_other_4xx_does_not_trigger_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """OrchestratorError (non-429 4xx) is a caller bug — re-raise
    untouched, do NOT switch models."""

    async def handler(**kwargs: Any) -> ChatResult:
        raise OrchestratorError("400 bad model id")

    calls = _patch_chat(monkeypatch, handler)
    with pytest.raises(OrchestratorError):
        await chat_with_fallback(
            messages=[ChatMessage(role="user", content="hi")],
            temperature=0.5,
            max_tokens=500,
            primary_model="moonshotai/kimi-k2.6",
            fallback_model="anthropic/claude-3.5-sonnet",
        )
    # Only the primary was tried — no second call to fallback
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_both_models_failing_reraises_fallback_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def handler(**kwargs: Any) -> ChatResult:
        if kwargs["model"] == "moonshotai/kimi-k2.6":
            raise RateLimitError("primary 429")
        raise UpstreamError("fallback 503")

    _patch_chat(monkeypatch, handler)
    with pytest.raises(UpstreamError, match="fallback 503"):
        await chat_with_fallback(
            messages=[ChatMessage(role="user", content="hi")],
            temperature=0.5,
            max_tokens=500,
            primary_model="moonshotai/kimi-k2.6",
            fallback_model="anthropic/claude-3.5-sonnet",
        )


@pytest.mark.asyncio
async def test_defaults_come_from_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """If no models explicitly given, picks up from Settings."""
    seen: dict[str, Any] = {}

    async def handler(**kwargs: Any) -> ChatResult:
        seen["model"] = kwargs["model"]
        return _result(kwargs["model"])

    _patch_chat(monkeypatch, handler)
    from bot.config import get_settings

    await chat_with_fallback(
        messages=[ChatMessage(role="user", content="hi")],
        temperature=0.5,
        max_tokens=500,
    )
    assert seen["model"] == get_settings().default_llm_model
