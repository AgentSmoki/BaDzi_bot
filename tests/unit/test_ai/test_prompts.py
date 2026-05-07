"""Loader tests for ai.prompts. The 68 KB Anastasia prompt itself
isn't validated here — we just check the loader works, returns the
real file, and caches subsequent reads."""

from __future__ import annotations

import pytest

from ai.prompts import ANASTASIA_SYSTEM, get_prompt, load_system_prompt


def test_load_system_prompt_returns_anastasia_file() -> None:
    text = load_system_prompt()
    # File is ~39k chars (~68 KB on disk — Cyrillic is 2 bytes in UTF-8).
    # Bound is loose so trimming the prompt later doesn't break the test.
    assert len(text) > 30_000
    # Persona signature lives in the first lines of v2.0
    assert "АНАСТАСИЯ" in text or "Анастасия" in text


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
