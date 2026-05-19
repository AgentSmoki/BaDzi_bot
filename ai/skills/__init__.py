"""Skill catalog for the fast-router-based AI flow (Wave 6, ADR-010).

A *skill* is a markdown file in ``ai/skills/<name>.md`` containing a
YAML frontmatter (metadata for the router) and a body (instructions
injected into the main LLM prompt as the ``[SKILL]`` section).

Five built-in skills:
- ``work``           — career, money, business questions
- ``relationships``  — partner, marriage, compatibility
- ``health``         — body systems, element balance, TCM
- ``time``           — forecasts, luck pillars, current period
- ``default``        — fallback for general / philosophical questions

Public API:
    from ai.skills import load_skill, list_skills, SkillName, SkillSpec, SkillSelection
"""

from __future__ import annotations

from ai.skills.loader import list_skills, load_skill
from ai.skills.models import SkillName, SkillSelection, SkillSpec

__all__ = [
    "SkillName",
    "SkillSelection",
    "SkillSpec",
    "list_skills",
    "load_skill",
]
