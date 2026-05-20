"""Tests for ai.forecast (Wave 3b).

LLM is mocked — generators are thin wrappers around chat_with_fallback
so the tests verify (a) we send the right context shape and (b) the
result envelope is filled correctly."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

import pytest

from ai.fallback import FallbackResult
from ai.forecast import (
    ForecastResult,
    generate_daily_forecast,
    generate_monthly_forecast,
)
from ai.orchestrator import ChatMessage, ChatResult, ChatUsage
from calculator import calculate_chart
from calculator.models import ChartInput


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


def _fake_fallback_result(text: str) -> FallbackResult:
    return FallbackResult(
        result=ChatResult(
            text=text,
            model="qwen3.6-35b-a3b",
            usage=ChatUsage(prompt_tokens=1200, completion_tokens=600, total_tokens=1800),
            latency_ms=4500,
            trace_id="t",
            provider="yc",
        ),
        tier=1,
        provider="yc",
        used_fallback=False,
    )


# ── Daily ────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_daily_forecast_returns_result(
    monkeypatch: pytest.MonkeyPatch,
    reference_chart,  # type: ignore[no-untyped-def]
) -> None:
    text = (
        "## БЛОК 1. Общая энергия дня\nтекст1\n\n"
        "## БЛОК 2. Что активируется (звёзды и взаимодействия)\nтекст2\n\n"
        "## БЛОК 3. Благоприятные сферы\nтекст3\n\n"
        "## БЛОК 4. На что обратить внимание\nтекст4\n\n"
        "## БЛОК 5. Рекомендации на день\nтекст5"
    )

    async def fake_chat(**_kw: Any) -> FallbackResult:
        return _fake_fallback_result(text)

    monkeypatch.setattr("ai.forecast.chat_with_fallback", fake_chat)
    result = await generate_daily_forecast(chart=reference_chart, target_date=date(2026, 5, 19))

    assert isinstance(result, ForecastResult)
    assert "БЛОК 1. Общая энергия дня" in result.text
    assert "БЛОК 5. Рекомендации" in result.text
    assert result.model == "qwen3.6-35b-a3b"
    assert result.completion_tokens == 600
    assert result.used_fallback is False


@pytest.mark.asyncio
async def test_daily_forecast_sends_natal_and_target_in_payload(
    monkeypatch: pytest.MonkeyPatch,
    reference_chart,  # type: ignore[no-untyped-def]
) -> None:
    """The LLM payload must include [BAZI_DATA], [TARGET_DATE], and
    [TARGET_PILLARS] sections — these are the contract the prompt
    relies on. If something renames them, this test screams."""
    captured: dict[str, Any] = {}

    async def fake_chat(**kwargs: Any) -> FallbackResult:
        captured.update(kwargs)
        return _fake_fallback_result("## БЛОК 1. x\nx")

    monkeypatch.setattr("ai.forecast.chat_with_fallback", fake_chat)
    await generate_daily_forecast(chart=reference_chart, target_date=date(2026, 5, 19))

    messages: list[ChatMessage] = captured["messages"]
    user_content = messages[-1].content
    assert "[BAZI_DATA]" in user_content
    assert "[TARGET_DATE]" in user_content
    assert "2026-05-19" in user_content
    assert "[TARGET_PILLARS]" in user_content
    assert captured["intent"] == "interpretation"


@pytest.mark.asyncio
async def test_daily_forecast_system_prompt_includes_time_skill(
    monkeypatch: pytest.MonkeyPatch,
    reference_chart,  # type: ignore[no-untyped-def]
) -> None:
    """Forecast персона = base.md + time skill body."""
    captured: dict[str, Any] = {}

    async def fake_chat(**kwargs: Any) -> FallbackResult:
        captured.update(kwargs)
        return _fake_fallback_result("## БЛОК 1. x\nx")

    monkeypatch.setattr("ai.forecast.chat_with_fallback", fake_chat)
    await generate_daily_forecast(chart=reference_chart, target_date=date(2026, 5, 19))

    system = captured["messages"][0].content
    assert "[SKILL: time]" in system
    # base.md identity marker
    assert "Анастасия" in system


# ── Monthly ──────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_monthly_forecast_returns_result(
    monkeypatch: pytest.MonkeyPatch,
    reference_chart,  # type: ignore[no-untyped-def]
) -> None:
    text = (
        "## БЛОК 1. Общая энергия месяца\nx\n\n"
        "## БЛОК 2. Главная тема и вызов\nx\n\n"
        "## БЛОК 3. Возможности (сферы расцвета)\nx\n\n"
        "## БЛОК 4. Зоны риска\nx\n\n"
        "## БЛОК 5. По неделям\nнеделя1\nнеделя2\nнеделя3\nнеделя4\n\n"
        "## БЛОК 6. Рекомендации на месяц\nx"
    )

    async def fake_chat(**_kw: Any) -> FallbackResult:
        return _fake_fallback_result(text)

    monkeypatch.setattr("ai.forecast.chat_with_fallback", fake_chat)
    result = await generate_monthly_forecast(chart=reference_chart, period_start=date(2026, 6, 1))

    assert "По неделям" in result.text
    assert "БЛОК 6. Рекомендации" in result.text


@pytest.mark.asyncio
async def test_monthly_forecast_sends_mid_month_pillars(
    monkeypatch: pytest.MonkeyPatch,
    reference_chart,  # type: ignore[no-untyped-def]
) -> None:
    """Monthly prompt anchors the «по неделям» block on first-day +
    15th-day pillars. Without the mid-month sample the LLM hallucinates
    weekly transitions."""
    captured: dict[str, Any] = {}

    async def fake_chat(**kwargs: Any) -> FallbackResult:
        captured.update(kwargs)
        return _fake_fallback_result("## БЛОК 1. x\nx")

    monkeypatch.setattr("ai.forecast.chat_with_fallback", fake_chat)
    await generate_monthly_forecast(chart=reference_chart, period_start=date(2026, 6, 1))

    user_content = captured["messages"][-1].content
    assert "[TARGET_PILLARS]" in user_content
    assert "[TARGET_PILLARS_MID]" in user_content
    assert "2026-06-01" in user_content
    # 15-дневное смещение → 2026-06-30 (range start + 29)
    assert "2026-06-30" in user_content
