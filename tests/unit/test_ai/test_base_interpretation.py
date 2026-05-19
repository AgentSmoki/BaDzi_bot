"""Tests for ai.base_interpretation. ``chat_with_fallback`` is mocked
so the suite never touches OpenRouter — conventions.mdc forbids live
LLM calls in pytest because they cost money."""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from ai.base_interpretation import (
    BLOCK_TITLES,
    BaseInterpretation,
    format_for_telegram,
    generate_base_interpretation,
    parse_blocks,
)
from ai.fallback import FallbackResult
from ai.orchestrator import ChatResult, ChatUsage
from calculator import calculate_chart
from calculator.models import ChartInput

# ── parse_blocks ─────────────────────────────────────────────────────────


def test_parse_blocks_extracts_all_six_in_order() -> None:
    text = "\n".join(
        [
            "## БЛОК 1. Баланс",
            "Тут про стихии.",
            "",
            "## БЛОК 2. ГД",
            "Тут про личность.",
            "",
            "## БЛОК 3. Круг",
            "Реализация.",
            "",
            "## БЛОК 4. Партнёр",
            "Совместимость.",
            "",
            "## БЛОК 5. Сильные стороны",
            "Что удаётся.",
            "",
            "## БЛОК 6. Текущий год",
            "Сейчас.",
        ]
    )
    p = parse_blocks(text)
    assert p.block_1_balance == "Тут про стихии."
    assert p.block_2_day_master == "Тут про личность."
    assert p.block_3_realization == "Реализация."
    assert p.block_4_partner == "Совместимость."
    assert p.block_5_strengths == "Что удаётся."
    assert p.block_6_current_year == "Сейчас."


def test_parse_blocks_tolerates_punctuation_and_case() -> None:
    """Headings might come back as `## Блок 1:`, `## BLOCK 2 —`,
    `## БЛОК 3.` — all should still parse."""
    text = "\n".join(
        [
            "## Блок 1: Баланс",
            "первый",
            "## BLOCK 2 — ГД",
            "второй",
            "## БЛОК 3. Круг",
            "третий",
        ]
    )
    p = parse_blocks(text)
    assert p.block_1_balance == "первый"
    assert p.block_2_day_master == "второй"
    assert p.block_3_realization == "третий"


def test_parse_blocks_handles_out_of_order() -> None:
    """Defensive: if the LLM emits 2 before 1, we still want each
    body to land in its correct slot."""
    text = "\n".join(
        [
            "## БЛОК 2. ГД",
            "это блок 2",
            "## БЛОК 1. Баланс",
            "это блок 1",
        ]
    )
    p = parse_blocks(text)
    assert p.block_1_balance == "это блок 1"
    assert p.block_2_day_master == "это блок 2"


def test_parse_blocks_missing_blocks_become_empty() -> None:
    text = "## БЛОК 1. Баланс\nтолько первый"
    p = parse_blocks(text)
    assert p.block_1_balance == "только первый"
    assert p.block_2_day_master == ""
    assert p.block_6_current_year == ""


def test_parse_blocks_no_headings_falls_back_to_block_one() -> None:
    """If the LLM returns plain text with no headings, drop it all
    into block 1 instead of losing the response."""
    p = parse_blocks("просто длинный ответ без заголовков")
    assert p.block_1_balance == "просто длинный ответ без заголовков"
    assert p.block_2_day_master == ""


def test_parse_blocks_drops_text_before_first_heading() -> None:
    """LLM sometimes emits a one-line preamble like 'Хорошо, начнём:'.
    That shouldn't pollute block 1."""
    text = "\n".join(
        [
            "Хорошо, вот шесть блоков:",
            "",
            "## БЛОК 1. Баланс",
            "правильный текст",
        ]
    )
    p = parse_blocks(text)
    assert p.block_1_balance == "правильный текст"


# ── format_for_telegram ──────────────────────────────────────────────────


def test_format_for_telegram_renders_all_blocks() -> None:
    p = BaseInterpretation(
        block_1_balance="b1",
        block_2_day_master="b2",
        block_3_realization="b3",
        block_4_partner="b4",
        block_5_strengths="b5",
        block_6_current_year="b6",
    )
    out = format_for_telegram(p, chart_label="12.09.1999")
    assert "<b>Базовая интерпретация · 12.09.1999</b>" in out
    for idx in range(1, 7):
        assert f"<b>{idx}. {BLOCK_TITLES[idx]}</b>" in out
    assert "b1" in out and "b6" in out


def test_format_for_telegram_skips_empty_blocks() -> None:
    p = BaseInterpretation(block_1_balance="b1", block_3_realization="b3")
    out = format_for_telegram(p)
    assert "1. Баланс пяти стихий" in out
    assert "3. Реализация по кругу порождения" in out
    assert "2. Господин" not in out
    assert "4. Идеальный" not in out


def test_format_for_telegram_strips_exclamation_marks() -> None:
    """Anastasia stylebook forbids `!`. Even if the LLM ignores the
    instruction, the formatter must clean them up."""
    p = BaseInterpretation(block_1_balance="Какая прекрасная карта!")
    out = format_for_telegram(p)
    assert "!" not in out
    assert "Какая прекрасная карта." in out


# ── generate_base_interpretation (mocked) ────────────────────────────────


@pytest.fixture
def reference_chart():  # type: ignore[no-untyped-def]
    return calculate_chart(
        ChartInput(
            birth_datetime=datetime(1999, 9, 12, 23, 55),
            latitude=48.7894,
            longitude=44.7783,
            tz_offset=4.0,
            early_rat=False,
            gender="female",
        )
    )


def _fake_response(
    text: str, *, model: str = "gpt://test-folder/qwen3.6-35b-a3b/latest"
) -> FallbackResult:
    return FallbackResult(
        result=ChatResult(
            text=text,
            model=model,
            usage=ChatUsage(
                prompt_tokens=18000, completion_tokens=2500, total_tokens=20500, cost_usd=0.025
            ),
            latency_ms=42_000,
            trace_id="test-trace",
            provider="yc",
        ),
        tier=1,
        provider="yc",
        used_fallback=False,
    )


@pytest.mark.asyncio
async def test_generate_base_interpretation_parses_six_blocks(
    monkeypatch: pytest.MonkeyPatch,
    reference_chart,  # type: ignore[no-untyped-def]
) -> None:
    fake_md = "\n".join(
        [
            "## БЛОК 1. Баланс",
            "1",
            "## БЛОК 2. ГД",
            "2",
            "## БЛОК 3. Круг",
            "3",
            "## БЛОК 4. Партнёр",
            "4",
            "## БЛОК 5. Сильные стороны",
            "5",
            "## БЛОК 6. Текущий год",
            "6",
        ]
    )

    captured: dict[str, Any] = {}

    async def fake_chat(**kwargs: Any) -> FallbackResult:
        captured.update(kwargs)
        return _fake_response(fake_md)

    monkeypatch.setattr("ai.base_interpretation.chat_with_fallback", fake_chat)

    out = await generate_base_interpretation(chart=reference_chart, trace_id="abc")

    assert out.interpretation.block_1_balance == "1"
    assert out.interpretation.block_6_current_year == "6"
    assert out.model == "gpt://test-folder/qwen3.6-35b-a3b/latest"
    assert out.used_fallback is False
    assert out.cost_usd == pytest.approx(0.025)
    assert out.trace_id == "test-trace"
    # Interpretation calls now pass intent (not raw max_tokens) — budget
    # is sized per-tier inside ai.fallback.chat_with_fallback.
    assert captured["temperature"] < 0.6
    assert captured["intent"] == "interpretation"


@pytest.mark.asyncio
async def test_generate_base_interpretation_records_fallback_flag(
    monkeypatch: pytest.MonkeyPatch,
    reference_chart,  # type: ignore[no-untyped-def]
) -> None:
    """When chat_with_fallback says it switched to Claude, the result
    must carry that flag back to the caller (for telemetry)."""

    async def fake_chat(**_kwargs: Any) -> FallbackResult:
        return FallbackResult(
            result=ChatResult(
                text="## БЛОК 1. Баланс\nx",
                model="anthropic/claude-3.5-sonnet",
                usage=ChatUsage(),
                latency_ms=12_000,
                trace_id="t",
                provider="openrouter",
            ),
            tier=2,
            provider="openrouter",
            used_fallback=True,
        )

    monkeypatch.setattr("ai.base_interpretation.chat_with_fallback", fake_chat)
    out = await generate_base_interpretation(chart=reference_chart)
    assert out.used_fallback is True
    assert out.model == "anthropic/claude-3.5-sonnet"
