"""Tests for ai.skills.loader — file parsing + error handling.

Uses the real built-in skill files in ``ai/skills/*.md`` for happy
paths, and ``tmp_path`` for malformed-file scenarios.
"""

from __future__ import annotations

from pathlib import Path
from typing import get_args

import pytest

from ai.skills import loader as loader_module
from ai.skills.loader import SkillFileError, _parse_skill_file, list_skills, load_skill
from ai.skills.models import SkillName, SkillSpec

# ── Happy paths against real built-in files ──────────────────────────────


@pytest.mark.parametrize("name", list(get_args(SkillName)))
def test_load_skill_happy_path(name: SkillName) -> None:
    """Every built-in skill must load cleanly."""
    spec = load_skill(name)
    assert isinstance(spec, SkillSpec)
    assert spec.name == name
    assert spec.description  # non-empty
    assert spec.body  # non-empty
    assert "# Skill" in spec.body or "Универсальный" in spec.body


def test_list_skills_returns_all_five() -> None:
    skills = list_skills()
    assert len(skills) == 5
    names = {s.name for s in skills}
    assert names == {"work", "relationships", "health", "time", "default"}


def test_list_skills_is_tuple_for_cache_safety() -> None:
    """``lru_cache`` return must be hashable — tuple, not list."""
    assert isinstance(list_skills(), tuple)


def test_list_skills_returns_skill_specs() -> None:
    for s in list_skills():
        assert isinstance(s, SkillSpec)


def test_relationships_has_ui_action_for_partner_button() -> None:
    """Relationships skill drives the «Add partner chart» button —
    its frontmatter must declare the action so the handler can detect it."""
    spec = load_skill("relationships")
    assert "compare_partner_chart" in spec.ui_actions


# ── Error handling against tmp_path ──────────────────────────────────────


def test_parse_missing_frontmatter_raises(tmp_path: Path) -> None:
    p = tmp_path / "broken.md"
    p.write_text("# No frontmatter here\nJust body.", encoding="utf-8")
    with pytest.raises(SkillFileError, match="missing YAML frontmatter"):
        _parse_skill_file(p)


def test_parse_invalid_yaml_raises(tmp_path: Path) -> None:
    p = tmp_path / "bad_yaml.md"
    p.write_text("---\nname: work\n  bad: indentation: here\n---\nbody", encoding="utf-8")
    with pytest.raises(SkillFileError, match="invalid YAML frontmatter"):
        _parse_skill_file(p)


def test_parse_empty_body_raises(tmp_path: Path) -> None:
    p = tmp_path / "no_body.md"
    p.write_text("---\nname: work\ndescription: d\n---\n", encoding="utf-8")
    with pytest.raises(SkillFileError, match="body is empty"):
        _parse_skill_file(p)


def test_parse_invalid_skill_name_raises(tmp_path: Path) -> None:
    """Frontmatter ``name`` must be one of the Literal SkillName values."""
    p = tmp_path / "wrong_name.md"
    p.write_text(
        "---\nname: finance\ndescription: x\n---\nbody",
        encoding="utf-8",
    )
    with pytest.raises(SkillFileError, match="validation failed"):
        _parse_skill_file(p)


def test_parse_non_mapping_frontmatter_raises(tmp_path: Path) -> None:
    """A scalar or list in frontmatter (e.g. just a string) is not a valid spec."""
    p = tmp_path / "scalar_fm.md"
    p.write_text("---\njust a string\n---\nbody", encoding="utf-8")
    with pytest.raises(SkillFileError, match="must be a mapping"):
        _parse_skill_file(p)


def test_load_skill_missing_file_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Point the loader at an empty directory — every load_skill must fail."""
    monkeypatch.setattr(loader_module, "_SKILLS_DIR", tmp_path)
    load_skill.cache_clear()
    try:
        with pytest.raises(SkillFileError, match="skill file not found"):
            load_skill("work")
    finally:
        load_skill.cache_clear()


# ── Caching ──────────────────────────────────────────────────────────────


def test_load_skill_is_cached() -> None:
    """Second call must hit lru_cache, not re-parse the file."""
    a = load_skill("default")
    b = load_skill("default")
    assert a is b  # identity check — only possible with cache hit
