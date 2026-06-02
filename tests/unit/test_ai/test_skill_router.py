"""Tests for ai.skill_router.

``ai.orchestrator.chat`` is monkeypatched — the suite never touches
the real LLM (conventions.mdc forbids live LLM calls in pytest).

Coverage targets:
- happy paths: 5 skills × correct routing
- failure modes: 4xx, network, malformed JSON, JSON-decode error,
  Pydantic validation error, response with markdown fences / preamble
- side-effects: chart_brief renders DM + pillars + luck; catalog is
  injected into the system prompt; history tail is included
- response_format={"type":"json_object"} is requested
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from ai.orchestrator import ChatMessage, ChatResult, ChatUsage, OrchestratorError
from ai.skill_router import select_skill
from ai.skills.models import SkillSelection
from calculator import calculate_chart
from calculator.models import ChartInput

# ── Fixtures ─────────────────────────────────────────────────────────────


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


def _ok_chat_result(text: str) -> ChatResult:
    return ChatResult(
        text=text,
        model="qwen3.6-35b-a3b",
        usage=ChatUsage(prompt_tokens=400, completion_tokens=120, total_tokens=520),
        latency_ms=1200,
        trace_id="test-trace",
        provider="yc",
    )


# ── Happy paths ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_select_skill_work_happy_path(
    monkeypatch: pytest.MonkeyPatch,
    reference_chart,  # type: ignore[no-untyped-def]
) -> None:
    captured: dict[str, Any] = {}

    async def fake_chat(**kwargs: Any) -> ChatResult:
        captured.update(kwargs)
        return _ok_chat_result(
            '{"skill":"work","confidence":0.92,'
            '"clarifying_questions":[],'
            '"needs_partner_chart":false,'
            '"concept_hints":["正官","столп месяца"],'
            '"reason":"явный карьерный вопрос"}'
        )

    monkeypatch.setattr("ai.skill_router.chat", fake_chat)
    sel = await select_skill(question="Стоит ли мне сменить работу?", chart=reference_chart)
    assert isinstance(sel, SkillSelection)
    assert sel.skill == "work"
    assert sel.confidence == pytest.approx(0.92)
    assert sel.concept_hints == ["正官", "столп месяца"]


@pytest.mark.asyncio
async def test_select_skill_relationships_needs_partner_chart(
    monkeypatch: pytest.MonkeyPatch,
    reference_chart,  # type: ignore[no-untyped-def]
) -> None:
    async def fake_chat(**_kwargs: Any) -> ChatResult:
        return _ok_chat_result(
            '{"skill":"relationships","confidence":0.95,'
            '"clarifying_questions":[],'
            '"needs_partner_chart":true,'
            '"concept_hints":["夫妻宫","桃花"],'
            '"reason":"вопрос про конкретного партнёра"}'
        )

    monkeypatch.setattr("ai.skill_router.chat", fake_chat)
    sel = await select_skill(question="Подходит ли мне мой парень?", chart=reference_chart)
    assert sel.skill == "relationships"
    assert sel.needs_partner_chart is True


@pytest.mark.asyncio
async def test_select_skill_risk_for_dangerous_period_question(
    monkeypatch: pytest.MonkeyPatch,
    reference_chart,  # type: ignore[no-untyped-def]
) -> None:
    """Wave 7: risk skill triggered on «опасный месяц / трудный период»
    style questions. Router must prefer `risk` over `time` (which would
    give a neutral year overview)."""

    async def fake_chat(**_kwargs: Any) -> ChatResult:
        return _ok_chat_result(
            '{"skill":"risk","confidence":0.94,'
            '"clarifying_questions":[],'
            '"needs_partner_chart":false,'
            '"concept_hints":["六冲","流月地支","3-vs-1"],'
            '"reason":"запрос на оценку опасных периодов — алгоритм 3-vs-1"}'
        )

    monkeypatch.setattr("ai.skill_router.chat", fake_chat)
    sel = await select_skill(
        question="Какой самый опасный месяц для меня в 2026 году?",
        chart=reference_chart,
    )
    assert sel.skill == "risk"
    assert sel.confidence == pytest.approx(0.94)
    assert "3-vs-1" in sel.concept_hints


@pytest.mark.asyncio
async def test_select_skill_with_clarifying_questions(
    monkeypatch: pytest.MonkeyPatch,
    reference_chart,  # type: ignore[no-untyped-def]
) -> None:
    async def fake_chat(**_kwargs: Any) -> ChatResult:
        return _ok_chat_result(
            '{"skill":"health","confidence":0.78,'
            '"clarifying_questions":["Болит чаще днём или ночью?","Хронически или внезапно?"],'
            '"needs_partner_chart":false,'
            '"concept_hints":["Огонь","Дерево"],'
            '"reason":"симптом требует уточнения"}'
        )

    monkeypatch.setattr("ai.skill_router.chat", fake_chat)
    sel = await select_skill(question="Голова болит", chart=reference_chart)
    assert sel.skill == "health"
    assert len(sel.clarifying_questions) == 2
    assert "днём" in sel.clarifying_questions[0]


# ── Robust JSON extraction ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_select_skill_strips_markdown_fences(
    monkeypatch: pytest.MonkeyPatch,
    reference_chart,  # type: ignore[no-untyped-def]
) -> None:
    """LLM sometimes wraps JSON in ```json ... ``` despite the prompt
    saying «no markdown». Router must extract the JSON anyway."""

    async def fake_chat(**_kwargs: Any) -> ChatResult:
        return _ok_chat_result(
            "Конечно, вот ответ:\n\n```json\n"
            '{"skill":"time","confidence":0.9,'
            '"clarifying_questions":[],'
            '"needs_partner_chart":false,'
            '"concept_hints":["大運"],'
            '"reason":"forecast"}'
            "\n```"
        )

    monkeypatch.setattr("ai.skill_router.chat", fake_chat)
    sel = await select_skill(question="Что меня ждёт?", chart=reference_chart)
    assert sel.skill == "time"


# ── Failure modes (all should fall back to default) ──────────────────────


@pytest.mark.asyncio
async def test_select_skill_falls_back_on_upstream_error(
    monkeypatch: pytest.MonkeyPatch,
    reference_chart,  # type: ignore[no-untyped-def]
) -> None:
    async def fake_chat(**_kwargs: Any) -> ChatResult:
        raise OrchestratorError("fake 4xx")

    monkeypatch.setattr("ai.skill_router.chat", fake_chat)
    sel = await select_skill(question="any", chart=reference_chart)
    assert sel.skill == "default"
    assert sel.confidence == 0.0
    assert "fallback" in sel.reason.lower()


@pytest.mark.asyncio
async def test_select_skill_falls_back_on_no_json(
    monkeypatch: pytest.MonkeyPatch,
    reference_chart,  # type: ignore[no-untyped-def]
) -> None:
    async def fake_chat(**_kwargs: Any) -> ChatResult:
        return _ok_chat_result("Я не могу определить skill для этого вопроса.")

    monkeypatch.setattr("ai.skill_router.chat", fake_chat)
    sel = await select_skill(question="any", chart=reference_chart)
    assert sel.skill == "default"
    assert "no_json" in sel.reason


@pytest.mark.asyncio
async def test_select_skill_falls_back_on_invalid_json(
    monkeypatch: pytest.MonkeyPatch,
    reference_chart,  # type: ignore[no-untyped-def]
) -> None:
    """Braces are balanced (regex extracts) but JSON is malformed
    (unquoted key) — json.loads must fail and we fall back."""

    async def fake_chat(**_kwargs: Any) -> ChatResult:
        return _ok_chat_result('{"skill": "work", confidence: 0.9, broken}')

    monkeypatch.setattr("ai.skill_router.chat", fake_chat)
    sel = await select_skill(question="any", chart=reference_chart)
    assert sel.skill == "default"
    assert "json_decode" in sel.reason


@pytest.mark.asyncio
async def test_select_skill_falls_back_on_invalid_schema(
    monkeypatch: pytest.MonkeyPatch,
    reference_chart,  # type: ignore[no-untyped-def]
) -> None:
    """Valid JSON, but with skill name outside the Literal SkillName."""

    async def fake_chat(**_kwargs: Any) -> ChatResult:
        return _ok_chat_result(
            '{"skill":"finance","confidence":0.5,'
            '"clarifying_questions":[],'
            '"needs_partner_chart":false,'
            '"concept_hints":[],'
            '"reason":"wrong skill name"}'
        )

    monkeypatch.setattr("ai.skill_router.chat", fake_chat)
    sel = await select_skill(question="any", chart=reference_chart)
    assert sel.skill == "default"
    assert "validation" in sel.reason


# ── Side-effects (what we pass to chat) ──────────────────────────────────


@pytest.mark.asyncio
async def test_select_skill_omits_response_format(
    monkeypatch: pytest.MonkeyPatch,
    reference_chart,  # type: ignore[no-untyped-def]
) -> None:
    # YC AI Studio rejects `response_format` with "Failed to parse model URI"
    # (live regression 2026-05-20). Skill router must NOT send this field —
    # JSON shape is enforced by the system prompt + repaired by `_extract_json`.
    captured: dict[str, Any] = {}

    async def fake_chat(**kwargs: Any) -> ChatResult:
        captured.update(kwargs)
        return _ok_chat_result(
            '{"skill":"default","confidence":0.5,'
            '"clarifying_questions":[],'
            '"needs_partner_chart":false,'
            '"concept_hints":[],'
            '"reason":"x"}'
        )

    monkeypatch.setattr("ai.skill_router.chat", fake_chat)
    await select_skill(question="x", chart=reference_chart)
    assert "response_format" not in captured
    assert captured["temperature"] == pytest.approx(0.1)
    assert captured["provider"] == "yc"


@pytest.mark.asyncio
async def test_select_skill_injects_catalog_and_chart_brief(
    monkeypatch: pytest.MonkeyPatch,
    reference_chart,  # type: ignore[no-untyped-def]
) -> None:
    captured: dict[str, Any] = {}

    async def fake_chat(**kwargs: Any) -> ChatResult:
        captured.update(kwargs)
        return _ok_chat_result(
            '{"skill":"work","confidence":0.6,'
            '"clarifying_questions":[],'
            '"needs_partner_chart":false,'
            '"concept_hints":[],'
            '"reason":"x"}'
        )

    monkeypatch.setattr("ai.skill_router.chat", fake_chat)
    await select_skill(question="вопрос про работу", chart=reference_chart)

    messages: list[ChatMessage] = captured["messages"]
    assert messages[0].role == "system"
    # Catalog substituted into the {catalog} placeholder
    assert "- **work**:" in messages[0].content
    assert "- **relationships**:" in messages[0].content
    # User message carries question + chart brief
    user_msg = messages[-1]
    assert user_msg.role == "user"
    assert "вопрос про работу" in user_msg.content
    assert "Дневной Мастер:" in user_msg.content
    assert "Столпы" in user_msg.content


@pytest.mark.asyncio
async def test_select_skill_history_tail_passed(
    monkeypatch: pytest.MonkeyPatch,
    reference_chart,  # type: ignore[no-untyped-def]
) -> None:
    """History longer than tail is truncated; only last N messages reach the router."""
    captured: dict[str, Any] = {}

    async def fake_chat(**kwargs: Any) -> ChatResult:
        captured.update(kwargs)
        return _ok_chat_result(
            '{"skill":"default","confidence":0.5,'
            '"clarifying_questions":[],'
            '"needs_partner_chart":false,'
            '"concept_hints":[],'
            '"reason":"x"}'
        )

    monkeypatch.setattr("ai.skill_router.chat", fake_chat)
    long_history = [ChatMessage(role="user", content=f"msg{i}") for i in range(10)]
    await select_skill(question="продолжи", chart=reference_chart, history=long_history)

    messages: list[ChatMessage] = captured["messages"]
    # 1 system + tail (4) + 1 user = 6
    assert len(messages) == 6
    # Tail should be msg6..msg9 (last 4)
    history_contents = [m.content for m in messages[1:5]]
    assert history_contents == ["msg6", "msg7", "msg8", "msg9"]


def test_router_prompt_forbids_asking_chart_known_data() -> None:
    """Bug A (2026-06-02): the router system prompt must explicitly forbid
    clarifying questions that ask for data already in the chart (birth
    date/year/time, gender, current luck pillar/такт)."""
    from ai.prompts import load_skill_router_prompt

    prompt = load_skill_router_prompt()
    assert "ТЕКУЩИЙ АКТИВНЫЙ ТАКТ" in prompt
    assert "Уточните ваш год рождения и текущий активный такт?" in prompt
