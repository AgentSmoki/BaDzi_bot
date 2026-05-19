"""Tests for the Wave 6 / Phase 5 additions to ai.temporal_context.compose_messages.

Covers the new optional sections:
- ``[PARTNER_CHART]`` when ``partner_chart`` is passed
- ``[SKILL: <name>]`` when ``skill_spec`` is passed
- ``[CLARIFICATIONS]`` when ``clarifications`` is passed
- ``concept_hints`` is forwarded to ``load_knowledge_for_question``

Backward-compat: existing callers (base_interpretation, calendar) that
pass none of the new kwargs must produce the unchanged section layout.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from ai.skills.models import SkillSpec
from ai.temporal_context import compose_messages
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


@pytest.fixture
def partner_chart():  # type: ignore[no-untyped-def]
    """A clearly distinct partner chart so we can tell sections apart."""
    return calculate_chart(
        ChartInput(
            birth_datetime=datetime(1988, 4, 27, 7, 3),
            latitude=44.6166,
            longitude=33.5254,
            tz_offset=3.0,
            early_rat=False,
            gender="male",
        )
    )


def _user_body(msgs: Any) -> str:
    return msgs[-1].content


# ── New sections ─────────────────────────────────────────────────────────


def test_skill_section_emitted_when_skill_spec_passed(reference_chart) -> None:  # type: ignore[no-untyped-def]
    spec = SkillSpec(
        name="work",
        description="карьера",
        body="При ответе используй столп месяца.",
    )
    msgs = compose_messages(
        system_prompt="anastasia",
        chart=reference_chart,
        question="как мне сейчас в работе?",
        skill_spec=spec,
    )
    body = _user_body(msgs)
    assert "[SKILL: work]" in body
    assert "При ответе используй столп месяца." in body
    assert "[/SKILL]" in body


def test_partner_chart_section_emitted(reference_chart, partner_chart) -> None:  # type: ignore[no-untyped-def]
    msgs = compose_messages(
        system_prompt="anastasia",
        chart=reference_chart,
        question="сравни нас с партнёром",
        partner_chart=partner_chart,
    )
    body = _user_body(msgs)
    assert "[PARTNER_CHART]" in body
    assert "[/PARTNER_CHART]" in body
    # Partner chart has a different day master than the natal chart — confirm
    # we rendered the partner one, not duplicated the natal one.
    assert "[BAZI_DATA]" in body
    assert body.index("[BAZI_DATA]") < body.index("[PARTNER_CHART]")


def test_clarifications_section_formats_q_and_a(reference_chart) -> None:  # type: ignore[no-untyped-def]
    msgs = compose_messages(
        system_prompt="anastasia",
        chart=reference_chart,
        question="что меня ждёт?",
        clarifications=[
            ("Какая сфера?", "карьера"),
            ("На какой период?", "этот год"),
        ],
    )
    body = _user_body(msgs)
    assert "[CLARIFICATIONS]" in body
    assert "- Q: Какая сфера?" in body
    assert "  A: карьера" in body
    assert "- Q: На какой период?" in body
    assert "  A: этот год" in body
    assert "[/CLARIFICATIONS]" in body


def test_clarifications_empty_list_omits_section(reference_chart) -> None:  # type: ignore[no-untyped-def]
    msgs = compose_messages(
        system_prompt="anastasia",
        chart=reference_chart,
        question="x",
        clarifications=[],
    )
    assert "[CLARIFICATIONS]" not in _user_body(msgs)


# ── concept_hints forwarding to RAG ──────────────────────────────────────


def test_concept_hints_forwarded_to_knowledge_loader(
    monkeypatch: pytest.MonkeyPatch,
    reference_chart,  # type: ignore[no-untyped-def]
) -> None:
    captured: dict[str, Any] = {}

    def fake_loader(
        question: str, *, top_k: int = 5, concept_hints: list[str] | None = None
    ) -> str:
        captured["question"] = question
        captured["concept_hints"] = concept_hints
        return ""  # empty so the section is skipped

    monkeypatch.setattr("ai.temporal_context.load_knowledge_for_question", fake_loader)

    compose_messages(
        system_prompt="anastasia",
        chart=reference_chart,
        question="карьера",
        concept_hints=["正官", "столп месяца"],
    )
    assert captured["concept_hints"] == ["正官", "столп месяца"]


def test_concept_hints_default_is_none(
    monkeypatch: pytest.MonkeyPatch,
    reference_chart,  # type: ignore[no-untyped-def]
) -> None:
    """Legacy callers that don't pass concept_hints must result in
    ``concept_hints=None`` reaching the loader, not [] or anything else."""
    captured: dict[str, Any] = {}

    def fake_loader(
        question: str, *, top_k: int = 5, concept_hints: list[str] | None = None
    ) -> str:
        captured["concept_hints"] = concept_hints
        return ""

    monkeypatch.setattr("ai.temporal_context.load_knowledge_for_question", fake_loader)
    compose_messages(system_prompt="anastasia", chart=reference_chart, question="x")
    assert captured["concept_hints"] is None


# ── Section order ────────────────────────────────────────────────────────


def test_section_order_when_all_present(reference_chart, partner_chart) -> None:  # type: ignore[no-untyped-def]
    """Spec: BAZI_DATA → PARTNER_CHART → CURRENT_MOMENT → SKILL →
    CLARIFICATIONS → INSTRUCTIONS → QUESTION."""
    spec = SkillSpec(
        name="relationships",
        description="отношения",
        body="skill body content",
    )
    msgs = compose_messages(
        system_prompt="anastasia",
        chart=reference_chart,
        question="он мне подходит?",
        partner_chart=partner_chart,
        include_temporal=True,
        skill_spec=spec,
        clarifications=[("Сколько вместе?", "год")],
    )
    body = _user_body(msgs)
    order = [
        body.index("[BAZI_DATA]"),
        body.index("[PARTNER_CHART]"),
        body.index("[CURRENT_MOMENT]"),
        body.index("[SKILL: relationships]"),
        body.index("[CLARIFICATIONS]"),
        body.index("[INSTRUCTIONS]"),
        body.index("[QUESTION]"),
    ]
    assert order == sorted(order), f"sections out of order: {order}"


# ── Backward compatibility ───────────────────────────────────────────────


def test_legacy_call_signature_works_without_skill_kwargs(reference_chart) -> None:  # type: ignore[no-untyped-def]
    """base_interpretation.py / calendar callers must keep working with
    no Wave-6 kwargs and produce no new sections."""
    msgs = compose_messages(
        system_prompt="anastasia",
        chart=reference_chart,
        question="вопрос",
    )
    body = _user_body(msgs)
    assert "[SKILL" not in body
    assert "[PARTNER_CHART]" not in body
    assert "[CLARIFICATIONS]" not in body
    # Original layout preserved.
    assert "[BAZI_DATA]" in body
    assert "[INSTRUCTIONS]" in body
    assert "[QUESTION]" in body
