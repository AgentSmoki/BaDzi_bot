"""Pydantic models for the skill catalog and fast-router output.

``SkillSpec`` describes one skill's metadata + body. Loaded from
``ai/skills/<name>.md`` by ``ai.skills.loader.load_skill``.

``SkillSelection`` is the JSON shape the fast-LLM router returns for
one user question. Parsed via ``model_validate_json`` from the router
response.

Both models are frozen at construction (``ConfigDict(frozen=True)``)
so they can be cached and passed safely between async tasks.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

SkillName = Literal["work", "relationships", "health", "time", "risk", "default"]
"""The fixed enum of skill identifiers. Adding a new skill = add to
this Literal + create ``ai/skills/<name>.md``.

``risk`` (Wave 7) handles dangerous-period questions via the 3-vs-1
chain-of-thought from the Мастер ЭдоХа school — accumulated branches
beat lone 六冲 clashes in danger ranking."""


class SkillSpec(BaseModel):
    """One skill, loaded from its .md file.

    The ``body`` is the human-language instruction that gets injected
    into the main LLM prompt as the ``[SKILL]`` section. Everything
    else is metadata used by the router (in its catalog prompt) and
    by the handler (e.g. ``ui_actions`` triggers the partner-chart
    button)."""

    model_config = ConfigDict(frozen=True)

    name: SkillName
    description: str
    """One-sentence summary shown to the router LLM in the catalog."""
    trigger_keywords: list[str] = Field(default_factory=list)
    """Hint vocabulary for the router (not used as a hard rule —
    LLM decides; keywords just help its few-shot reasoning)."""
    required_inputs: list[str] = Field(default_factory=list)
    """Tokens like ``partner_chart_optional`` / ``current_moment``.
    Currently advisory; handler interprets specific values."""
    ui_actions: list[str] = Field(default_factory=list)
    """UI side-effects this skill may trigger, e.g.
    ``compare_partner_chart`` (handler shows the «Add partner chart»
    button)."""
    body: str
    """Full markdown instructions injected into [SKILL] block."""


class SkillSelection(BaseModel):
    """Fast-router output for one user turn.

    The router LLM returns this as JSON; we ``model_validate_json``
    it. On parse failure the handler falls back to
    ``SkillSelection(skill="default", confidence=0.0, ...)``.
    """

    model_config = ConfigDict(frozen=True)

    skill: SkillName
    confidence: float = Field(ge=0.0, le=1.0)
    """Router's self-rated confidence. Handler may downgrade to
    ``default`` if below a threshold (e.g. 0.4)."""
    clarifying_questions: list[str] = Field(default_factory=list, max_length=3)
    """0-3 questions to ask the user before invoking the main LLM.
    Empty list = enough context, proceed directly."""
    needs_partner_chart: bool = False
    """``True`` only when ``skill == "relationships"`` and the user
    asked about a specific person ("my husband", "my girlfriend").
    Handler will offer the «Add partner chart» button."""
    concept_hints: list[str] = Field(default_factory=list, max_length=10)
    """Chinese terms / star names / interaction types extracted from
    the question. Passed to ``ai.rag.public.load_knowledge_for_question``
    as ranking boost so the KuzuDB retriever pulls relevant nodes."""
    reason: str
    """One-sentence explanation. Logged to ``consultation.completed``
    for /admin debugging."""
