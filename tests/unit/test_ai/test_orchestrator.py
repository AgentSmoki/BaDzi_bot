"""Unit tests for ai.orchestrator.

OpenRouter is mocked via httpx.MockTransport so no network call leaves
the test process — the conventions doc explicitly bans live AI calls
in pytest because they cost money. Coverage targets:

- happy path: response parsed into ChatResult with usage + latency
- 429 → RateLimitError
- 5xx → UpstreamError
- 4xx (other) → OrchestratorError (not a fallback candidate)
- malformed JSON / unexpected shape → UpstreamError
- network failure → UpstreamError
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
    RateLimitError,
    UpstreamError,
    chat,
)


def _build_response(
    text: str = "Привет, я Анастасия.",
    *,
    prompt_tokens: int = 50,
    completion_tokens: int = 12,
    cost: float = 0.00021,
) -> dict[str, object]:
    return {
        "id": "gen-test-1",
        "model": "moonshotai/kimi-2.6",
        "choices": [{"message": {"role": "assistant", "content": text}, "finish_reason": "stop"}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "cost": cost,
        },
    }


@pytest.fixture(autouse=True)
def _reset_client() -> Iterator[None]:
    """Force orchestrator to rebuild its singleton client for every
    test so each test can install its own MockTransport."""
    orchestrator._client = None
    yield
    orchestrator._client = None


def _install_mock(handler: Callable[[httpx.Request], httpx.Response]) -> None:
    """Patch the singleton client with a MockTransport-driven one."""
    transport = httpx.MockTransport(handler)
    orchestrator._client = httpx.AsyncClient(
        base_url=orchestrator.OPENROUTER_BASE_URL,
        transport=transport,
        headers={"Authorization": "Bearer test"},
    )


@pytest.mark.asyncio
async def test_chat_happy_path_parses_text_and_usage() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/chat/completions")
        body = json.loads(request.content)
        assert body["model"] == "moonshotai/kimi-2.6"
        assert body["messages"][0]["role"] == "system"
        return httpx.Response(200, json=_build_response())

    _install_mock(handler)
    result = await chat(
        model="moonshotai/kimi-2.6",
        messages=[
            ChatMessage(role="system", content="Ты Анастасия."),
            ChatMessage(role="user", content="Расскажи про мою карту."),
        ],
    )
    assert "Анастасия" in result.text
    assert result.usage.prompt_tokens == 50
    assert result.usage.completion_tokens == 12
    assert result.usage.total_tokens == 62
    assert result.usage.cost_usd == pytest.approx(0.00021)
    assert result.latency_ms >= 0
    assert result.trace_id


@pytest.mark.asyncio
async def test_chat_uses_caller_trace_id() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=_build_response())

    _install_mock(handler)
    result = await chat(
        model="moonshotai/kimi-2.6",
        messages=[ChatMessage(role="user", content="hi")],
        trace_id="my-trace-123",
    )
    assert result.trace_id == "my-trace-123"


@pytest.mark.asyncio
async def test_chat_raises_rate_limit_on_429() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(429, text="Too Many Requests")

    _install_mock(handler)
    with pytest.raises(RateLimitError):
        await chat(
            model="moonshotai/kimi-2.6",
            messages=[ChatMessage(role="user", content="hi")],
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [500, 502, 503, 504])
async def test_chat_raises_upstream_error_on_5xx(status: int) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text="upstream broken")

    _install_mock(handler)
    with pytest.raises(UpstreamError):
        await chat(
            model="moonshotai/kimi-2.6",
            messages=[ChatMessage(role="user", content="hi")],
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("status", [400, 401, 403, 404])
async def test_chat_raises_orchestrator_error_on_other_4xx(status: int) -> None:
    """Non-429 4xx errors are caller bugs — must NOT be retried by the
    fallback layer (1.8.5)."""

    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(status, text="bad request")

    _install_mock(handler)
    with pytest.raises(OrchestratorError) as exc_info:
        await chat(
            model="moonshotai/kimi-2.6",
            messages=[ChatMessage(role="user", content="hi")],
        )
    # Specifically not a RateLimit / Upstream subclass.
    assert not isinstance(exc_info.value, RateLimitError | UpstreamError)


@pytest.mark.asyncio
async def test_chat_raises_upstream_on_malformed_json() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not valid json{")

    _install_mock(handler)
    with pytest.raises(UpstreamError):
        await chat(
            model="moonshotai/kimi-2.6",
            messages=[ChatMessage(role="user", content="hi")],
        )


@pytest.mark.asyncio
async def test_chat_raises_upstream_on_unexpected_shape() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        # No `choices` array → response shape unrecognised
        return httpx.Response(200, json={"id": "x", "error": "weird provider"})

    _install_mock(handler)
    with pytest.raises(UpstreamError):
        await chat(
            model="moonshotai/kimi-2.6",
            messages=[ChatMessage(role="user", content="hi")],
        )


@pytest.mark.asyncio
async def test_chat_raises_upstream_on_network_failure() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("dns lookup failed")

    _install_mock(handler)
    with pytest.raises(UpstreamError):
        await chat(
            model="moonshotai/kimi-2.6",
            messages=[ChatMessage(role="user", content="hi")],
        )


@pytest.mark.asyncio
async def test_chat_thinking_model_truncated_gives_specific_error() -> None:
    """When a thinking model spends its whole max_tokens on reasoning
    and arrives at finish_reason=length with content=null, the user
    should get a specific message naming max_tokens — not a generic
    'unexpected shape'."""

    def handler(_: httpx.Request) -> httpx.Response:
        body = {
            "choices": [
                {
                    "finish_reason": "length",
                    "native_finish_reason": "length",
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "reasoning": "...long internal monologue...",
                        "reasoning_details": [{"type": "reasoning.text", "text": "..."}],
                    },
                }
            ],
            "usage": {"prompt_tokens": 50, "completion_tokens": 200, "total_tokens": 250},
        }
        return httpx.Response(200, json=body)

    _install_mock(handler)
    with pytest.raises(UpstreamError) as exc:
        await chat(
            model="moonshotai/kimi-k2.6",
            messages=[ChatMessage(role="user", content="hi")],
            max_tokens=200,
        )
    assert "max_tokens" in str(exc.value).lower()


@pytest.mark.asyncio
async def test_chat_handles_missing_usage_fields() -> None:
    """Some OpenRouter providers return responses without a `usage`
    block. Orchestrator must default to zeros instead of crashing."""

    def handler(_: httpx.Request) -> httpx.Response:
        body = _build_response()
        del body["usage"]
        return httpx.Response(200, json=body)

    _install_mock(handler)
    result = await chat(
        model="moonshotai/kimi-2.6",
        messages=[ChatMessage(role="user", content="hi")],
    )
    assert result.usage.prompt_tokens == 0
    assert result.usage.cost_usd == 0.0
