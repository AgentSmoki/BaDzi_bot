"""Tests for ai.text_extract.extract_birth_data (Wave 2)."""

from __future__ import annotations

from typing import Any

import pytest

from ai.orchestrator import ChatResult, ChatUsage, OrchestratorError
from ai.text_extract import ExtractedBirthData, extract_birth_data


def _ok_result(text: str) -> ChatResult:
    return ChatResult(
        text=text,
        model="qwen3.6-35b-a3b",
        usage=ChatUsage(prompt_tokens=300, completion_tokens=80, total_tokens=380),
        latency_ms=1500,
        trace_id="t",
        provider="openrouter",
    )


# ── Happy paths ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_full_extract(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake(**_kw: Any) -> ChatResult:
        return _ok_result(
            '{"date_iso":"1988-04-27","time_iso":"07:03",'
            '"city":"Севастополь","gender":"male",'
            '"has_birth_time":true,"confidence":0.92}'
        )

    monkeypatch.setattr("ai.text_extract.chat", fake)
    out = await extract_birth_data("27.04.88 Севастополь 07:03 утра, мужчина")

    assert out.date_iso == "1988-04-27"
    assert out.time_iso == "07:03"
    assert out.city == "Севастополь"
    assert out.gender == "male"
    assert out.has_birth_time is True
    assert out.confidence == pytest.approx(0.92)
    assert out.is_complete is True
    assert out.missing_fields == []
    assert out.raw_text == "27.04.88 Севастополь 07:03 утра, мужчина"


@pytest.mark.asyncio
async def test_no_time_is_supported(monkeypatch: pytest.MonkeyPatch) -> None:
    """User says «время не помню» → has_birth_time=False but extract is
    still complete (time is optional)."""

    async def fake(**_kw: Any) -> ChatResult:
        return _ok_result(
            '{"date_iso":"1990-07-15","time_iso":null,"city":"Москва",'
            '"gender":"female","has_birth_time":false,"confidence":0.95}'
        )

    monkeypatch.setattr("ai.text_extract.chat", fake)
    out = await extract_birth_data("15 июля 1990 в Москве, женщина, время не помню")

    assert out.time_iso is None
    assert out.has_birth_time is False
    assert out.is_complete is True


@pytest.mark.asyncio
async def test_partial_missing_city(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake(**_kw: Any) -> ChatResult:
        return _ok_result(
            '{"date_iso":"1985-12-03","time_iso":null,"city":null,'
            '"gender":null,"has_birth_time":false,"confidence":0.7}'
        )

    monkeypatch.setattr("ai.text_extract.chat", fake)
    out = await extract_birth_data("1985-12-03")

    assert out.is_complete is False
    assert "city" in out.missing_fields
    assert "gender" in out.missing_fields
    assert "date" not in out.missing_fields


# ── Defensive: LLM produces inconsistent / weird output ──────────────────


@pytest.mark.asyncio
async def test_pins_has_birth_time_false_when_time_iso_null(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """LLM occasionally says has_birth_time=true but time_iso=null —
    we forcibly fix that to keep downstream code consistent."""

    async def fake(**_kw: Any) -> ChatResult:
        return _ok_result(
            '{"date_iso":"1990-01-01","time_iso":null,"city":"Москва",'
            '"gender":"male","has_birth_time":true,"confidence":0.9}'
        )

    monkeypatch.setattr("ai.text_extract.chat", fake)
    out = await extract_birth_data("01.01.1990 Москва мужчина")
    assert out.has_birth_time is False


# ── Fallback paths ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_empty_input_fallback() -> None:
    out = await extract_birth_data("")
    assert out.confidence == 0.0
    assert out.is_complete is False
    assert "fallback" not in out.raw_text  # raw_text stays empty


@pytest.mark.asyncio
async def test_upstream_error_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    async def boom(**_kw: Any) -> ChatResult:
        raise OrchestratorError("network down")

    monkeypatch.setattr("ai.text_extract.chat", boom)
    out = await extract_birth_data("какой-то текст")
    assert out.confidence == 0.0
    assert out.date_iso is None


@pytest.mark.asyncio
async def test_no_json_in_output_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake(**_kw: Any) -> ChatResult:
        return _ok_result("Извините, не могу извлечь.")

    monkeypatch.setattr("ai.text_extract.chat", fake)
    out = await extract_birth_data("any")
    assert out.confidence == 0.0


@pytest.mark.asyncio
async def test_invalid_json_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    async def fake(**_kw: Any) -> ChatResult:
        return _ok_result('{"date_iso": broken json}')

    monkeypatch.setattr("ai.text_extract.chat", fake)
    out = await extract_birth_data("any")
    assert out.confidence == 0.0


@pytest.mark.asyncio
async def test_schema_validation_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """LLM hallucinated a gender value outside the Literal."""

    async def fake(**_kw: Any) -> ChatResult:
        return _ok_result(
            '{"date_iso":"1990-01-01","time_iso":null,"city":"X",'
            '"gender":"alien","has_birth_time":false,"confidence":0.9}'
        )

    monkeypatch.setattr("ai.text_extract.chat", fake)
    out = await extract_birth_data("any")
    assert out.confidence == 0.0


# ── Side effects: what we send to chat ───────────────────────────────────


@pytest.mark.asyncio
async def test_passes_response_format_json(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    async def fake(**kwargs: Any) -> ChatResult:
        captured.update(kwargs)
        return _ok_result(
            '{"date_iso":null,"time_iso":null,"city":null,'
            '"gender":null,"has_birth_time":false,"confidence":0.1}'
        )

    monkeypatch.setattr("ai.text_extract.chat", fake)
    await extract_birth_data("any")
    assert captured["response_format"] == {"type": "json_object"}
    assert captured["temperature"] == pytest.approx(0.1)
    assert captured["provider"] == "openrouter"


def test_extracted_birth_data_is_frozen() -> None:
    """Frozen model — no accidental mutation."""
    from pydantic import ValidationError

    ext = ExtractedBirthData(raw_text="x", confidence=0.5)
    with pytest.raises(ValidationError):
        ext.date_iso = "1990-01-01"  # type: ignore[misc]
