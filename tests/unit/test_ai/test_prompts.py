"""Loader tests for ai.prompts. The 68 KB Anastasia prompt itself
isn't validated here — we just check the loader works, returns the
real file, and caches subsequent reads."""

from __future__ import annotations

import pytest

from ai.prompts import (
    ANASTASIA_SYSTEM,
    SchoolName,
    get_prompt,
    load_base_prompt,
    load_system_prompt,
)


def test_load_system_prompt_returns_anastasia_file() -> None:
    text = load_system_prompt()
    # File is ~39k chars (~68 KB on disk — Cyrillic is 2 bytes in UTF-8).
    # Bound is loose so trimming the prompt later doesn't break the test.
    assert len(text) > 30_000
    # Persona signature lives in the first lines of v2.0
    assert "ШИФУ" in text or "Шифу" in text


def test_load_system_prompt_is_cached() -> None:
    a = load_system_prompt()
    b = load_system_prompt()
    # Same string identity = served from lru_cache, no second disk read
    assert a is b


def test_get_prompt_unknown_name_raises() -> None:
    with pytest.raises(FileNotFoundError):
        get_prompt("does_not_exist_xyz")


def test_anastasia_constant_resolves() -> None:
    assert ANASTASIA_SYSTEM == "anastasia_system"
    # Can be used directly with get_prompt
    assert get_prompt(ANASTASIA_SYSTEM) == load_system_prompt()


# ── Wave 7 Phase 2 — three-school layered prompts ────────────────────────


def test_load_base_prompt_none_returns_base_only() -> None:
    """Backward-compat: callers that don't know the school (forecast,
    base_interpretation) get bare base.md with no methodology overlay."""
    text = load_base_prompt()
    assert "Шифу" in text
    # School overlay markers must NOT appear when school is None.
    assert "Школа 🎓 Классическая" not in text
    assert "Школа 🌀 Мастер ЭдоХа" not in text
    assert "Школа 🧬 Современная" not in text


@pytest.mark.parametrize(
    ("school", "marker"),
    [
        ("classic", "Школа 🎓 Классическая"),
        ("edoha", "Школа 🌀 Мастер ЭдоХа"),
        ("modern", "Школа 🧬 Современная"),
    ],
)
def test_load_base_prompt_with_school_appends_overlay(school: SchoolName, marker: str) -> None:
    """Each school selection concatenates base.md + base_<school>.md.
    The methodology marker (header from the overlay file) must appear
    and the universal core stays intact."""
    text = load_base_prompt(school=school)
    assert "Шифу" in text  # core persona kept
    assert marker in text  # overlay header injected
    # Layer separator between base and school overlay
    assert "---" in text


def test_load_base_prompt_school_is_cached() -> None:
    """lru_cache keys on the school argument — repeated calls hit cache."""
    a = load_base_prompt(school="edoha")
    b = load_base_prompt(school="edoha")
    assert a is b
    # Different schools give different identities
    c = load_base_prompt(school="classic")
    assert a is not c
