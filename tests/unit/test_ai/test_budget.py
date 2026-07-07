"""Unit tests for ai.budget — dynamic max_tokens sizing.

Pure-function module, no mocks needed. Each test pins one
combination of (input size, ctx window, intent) → expected output.
"""

from __future__ import annotations

from ai.budget import (
    CHARS_PER_TOKEN,
    DEFAULT_RATIO,
    SAFETY_MARGIN_TOKENS,
    compute_max_tokens,
    estimate_input_tokens,
)
from ai.orchestrator import ChatMessage


def _msg(content: str, role: str = "user") -> ChatMessage:
    return ChatMessage(role=role, content=content)  # type: ignore[arg-type]


class TestEstimateInputTokens:
    def test_empty_messages_zero(self) -> None:
        assert estimate_input_tokens([]) == 0

    def test_single_short_message_includes_overhead(self) -> None:
        # 'hello' = 5 chars / 3.2 ≈ 1, plus 4 overhead = 5
        assert estimate_input_tokens([_msg("hello")]) == 5

    def test_multiple_messages_sum_with_per_message_overhead(self) -> None:
        msgs = [_msg("a" * 320), _msg("b" * 320), _msg("c" * 320)]
        # 960 chars / 3.2 = 300 + 4*3 = 312
        assert estimate_input_tokens(msgs) == 312


class TestComputeMaxTokens:
    def test_small_input_returns_intent_ratio_of_context(self) -> None:
        # 100 chars ≈ 31 tokens, ctx=10_000, complex ratio=0.30 → 3000
        result = compute_max_tokens(
            messages=[_msg("x" * 100)],
            model_context_window=10_000,
            intent="complex",
        )
        assert result == int(10_000 * DEFAULT_RATIO["complex"])

    def test_huge_input_returns_available_minus_safety(self) -> None:
        # Fill ~95% of context: input ≈ 9500 tokens, ctx=10_000
        # → available = 10_000 - 9500 - 1000 = -500 → returns 0
        big = "x" * int(9500 * CHARS_PER_TOKEN)
        result = compute_max_tokens(
            messages=[_msg(big)],
            model_context_window=10_000,
            intent="normal",
        )
        assert result == 0

    def test_input_just_fits_returns_available_below_floor(self) -> None:
        # input ≈ 8000 tokens, ctx=10_000, margin=1000 → available=1000
        # floor=2000 by default → returns available (1000) since available<floor
        big = "y" * int(8000 * CHARS_PER_TOKEN)
        result = compute_max_tokens(
            messages=[_msg(big)],
            model_context_window=10_000,
            intent="complex",
            floor=2000,
        )
        # input_tokens = int(8000*3.2 / 3.2) + 4 = 8004 → available = 996
        assert 900 <= result <= 1000

    def test_ceiling_clamps_large_desired_output(self) -> None:
        # ctx=200_000, interpretation ratio=0.4 → desired 80_000.
        # ceiling=10_000 should clamp.
        result = compute_max_tokens(
            messages=[_msg("hi")],
            model_context_window=200_000,
            intent="interpretation",
            ceiling=10_000,
        )
        assert result == 10_000

    def test_floor_kicks_in_for_low_intent_on_small_ctx(self) -> None:
        # ctx=10_000, simple ratio=0.05 → desired 500.
        # floor=2000 should win since input is small.
        result = compute_max_tokens(
            messages=[_msg("hi")],
            model_context_window=10_000,
            intent="simple",
            floor=2000,
        )
        assert result == 2000

    def test_intent_scaling_monotonic(self) -> None:
        # Same input + ctx, max_tokens should grow with intent weight.
        msgs = [_msg("hi")]
        simple = compute_max_tokens(
            messages=msgs, model_context_window=100_000, intent="simple", ceiling=100_000
        )
        normal = compute_max_tokens(
            messages=msgs, model_context_window=100_000, intent="normal", ceiling=100_000
        )
        complex_ = compute_max_tokens(
            messages=msgs, model_context_window=100_000, intent="complex", ceiling=100_000
        )
        interp = compute_max_tokens(
            messages=msgs,
            model_context_window=100_000,
            intent="interpretation",
            ceiling=100_000,
        )
        assert simple < normal < complex_ < interp

    def test_qwen36_real_world_normal_question(self) -> None:
        # System prompt ≈39 KB, chart block ≈2 KB, question ≈200 chars.
        # ctx=262_144 (Qwen3.6 native), intent=normal (0.15) → ~39k
        # ceiling=32_000 clamps to 32_000.
        sys_prompt = "x" * 39_000
        chart_block = "y" * 2_000
        question = "что значит мой Господин дня?"
        result = compute_max_tokens(
            messages=[_msg(sys_prompt, "system"), _msg(chart_block + question)],
            model_context_window=262_144,
            intent="normal",
            ceiling=32_000,
        )
        assert result == 32_000

    def test_claude_fallback_smaller_context_smaller_budget(self) -> None:
        # Same prompt on Claude (200k vs Qwen 262k) → smaller output budget.
        sys_prompt = "x" * 39_000
        msgs = [_msg(sys_prompt, "system"), _msg("вопрос")]
        out_qwen = compute_max_tokens(
            messages=msgs,
            model_context_window=262_144,
            intent="complex",
            ceiling=100_000,
        )
        out_claude = compute_max_tokens(
            messages=msgs,
            model_context_window=200_000,
            intent="complex",
            ceiling=100_000,
        )
        assert out_qwen > out_claude

    def test_safety_margin_constant(self) -> None:
        # Documenting the 1000-token reservation so future refactors
        # don't silently shrink it without breaking this test.
        assert SAFETY_MARGIN_TOKENS == 1000
