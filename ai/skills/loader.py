"""Load skill .md files from ``ai/skills/`` directory.

A skill file looks like::

    ---
    name: relationships
    description: Партнёрство, брак, совместимость
    trigger_keywords: [партнёр, супруг, отношения]
    required_inputs: [partner_chart_optional]
    ui_actions: [compare_partner_chart]
    ---
    # Skill body in markdown...

Public API:
- ``load_skill(name) -> SkillSpec``  — cached, raises on missing/invalid
- ``list_skills() -> list[SkillSpec]`` — all built-in skills, cached

The loader is sync (file I/O on small static files) — skills load
once on startup and stay in ``lru_cache``.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path
from typing import Final, cast, get_args

import yaml
from pydantic import ValidationError

from ai.skills.models import SkillName, SkillSpec

_SKILLS_DIR: Final = Path(__file__).resolve().parent

_FRONTMATTER_RE: Final = re.compile(
    r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z",
    re.DOTALL,
)
"""Standard YAML frontmatter: ``---\\n<yaml>\\n---\\n<body>``.
``\\A`` / ``\\Z`` anchor to whole-string to avoid accidental matches
inside a body containing ``---`` separators."""


class SkillFileError(Exception):
    """Raised when a skill file is malformed (missing frontmatter,
    invalid YAML, missing required fields). Caller decides whether
    to surface or fall back to ``default``."""


def _parse_skill_file(path: Path) -> SkillSpec:
    """Read ``path`` as a skill .md, parse frontmatter+body, validate
    via ``SkillSpec``. Raises ``SkillFileError`` on any structural
    problem so the loader can return a clean error message."""
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise SkillFileError(f"cannot read {path}: {exc}") from exc

    match = _FRONTMATTER_RE.match(raw)
    if not match:
        raise SkillFileError(
            f"{path.name}: missing YAML frontmatter (expected '---' fences at top)"
        )

    fm_text, body = match.group(1), match.group(2).strip()
    if not body:
        raise SkillFileError(f"{path.name}: body is empty (only frontmatter present)")

    try:
        fm_data = yaml.safe_load(fm_text)
    except yaml.YAMLError as exc:
        raise SkillFileError(f"{path.name}: invalid YAML frontmatter: {exc}") from exc

    if not isinstance(fm_data, dict):
        raise SkillFileError(
            f"{path.name}: frontmatter must be a mapping, got {type(fm_data).__name__}"
        )

    try:
        return SkillSpec(**fm_data, body=body)
    except ValidationError as exc:
        raise SkillFileError(f"{path.name}: frontmatter validation failed: {exc}") from exc


@lru_cache(maxsize=8)
def load_skill(name: SkillName) -> SkillSpec:
    """Return the skill named ``name``, parsed and validated.

    Cached: skills are static at runtime, the file read happens once
    per process. Raises ``SkillFileError`` if the file is missing or
    malformed — caller should fall back to ``default``.
    """
    path = _SKILLS_DIR / f"{name}.md"
    if not path.is_file():
        raise SkillFileError(f"skill file not found: {path}")
    return _parse_skill_file(path)


@lru_cache(maxsize=1)
def list_skills() -> tuple[SkillSpec, ...]:
    """Return all built-in skills as a frozen tuple.

    Used by ``ai.skill_router`` to render the catalog inside the fast-
    router system prompt. Tuple (not list) so the ``lru_cache`` return
    value stays hashable and immutable.

    Skills that fail to load raise — refuse to start with a broken
    catalog rather than silently degrade.
    """
    names = cast(tuple[SkillName, ...], get_args(SkillName))
    return tuple(load_skill(n) for n in names)
