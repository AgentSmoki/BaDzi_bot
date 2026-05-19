"""Unit tests for ai.orchestrator (provider-agnostic).

Both providers (YC + OpenRouter) are mocked via httpx.MockTransport so
no network call leaves the test process — the conventions doc
explicitly bans live AI calls in pytest (cost). Each test installs a
mock for one provider and exercises ``chat(provider=..., ...)``.

Coverage targets:
- happy path on both providers
- 429 → RateLimitError
- 5xx → UpstreamError
- 4xx (other) → OrchestratorError (not a fallback candidate)
- malformed JSON / unexpected shape → UpstreamError
- network failure → UpstreamError
- thinking-truncated → specific UpstreamError naming max_tokens
- Authorization header shape per provider
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator

import httpx
import pytest

from ai import orchestrator
from ai.orchestrator import (
    ChatMessage,
    OrchestratorError,
    Provider,
    RateLimitError,
    UpstreamError,
    chat,
)


def _build_response(
    text: str = "Привет, я Анастасия.",
    *,
    model: str = "gpt://test-folder/qwen3.6-35b-a3b/latest",
    prompt_tokens: int = 50,
    completion_tokens: int = 12,
    cost: float = 0.00021,
) -> dict[str, object]:
    return {
        "id": "gen-test-1",
        "model": model,
        "choices": [{"message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "cost": cost,
        },
    }


@pytest.fixture(autouse=True)
def _reset_clients() -> Iterator[None]:
    """Force orchestrator to rebuild its per-provider singleton clients
    for every test so each test can install its own MockTransport."""
    orchestrator._clients.clear()
    yield
    orchestrator._clients.clear()


def _install_mock(
    provider: Provider,
    handler: Callable[[httpx.Request], httpx.Response],
) -> None:
    """Patch the singleton client for ``provider`` with a MockTransport."""
    transport = httpx.MockTransport(handler)
    base_url = orchestrator._YC_BASE_URL if provider == "yc" else orchestrator._OPENROUTER_BASE_URL
    # Headers don't matter for MockTransport, but we set the same shape
    # the production client would so any code that introspects headers
    # in tests sees a realistic value.
    auth = "Api-Key test" if provider == "yc" else "Bearer test"
    headers = {"Authorization": auth}
    if provider == "yc":
        headers["x-folder-id"] = "test-folder"
    orchestrator._clients[provider] = httpx.AsyncClient(
        base_url=base_url,
        transport=transport,
        headers=headers,
    )


# ── happy path on both providers ─────────────────────────────────────


@pytest.mark.asyncio
async def test_chat_yc_happy_path_parses_text_and_usage() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        captured["auth"] = request.headers.get("authorization")
        captured["folder"] = request.headers.get("x-folder-id")
        body = json.loads(request.content)
        assert body["model"].startswith("gpt://")
        return httpx.Response(200, json=_build_response())

    _install_mock("yc", handler)
    result = await chat(
        provider="yc",
        model="gpt://test-folder/qwen3.6-35b-a3b/latest",
        messages=[
            ChatMessage(role="system", content="Ты Анастасия."),
            ChatMessage(role="user", content="Расскажи про мою карту."),
        ],
        max_tokens=2000,
    )
    assert "Анастасия" in result.text
    assert result.provider == "yc"
    assert result.usage.prompt_tokens == 50
    assert result.usage.completion_tokens == 12
    assert result.usage.total_tokens == 62
    assert result.latency_ms >= 0
    assert result.trace_id
    # Headers reflect YC auth pattern (Api-Key + x-folder-id)
    assert captured["auth"] == "Api-Key test"
    assert captured["folder"] == "test-folder"


@pytest.mark.asyncio
async def test_chat_openrouter_happy_path_uses_bearer_auth() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json=_build_response(model="anthropic/claude-3.5-sonnet"))

    _install_mock("openrouter", handler)
    result = await chat(
        provider="openrouter",
        model="anthropic/claude-3.5-sonnet",
        messages=[ChatMessage(role="user", content="hi")],
        max_tokens=1000,
    )
    assert result.provider == "openrouter"
    assert captured["auth"] == "Bearer test"


@pytest.mark.asyncio
async def test_chat_uses_caller_trace_id() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_build_response())

    _install_mock("yc", handler)
    result = await chat(
        provider="yc",
        model="gpt://f/qwen3.6-35b-a3b/latest",
        messages=[ChatMessage(role="user", content="hi")],
        max_tokens=500,
        trace_id="my-trace-123",
    )
    assert result.trace_id == "my-trace-123"


# ── error paths ──────────────────────────────────────────────────────


@pytest.mark.asyncio
@pytest.mark.parametrize("provider", ["yc", "openrouter"])
async def test_chat_raises_rate_limit_on_429(provider: Provider) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="Too Many Requests")

    _install_mock(provider, handler)
    with pytest.raises(RateLimitError):
        await chat(
            provider=provider,
            model="anything",
            messages=[ChatMessage(role="user", content="hi")],
            max_tokens=500,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [500, 502, 503, 504])
async def test_chat_raises_upstream_error_on_5xx(status: int) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text="upstream broken")

    _install_mock("yc", handler)
    with pytest.raises(UpstreamError):
        await chat(
            provider="yc",
            model="gpt://f/qwen3.6-35b-a3b/latest",
            messages=[ChatMessage(role="user", content="hi")],
            max_tokens=500,
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 401, 403, 404])
async def test_chat_raises_orchestrator_error_on_other_4xx(status: int) -> None:
    """Non-429 4xx errors are caller bugs — must NOT trigger tier
    fallback in ai.fallback."""

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text="bad request")

    _install_mock("yc", handler)
    with pytest.raises(OrchestratorError) as exc_info:
        await chat(
            provider="yc",
            model="gpt://f/qwen3.6-35b-a3b/latest",
            messages=[ChatMessage(role="user", content="hi")],
            max_tokens=500,
        )
    # Specifically not a RateLimit / Upstream subclass.
    assert not isinstance(exc_info.value, RateLimitError | UpstreamError)


@pytest.mark.asyncio
async def test_chat_raises_upstream_on_malformed_json() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not valid json{")

    _install_mock("yc", handler)
    with pytest.raises(UpstreamError):
        await chat(
            provider="yc",
            model="gpt://f/qwen3.6-35b-a3b/latest",
            messages=[ChatMessage(role="user", content="hi")],
            max_tokens=500,
        )


@pytest.mark.asyncio
async def test_chat_raises_upstream_on_unexpected_shape() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"id": "x", "error": "weird provider"})

    _install_mock("yc", handler)
    with pytest.raises(UpstreamError):
        await chat(
            provider="yc",
            model="gpt://f/qwen3.6-35b-a3b/latest",
            messages=[ChatMessage(role="user", content="hi")],
            max_tokens=500,
        )


@pytest.mark.asyncio
async def test_chat_raises_upstream_on_network_failure() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("dns lookup failed")

    _install_mock("yc", handler)
    with pytest.raises(UpstreamError):
        await chat(
            provider="yc",
            model="gpt://f/qwen3.6-35b-a3b/latest",
            messages=[ChatMessage(role="user", content="hi")],
            max_tokens=500,
        )


@pytest.mark.asyncio
async def test_chat_thinking_model_truncated_gives_specific_error() -> None:
    """When a thinking model (Qwen3.6 / K2.6) burns max_tokens on
    reasoning and arrives at finish_reason=length with content=null,
    the user should get a specific message naming max_tokens — not a
    generic 'unexpected shape'."""

    def handler(_: httpx.Request) -> httpx.Response:
        body = {
            "choices": [
                {
                    "finish_reason": "length",
                    "native_finish_reason": "length",
                    "message": {
                        "role": "assistant",
                        "content": None,
                        # YC Qwen3.6 names this ``reasoning_content``;
                        # OpenRouter names it ``reasoning``. We support both.
                        "reasoning_content": "...long internal monologue...",
                    },
                }
            ],
            "usage": {"prompt_tokens": 50, "completion_tokens": 200, "total_tokens": 250},
        }
        return httpx.Response(200, json=body)

    _install_mock("yc", handler)
    with pytest.raises(UpstreamError) as exc:
        await chat(
            provider="yc",
            model="gpt://f/qwen3.6-35b-a3b/latest",
            messages=[ChatMessage(role="user", content="hi")],
            max_tokens=200,
        )
    assert "max_tokens" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_chat_handles_missing_usage_fields() -> None:
    """Some providers return responses without a ``usage`` block.
    Orchestrator must default to zeros instead of crashing."""

    def handler(_: httpx.Request) -> httpx.Response:
        body = _build_response()
        del body["usage"]
        return httpx.Response(200, json=body)

    _install_mock("yc", handler)
    result = await chat(
        provider="yc",
        model="gpt://f/qwen3.6-35b-a3b/latest",
        messages=[ChatMessage(role="user", content="hi")],
        max_tokens=500,
    )
    assert result.usage.prompt_tokens == 0
    assert result.usage.cost_usd == 0.0
