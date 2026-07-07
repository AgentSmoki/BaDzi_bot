"""Provider-agnostic async client for LLM chat completions (ADR-009).

Single point of contact with the upstream chat-completions API. После
миграции на OpenRouter-only (ADR-012) поддерживается один провайдер:

- ``openrouter`` — OpenRouter (``https://openrouter.ai/api/v1``),
                   auth via ``Bearer``. Обслуживает оба тира fallback
                   (разные модели), skill-router и весь fast-path.
                   Модель передаётся коротким слугом
                   (например ``qwen/qwen3.7-plus``).

Knows nothing about persona, history, fallback chains, or token
budgets — those concerns live in higher-level modules:
``ai.fallback`` (tier orchestration), ``ai.budget`` (max_tokens
sizing), ``ai.router`` (intent classification), ``ai.base_interpretation``
(6-block reading). This module's only job is to turn
``(provider, model, messages, max_tokens)`` into ``(text, usage)``
over async HTTP.

Both providers return OpenAI-compatible responses, so ``_parse_result``
handles them with a single code path. Cost telemetry asymmetry:
OpenRouter populates ``usage.cost`` in USD; YC AI Studio does not
return a cost field at all. We log ``cost_usd=0.0`` for YC and rely
on the future Langfuse integration (1.14) to multiply
``prompt/completion_tokens`` by a price table.

Qwen3.6-35B-A3B and Kimi-K2-class models emit ``reasoning_content``
before ``content`` — when ``max_tokens`` is too small they burn the
whole budget on reasoning and ``content`` arrives ``null`` with
``finish_reason="length"``. ``_parse_result`` detects this and raises
a specific ``UpstreamError`` so the caller knows to lift the budget
rather than treat it as a generic shape error.
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

Role = Literal["system", "user", "assistant"]
Provider = Literal["openrouter"]

_OPENROUTER_BASE_URL: Final = "https://openrouter.ai/api/v1"
_OPENROUTER_REFERER: Final = "https://github.com/AgentSmoki/BaDzi_bot"
_OPENROUTER_APP_TITLE: Final = "BaDzi-Bot Anastasia"


class ChatMessage(BaseModel):
    role: Role
    content: str


class ChatUsage(BaseModel):
    """Token + cost stats from one completion call.

    ``cost_usd`` is populated by OpenRouter; YC AI Studio leaves it at
    0.0 (no cost field on response). Post-hoc cost calculation lives
    in ``monitoring/`` once Langfuse lands (task 1.14)."""

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
    provider: Provider


class OrchestratorError(Exception):
    """Base error for orchestrator-level failures (network, auth,
    quota, malformed response). Lets the fallback layer distinguish
    upstream failures (retry on next tier) from our bugs (raise)."""


class RateLimitError(OrchestratorError):
    """Upstream returned 429 — likely fixable by switching tier."""


class UpstreamError(OrchestratorError):
    """Upstream returned 5xx, invalid JSON, or empty content after
    a reasoning burn — retry on next tier is reasonable."""


_clients: dict[Provider, httpx.AsyncClient] = {}


def _get_client(provider: Provider) -> httpx.AsyncClient:
    """Lazy per-provider singleton. Connection pooling kicks in across
    calls so high-frequency tiers (YC) stay warm."""
    if provider in _clients:
        return _clients[provider]
    settings = get_settings()
    timeout = httpx.Timeout(connect=10.0, read=settings.llm_timeout, write=10.0, pool=10.0)
    client = httpx.AsyncClient(
        base_url=_OPENROUTER_BASE_URL,
        headers={
            "Authorization": f"Bearer {settings.openrouter_api_key.get_secret_value()}",
            "HTTP-Referer": _OPENROUTER_REFERER,
            "X-Title": _OPENROUTER_APP_TITLE,
            "Content-Type": "application/json",
        },
        timeout=timeout,
    )
    _clients[provider] = client
    return client


async def close_clients() -> None:
    """Idempotent shutdown — call from bot lifecycle hook. Closes
    every provider client that was opened during the process lifetime."""
    for provider in list(_clients.keys()):
        await _clients[provider].aclose()
        del _clients[provider]


async def chat(
    *,
    provider: Provider,
    model: str,
    messages: list[ChatMessage],
    temperature: float = 0.7,
    max_tokens: int,
    trace_id: str | None = None,
    response_format: dict[str, str] | None = None,
) -> ChatResult:
    """Send a chat completion request to the chosen provider.

    Raises ``RateLimitError`` on 429 and ``UpstreamError`` on 5xx /
    malformed JSON / network problems so the fallback layer can
    decide whether to retry on the next tier or surface the error
    to the user.

    ``response_format`` is the OpenAI-style structured-output hint —
    e.g. ``{"type": "json_object"}`` to coerce JSON. Passed through
    only if non-None (legacy callers stay unchanged). Skill-router
    relies on this; if YC ignores the field, the prompt itself
    enforces JSON shape and we repair on parse failure.
    """
    trace = trace_id or uuid.uuid4().hex
    payload: dict[str, object] = {
        "model": model,
        "messages": [m.model_dump() for m in messages],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if response_format is not None:
        payload["response_format"] = response_format
    started = time.perf_counter()
    log = logger.bind(trace_id=trace, provider=provider, model=model)
    log.info("orchestrator.request", message_count=len(messages), max_tokens=max_tokens)
    try:
        response = await _get_client(provider).post("/chat/completions", json=payload)
    except httpx.HTTPError as exc:
        latency = int((time.perf_counter() - started) * 1000)
        log.warning("orchestrator.network_error", latency_ms=latency, error=str(exc))
        raise UpstreamError(f"network error talking to {provider}: {exc}") from exc

    latency = int((time.perf_counter() - started) * 1000)

    if response.status_code == 429:
        log.warning("orchestrator.rate_limited", latency_ms=latency, status=response.status_code)
        raise RateLimitError(f"{provider} rate limit (429): {response.text[:200]}")
    if response.status_code >= 500:
        log.warning("orchestrator.upstream_5xx", latency_ms=latency, status=response.status_code)
        raise UpstreamError(f"{provider} {response.status_code}: {response.text[:200]}")
    if response.status_code >= 400:
        # 4xx other than 429 means our request is wrong (bad model id,
        # missing key, etc.) — not a candidate for tier fallback.
        log.error("orchestrator.client_error", latency_ms=latency, status=response.status_code)
        raise OrchestratorError(f"{provider} {response.status_code}: {response.text[:200]}")

    try:
        body = response.json()
    except ValueError as exc:
        log.warning("orchestrator.bad_json", latency_ms=latency)
        raise UpstreamError(f"{provider} returned non-JSON body: {exc}") from exc

    return _parse_result(
        body, model=model, provider=provider, latency_ms=latency, trace_id=trace, log=log
    )


def _parse_result(
    body: dict,  # type: ignore[type-arg]
    *,
    model: str,
    provider: Provider,
    latency_ms: int,
    trace_id: str,
    log: structlog.stdlib.BoundLogger,
) -> ChatResult:
    """Pull text + usage out of an OpenAI-compatible response.

    Defensive against missing/extra fields — different upstream
    providers return slightly different shapes. The thinking-model
    truncation case (Qwen3.6, K2.6) is detected specifically so the
    caller can lift max_tokens rather than treat it as a shape error.
    """
    try:
        choice = body["choices"][0]
        message = choice["message"]
        text = message.get("content")
    except (KeyError, IndexError, TypeError) as exc:
        log.warning("orchestrator.shape_error", latency_ms=latency_ms)
        raise UpstreamError(f"unexpected response shape: {exc}") from exc

    if not isinstance(text, str) or not text:
        # Qwen3.6 / Kimi K2.6 / Claude-thinking emit ``reasoning`` (or
        # ``reasoning_content`` on YC) BEFORE the user-facing content.
        # If max_tokens was too small the reasoning fills the whole
        # budget and content arrives null with finish_reason="length".
        finish = choice.get("finish_reason") or choice.get("native_finish_reason") or ""
        has_reasoning = bool(
            message.get("reasoning")
            or message.get("reasoning_details")
            or message.get("reasoning_content")
        )
        if has_reasoning and finish == "length":
            log.warning(
                "orchestrator.thinking_truncated",
                latency_ms=latency_ms,
                finish_reason=finish,
            )
            raise UpstreamError(
                "thinking model exhausted max_tokens on reasoning before "
                "producing content; raise max_tokens (Qwen3.6/K2.6-class "
                "floor should be ≥2000)"
            )
        log.warning("orchestrator.shape_error", latency_ms=latency_ms)
        raise UpstreamError("choices[0].message.content was empty or not a string")

    usage_raw = body.get("usage") or {}
    usage = ChatUsage(
        prompt_tokens=int(usage_raw.get("prompt_tokens", 0) or 0),
        completion_tokens=int(usage_raw.get("completion_tokens", 0) or 0),
        total_tokens=int(usage_raw.get("total_tokens", 0) or 0),
        # YC doesn't return cost — stays 0.0, post-hoc calc lives in monitoring/
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
    return ChatResult(
        text=text,
        model=model,
        usage=usage,
        latency_ms=latency_ms,
        trace_id=trace_id,
        provider=provider,
    )
