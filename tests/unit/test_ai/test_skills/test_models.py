"""Tests for ai.skills.models — Pydantic validation rules.

Loader-level tests (file parsing, fallback) live in test_loader.py.
This file only covers schema constraints.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ai.skills.models import SkillSelection, SkillSpec

# ── SkillSpec ────────────────────────────────────────────────────────────


def test_skill_spec_minimal_valid() -> None:
    spec = SkillSpec(name="work", description="карьера", body="instructions")
    assert spec.name == "work"
    assert spec.description == "карьера"
    assert spec.body == "instructions"
    assert spec.trigger_keywords == []
    assert spec.required_inputs == []
    assert spec.ui_actions == []


def test_skill_spec_invalid_name_rejected() -> None:
    with pytest.raises(ValidationError):
        SkillSpec(name="finance", description="x", body="y")  # type: ignore[arg-type]


def test_skill_spec_is_frozen() -> None:
    spec = SkillSpec(name="health", description="d", body="b")
    with pytest.raises(ValidationError):
        spec.description = "mutated"  # type: ignore[misc]


# ── SkillSelection ───────────────────────────────────────────────────────


def test_skill_selection_minimal_valid() -> None:
    sel = SkillSelection(skill="time", confidence=0.85, reason="temporal kwd")
    assert sel.skill == "time"
    assert sel.confidence == 0.85
    assert sel.clarifying_questions == []
    assert sel.needs_partner_chart is False
    assert sel.concept_hints == []


def test_skill_selection_confidence_clamped() -> None:
    """confidence must be 0..1."""
    with pytest.raises(ValidationError):
        SkillSelection(skill="work", confidence=1.5, reason="x")
    with pytest.raises(ValidationError):
        SkillSelection(skill="work", confidence=-0.1, reason="x")


def test_skill_selection_clarifying_questions_max_three() -> None:
    with pytest.raises(ValidationError):
        SkillSelection(
            skill="work",
            confidence=0.5,
            reason="x",
            clarifying_questions=["a", "b", "c", "d"],
        )


def test_skill_selection_concept_hints_max_ten() -> None:
    with pytest.raises(ValidationError):
        SkillSelection(
            skill="time",
            confidence=0.7,
            reason="x",
            concept_hints=[f"c{i}" for i in range(11)],
        )


def test_skill_selection_json_roundtrip() -> None:
    """SkillSelection.model_validate_json should parse LLM router output."""
    payload = (
        '{"skill":"relationships","confidence":0.92,'
        '"clarifying_questions":["Какой это период?"],'
        '"needs_partner_chart":true,'
        '"concept_hints":["桃花","正官"],'
        '"reason":"asked about marriage"}'
    )
    sel = SkillSelection.model_validate_json(payload)
    assert sel.skill == "relationships"
    assert sel.needs_partner_chart is True
    assert sel.clarifying_questions == ["Какой это период?"]
    assert sel.concept_hints == ["桃花", "正官"]


def test_skill_selection_is_frozen() -> None:
    sel = SkillSelection(skill="default", confidence=0.0, reason="x")
    with pytest.raises(ValidationError):
        sel.confidence = 0.9  # type: ignore[misc]
