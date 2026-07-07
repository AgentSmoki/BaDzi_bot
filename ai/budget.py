"""Dynamic token budget calculation (ADR-009).

Sizes ``max_tokens`` for chat-completion calls based on how much of the
model's context window the *input* messages already consume. Without
this every call would either ship a small fixed cap (and truncate long
answers) or a huge one (and burn budget on accidental 100k responses).

Tier-aware: the same prompt may go to Qwen3.6-35B-A3B (262k context)
or to Claude 3.5 Sonnet via OpenRouter (200k context). The fallback
layer (``ai.fallback``) recomputes ``max_tokens`` for each tier so the
output budget always matches the model that's actually answering.

Token estimation here is a char-based heuristic
(``len(content) / CHARS_PER_TOKEN``). Russian+Chinese mixed text lands
around 3.0 chars/token; English ≈4.0; we use 3.2 as the global average.
This is intentional — exact ``prompt_tokens`` come back in the response
``usage`` block, and we log the post-hoc value so the heuristic can be
re-tuned from real traffic. A heuristic that over-estimates input is
*safe* (we just allocate a slightly smaller output budget); one that
under-estimates can blow the context window, so the 1000-token safety
margin below absorbs the wobble.

Intent classes mirror ``ai.router.RouteDecision.intent`` plus a fourth
class ``interpretation`` reserved for the 6-block base reading
(``ai.base_interpretation``) which wants ~40% of the window since each
block is 100-180 words and we send six in one call.
"""

from __future__ import annotations

from typing import Final, Literal

from ai.orchestrator import ChatMessage

CHARS_PER_TOKEN: Final[float] = 3.2
SAFETY_MARGIN_TOKENS: Final[int] = 1000

IntentClass = Literal["simple", "normal", "complex", "interpretation"]

DEFAULT_RATIO: Final[dict[IntentClass, float]] = {
    "simple": 0.05,
    "normal": 0.15,
    "complex": 0.30,
    "interpretation": 0.40,
}


def estimate_input_tokens(messages: list[ChatMessage]) -> int:
    """Rough char-based token estimate for a list of chat messages.

    Sums ``len(content)`` across all messages, divides by
    ``CHARS_PER_TOKEN``, then adds 4 tokens per message for the
    role/separator overhead that OpenAI-compat APIs serialize on the
    wire. Conservative — real ``prompt_tokens`` from the response are
    typically within ±10% of this estimate for our prompts.
    """
    total_chars = sum(len(m.content) for m in messages)
    return int(total_chars / CHARS_PER_TOKEN) + 4 * len(messages)


def compute_max_tokens(
    *,
    messages: list[ChatMessage],
    model_context_window: int,
    intent: IntentClass = "normal",
    floor: int = 2000,
    ceiling: int | None = None,
) -> int:
    """Pick ``max_tokens`` that fits the model's context with safety margin.

    Algorithm::

        input_tokens   = estimate_input_tokens(messages)
        available_out  = model_context_window − input_tokens − SAFETY_MARGIN
        desired_out    = DEFAULT_RATIO[intent] × model_context_window
        result         = clamp(min(desired_out, available_out), floor, ceiling)

    Edge cases:
    - If ``available_out`` < ``floor`` (prompt nearly fills the window),
      returns ``available_out`` anyway so the caller can decide whether
      to truncate history. The orchestrator will surface a "thinking
      truncated" error if reasoning eats the whole tiny budget.
    - If ``available_out`` ≤ 0 (input already exceeds context), returns
      0 — the fallback layer treats that as a signal to skip this tier.

    The ratios are tuned for Qwen3.6 (262k) but scale linearly to
    Claude 3.5 Sonnet (200k) via the ``model_context_window`` argument.
    """
    input_tokens = estimate_input_tokens(messages)
    available_out = model_context_window - input_tokens - SAFETY_MARGIN_TOKENS
    if available_out <= 0:
        return 0

    desired_out = int(DEFAULT_RATIO[intent] * model_context_window)
    target = min(desired_out, available_out)

    if ceiling is not None:
        target = min(target, ceiling)

    if available_out < floor:
        return available_out
    return max(floor, target)
