"""Tests for knowledge.ingest.parser."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from knowledge.ingest.parser import parse_md_file, scan_kb

_VALID = """\
---
level: L7
topic: relationships
title: Тестовое правило
related_concepts:
  - taohua
  - day_master_strength
applicable_when:
  - dm_yin_water
source: lesson_2024_03_15
source_authority: 9
last_updated: 2026-05-17
---

# Тестовое правило

Тело правила.
"""


def _write(path: Path, content: str = _VALID) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_parses_valid_md_to_ingested_doc(tmp_path: Path) -> None:
    p = _write(tmp_path / "L7_predictive_patterns/relationships/01.md")
    doc = parse_md_file(p, kb_root=tmp_path)
    assert doc is not None
    assert doc.level == 7
    assert doc.title == "Тестовое правило"
    assert doc.topic == "relationships"
    assert doc.node_id == "L7_predictive_patterns/relationships/01"
    assert "taohua" in doc.related_concepts
    assert doc.source_authority == 9


# ── Wave 7 Phase 5 — school frontmatter handling ─────────────────────────


def test_parse_school_defaults_to_universal_when_omitted(tmp_path: Path) -> None:
    """Legacy docs (pre-Phase-5) don't carry the `school:` key. Parser
    must default to ``universal`` so re-ingest doesn't drop them."""
    p = _write(tmp_path / "legacy.md")
    doc = parse_md_file(p, kb_root=tmp_path)
    assert doc is not None
    assert doc.school == "universal"


@pytest.mark.parametrize("school", ["universal", "classic", "edoha", "modern"])
def test_parse_school_explicit_value_round_trips(tmp_path: Path, school: str) -> None:
    """All four valid school values are accepted verbatim."""
    content = _VALID.replace(
        "source_authority: 9",
        f"source_authority: 9\nschool: {school}",
    )
    p = _write(tmp_path / f"{school}.md", content)
    doc = parse_md_file(p, kb_root=tmp_path)
    assert doc is not None
    assert doc.school == school


def test_parse_school_unknown_value_falls_back_to_universal(tmp_path: Path) -> None:
    """Typos like ``school: clasic`` shouldn't poison the graph — parser
    warns and substitutes the safe default."""
    content = _VALID.replace(
        "source_authority: 9",
        "source_authority: 9\nschool: bogus_school",
    )
    p = _write(tmp_path / "typo.md", content)
    doc = parse_md_file(p, kb_root=tmp_path)
    assert doc is not None
    assert doc.school == "universal"


def test_content_hash_is_sha256_of_body_only(tmp_path: Path) -> None:
    """Frontmatter edits must not invalidate the hash (only body counts)."""
    p = _write(tmp_path / "a.md")
    doc1 = parse_md_file(p, kb_root=tmp_path)
    assert doc1 is not None

    # Re-write with a different `title` in frontmatter, same body. We
    # only swap the `title:` line — the H1 heading "# Тестовое правило"
    # in the body stays as-is, so the body hash should not move.
    flipped = _VALID.replace("title: Тестовое правило", "title: Другое имя")
    _write(p, flipped)
    doc2 = parse_md_file(p, kb_root=tmp_path)
    assert doc2 is not None
    assert doc1.content_hash == doc2.content_hash

    # Direct sanity: hash matches sha256 of the body the parser pulled out.
    assert doc1.content_hash == hashlib.sha256(doc1.body.encode("utf-8")).hexdigest()


def test_body_edit_changes_hash(tmp_path: Path) -> None:
    p = _write(tmp_path / "a.md")
    h1 = parse_md_file(p, kb_root=tmp_path).content_hash  # type: ignore[union-attr]
    edited = _VALID + "\nДополнительный абзац.\n"
    _write(p, edited)
    h2 = parse_md_file(p, kb_root=tmp_path).content_hash  # type: ignore[union-attr]
    assert h1 != h2


def test_missing_frontmatter_returns_none(tmp_path: Path) -> None:
    p = _write(tmp_path / "a.md", "no frontmatter here\n")
    assert parse_md_file(p, kb_root=tmp_path) is None


def test_bad_yaml_returns_none(tmp_path: Path) -> None:
    p = _write(tmp_path / "a.md", "---\n: : : not yaml\n---\nbody\n")
    assert parse_md_file(p, kb_root=tmp_path) is None


def test_bad_level_returns_none(tmp_path: Path) -> None:
    p = _write(
        tmp_path / "a.md",
        _VALID.replace("level: L7", "level: not_a_number"),
    )
    assert parse_md_file(p, kb_root=tmp_path) is None


def test_last_updated_string_accepted(tmp_path: Path) -> None:
    """YAML may give us an ISO string instead of a date object."""
    p = _write(
        tmp_path / "a.md",
        _VALID.replace("last_updated: 2026-05-17", 'last_updated: "2026-05-17T08:00:00Z"'),
    )
    doc = parse_md_file(p, kb_root=tmp_path)
    assert doc is not None
    assert doc.last_updated.year == 2026


def test_scan_kb_skips_readme_template_and_underscore_dirs(tmp_path: Path) -> None:
    _write(tmp_path / "L5_stars" / "a.md")
    _write(tmp_path / "README.md", "ignore me")
    _write(tmp_path / "_template.md", "ignore me")
    _write(tmp_path / "_audio_transcripts" / "raw.md")
    docs = scan_kb(tmp_path)
    assert len(docs) == 1
    assert docs[0].node_id == "L5_stars/a"


def test_scan_kb_missing_root_returns_empty(tmp_path: Path) -> None:
    assert scan_kb(tmp_path / "does_not_exist") == []


@pytest.mark.parametrize(
    "missing_field",
    ["level", "title", "related_concepts"],
)
def test_partial_frontmatter_does_not_crash(tmp_path: Path, missing_field: str) -> None:
    """Most fields are optional and default to safe values; only ``level``
    being non-numeric is a hard failure (tested separately)."""
    content = "\n".join(
        line
        for line in _VALID.splitlines()
        if not line.startswith(f"{missing_field}:")
        and missing_field not in line.split(":")[0].strip()
    )
    p = _write(tmp_path / "a.md", content)
    doc = parse_md_file(p, kb_root=tmp_path)
    if missing_field == "level":
        assert doc is None
    else:
        assert doc is not None
