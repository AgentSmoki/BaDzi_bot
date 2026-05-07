"""OpenRouter async client for LLM chat completions.

Single point of contact with the OpenRouter HTTP API. Knows nothing
about the bot transport, Anastasia's persona, or fallback chains —
those concerns live in higher-level modules (1.8.5 fallback, 1.10
base interpretation, 1.13 FAQ chat). This module's only job is to
turn ``(model_id, messages)`` into ``(text, usage)`` over async HTTP.

Per ADR-002 the active model is selected via a Redis feature flag
(``llm:active_model``); this module accepts the model id as an
explicit argument so the flag-reading code stays in 1.8.5/1.13.

Cost / latency / token telemetry is logged through structlog with
``trace_id`` so AI calls can be reconciled with the
``Consultation`` table later.
"""

from __future__ import annotations

import time
import uuid
from typing import Final, Literal

import httpx
import structlog
from pydantic import BaseModel, Field

from bot.config import get_settings

logger = structlog.get_logger(__name__)

OPENROUTER_BASE_URL: Final = "https://openrouter.ai/api/v1"
OPENROUTER_REFERER: Final = "https://github.com/AgentSmoki/BaDzi_bot"
OPENROUTER_APP_TITLE: Final = "BaDzi-Bot Anastasia"

Role = Literal["system", "user", "assistant"]


class ChatMessage(BaseModel):
    role: Role
    content: str


class ChatUsage(BaseModel):
    """Token + cost stats from one completion call.

    OpenRouter returns prompt/completion token counts and (when the
    upstream provider exposes it) a USD cost figure on the response's
    ``usage`` object."""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0


class ChatResult(BaseModel):
    text: str
    model: str
    usage: ChatUsage = Field(default_factory=ChatUsage)
    latency_ms: int
    trace_id: str


class OrchestratorError(Exception):
    """Base error for orchestrator-level failures (network, auth,
    quota, malformed response). Lets the fallback layer (1.8.5)
    distinguish AI failures from upstream bugs."""


class RateLimitError(OrchestratorError):
    """OpenRouter returned 429."""


class UpstreamError(OrchestratorError):
    """OpenRouter / provider returned 5xx or invalid JSON."""


_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    """Lazy singleton httpx client. Reused across calls so connection
    pooling and HTTP/2 multiplexing actually kick in."""
    global _client
    if _client is None:
        settings = get_settings()
        _client = httpx.AsyncClient(
            base_url=OPENROUTER_BASE_URL,
            headers={
                "Authorization": f"Bearer {settings.openrouter_api_key.get_secret_value()}",
                "HTTP-Referer": OPENROUTER_REFERER,
                "X-Title": OPENROUTER_APP_TITLE,
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(connect=10.0, read=settings.llm_timeout, write=10.0, pool=10.0),
        )
    return _client


async def close_client() -> None:
    """Idempotent shutdown — call from bot lifecycle hook."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def chat(
    *,
    model: str,
    messages: list[ChatMessage],
    temperature: float = 0.7,
    max_tokens: int | None = None,
    trace_id: str | None = None,
) -> ChatResult:
    """Send a chat completion request.

    Raises ``RateLimitError`` on 429 and ``UpstreamError`` on 5xx /
    malformed JSON / network problems so the fallback layer (1.8.5)
    can decide whether to retry, switch model, or surface the error
    to the user.
    """
    settings = get_settings()
    trace = trace_id or uuid.uuid4().hex
    payload: dict[str, object] = {
        "model": model,
        "messages": [m.model_dump() for m in messages],
        "temperature": temperature,
        "max_tokens": max_tokens or settings.max_output_tokens,
    }
    started = time.perf_counter()
    log = logger.bind(trace_id=trace, model=model)
    log.info("orchestrator.request", message_count=len(messages))
    try:
        response = await _get_client().post("/chat/completions", json=payload)
    except httpx.HTTPError as exc:
        latency = int((time.perf_counter() - started) * 1000)
        log.warning("orchestrator.network_error", latency_ms=latency, error=str(exc))
        raise UpstreamError(f"network error talking to OpenRouter: {exc}") from exc

    latency = int((time.perf_counter() - started) * 1000)

    if response.status_code == 429:
        log.warning("orchestrator.rate_limited", latency_ms=latency, status=response.status_code)
        raise RateLimitError(f"OpenRouter rate limit (429): {response.text[:200]}")
    if response.status_code >= 500:
        log.warning("orchestrator.upstream_5xx", latency_ms=latency, status=response.status_code)
        raise UpstreamError(f"OpenRouter {response.status_code}: {response.text[:200]}")
    if response.status_code >= 400:
        # 4xx other than 429 means our request is wrong (bad model id,
        # missing key, etc.) — not a candidate for fallback.
        log.error("orchestrator.client_error", latency_ms=latency, status=response.status_code)
        raise OrchestratorError(f"OpenRouter {response.status_code}: {response.text[:200]}")

    try:
        body = response.json()
    except ValueError as exc:
        log.warning("orchestrator.bad_json", latency_ms=latency)
        raise UpstreamError(f"OpenRouter returned non-JSON body: {exc}") from exc

    return _parse_result(body, model=model, latency_ms=latency, trace_id=trace, log=log)


def _parse_result(
    body: dict,  # type: ignore[type-arg]
    *,
    model: str,
    latency_ms: int,
    trace_id: str,
    log: structlog.stdlib.BoundLogger,
) -> ChatResult:
    """Pull text + usage out of an OpenRouter response. Defensive
    against missing / extra fields — different upstream providers
    return slightly different shapes."""
    try:
        choice = body["choices"][0]
        message = choice["message"]
        text = message.get("content")
    except (KeyError, IndexError, TypeError) as exc:
        log.warning("orchestrator.shape_error", latency_ms=latency_ms)
        raise UpstreamError(f"unexpected response shape: {exc}") from exc

    if not isinstance(text, str) or not text:
        # Thinking models (K2.6, claude-thinking, etc.) emit
        # `reasoning` / `reasoning_details` BEFORE the user-facing
        # content. If max_tokens was too small the reasoning fills
        # the whole budget and `content` arrives null with
        # finish_reason="length". Surface this as a specific error
        # so the caller knows to raise the budget — not as a generic
        # "weird shape".
        finish = choice.get("finish_reason") or choice.get("native_finish_reason") or ""
        has_reasoning = bool(message.get("reasoning") or message.get("reasoning_details"))
        if has_reasoning and finish == "length":
            log.warning(
                "orchestrator.thinking_truncated",
                latency_ms=latency_ms,
                finish_reason=finish,
            )
            raise UpstreamError(
                "thinking model exhausted max_tokens on reasoning before "
                "producing content; raise max_tokens (router budgets "
                "should be ≥2500 for K2.6-class)"
            )
        log.warning("orchestrator.shape_error", latency_ms=latency_ms)
        raise UpstreamError("choices[0].message.content was empty or not a string")

    usage_raw = body.get("usage") or {}
    usage = ChatUsage(
        prompt_tokens=int(usage_raw.get("prompt_tokens", 0) or 0),
        completion_tokens=int(usage_raw.get("completion_tokens", 0) or 0),
        total_tokens=int(usage_raw.get("total_tokens", 0) or 0),
        cost_usd=float(usage_raw.get("cost", 0.0) or 0.0),
    )
    log.info(
        "orchestrator.response",
        latency_ms=latency_ms,
        prompt_tokens=usage.prompt_tokens,
        completion_tokens=usage.completion_tokens,
        cost_usd=usage.cost_usd,
        text_chars=len(text),
    )
    return ChatResult(text=text, model=model, usage=usage, latency_ms=latency_ms, trace_id=trace_id)
