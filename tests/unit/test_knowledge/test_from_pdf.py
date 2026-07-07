"""Tests for knowledge.ingest.from_pdf — TOC + chunk prompt builders."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from knowledge.ingest.from_pdf import (
    TocEntry,
    load_toc,
    render_chunk_prompt,
    render_toc_prompt,
    slice_body_by_pages,
    target_path_for,
    toc_path_for,
)

_PDF_TEXT = """<!-- page 1 -->
Глава 1 текст
страница 1 продолжение

<!-- page 2 -->
Страница 2 контент

<!-- page 3 -->
Страница 3 контент

<!-- page 4 -->
Страница 4 контент
"""


@pytest.fixture
def pdf_md(tmp_path: Path) -> Path:
    """A minimal PDF-extracted .md with page markers."""
    kb_root = tmp_path / "kb"
    (kb_root / "_audio_transcripts").mkdir(parents=True)
    p = kb_root / "_audio_transcripts" / "course.md"
    p.write_text(_PDF_TEXT, encoding="utf-8")
    return p


def test_slice_by_pages_inclusive_range(pdf_md: Path) -> None:
    text = pdf_md.read_text(encoding="utf-8")
    slc = slice_body_by_pages(text, 2, 3)
    assert "Страница 2" in slc
    assert "Страница 3" in slc
    assert "Страница 4" not in slc
    assert "Глава 1" not in slc


def test_slice_single_page(pdf_md: Path) -> None:
    text = pdf_md.read_text(encoding="utf-8")
    slc = slice_body_by_pages(text, 1, 1)
    assert "Глава 1" in slc
    assert "Страница 2" not in slc


def test_slice_unknown_page_returns_empty(pdf_md: Path) -> None:
    text = pdf_md.read_text(encoding="utf-8")
    assert slice_body_by_pages(text, 99, 100) == ""


def test_slice_no_markers_returns_empty() -> None:
    assert slice_body_by_pages("no markers here", 1, 5) == ""


def test_toc_path_is_sibling_with_toc_json_suffix(pdf_md: Path) -> None:
    p = toc_path_for(pdf_md)
    assert p.name == "course.toc.json"
    assert p.parent == pdf_md.parent


def test_render_toc_prompt_contains_contract(pdf_md: Path) -> None:
    prompt = render_toc_prompt(pdf_md, max_chapters=20)
    # Output contract requires Write + valid JSON
    assert "Write" in prompt
    assert "JSON" in prompt
    # The level scale must be in the prompt so the subagent classifies correctly
    for level in ("L1", "L2", "L3", "L4", "L5", "L6", "L7"):
        assert level in prompt
    # The output path must be referenced
    assert str(toc_path_for(pdf_md)) in prompt
    # Body must be included in prompt
    assert "Глава 1 текст" in prompt


def _entry(**kw: object) -> TocEntry:
    base = {
        "chapter_no": 1,
        "title": "Test",
        "page_start": 1,
        "page_end": 2,
        "level": 1,
        "topic": "foundations",
        "related_concepts": ["a", "b"],
        "summary": "test summary",
        "target_folder": "L1_foundational",
        "target_filename": "01_test.md",
    }
    base.update(kw)
    return TocEntry.from_dict(base)


def test_toc_entry_rejects_invalid_level() -> None:
    with pytest.raises(ValueError, match="invalid level"):
        _entry(level=99)


def test_target_path_for_lands_under_kb_root(pdf_md: Path) -> None:
    """The target .md should live under the KB root (the parent of
    _audio_transcripts/), not next to the PDF.md."""
    entry = _entry(target_folder="L2_atoms/stems", target_filename="03_xyz.md")
    target = target_path_for(entry, pdf_md)
    # kb_root = pdf_md.parents[1] in the fixture
    assert target == pdf_md.parents[1] / "L2_atoms" / "stems" / "03_xyz.md"


def test_render_chunk_prompt_contains_frontmatter_template(pdf_md: Path) -> None:
    entry = _entry()
    prompt = render_chunk_prompt(entry, "тело главы", pdf_md)
    assert "level: L1" in prompt
    assert "topic: foundations" in prompt
    assert "source_authority: 9" in prompt
    assert "тело главы" in prompt
    assert str(target_path_for(entry, pdf_md)) in prompt


def test_load_toc_skips_invalid_rows(tmp_path: Path) -> None:
    p = tmp_path / "toc.json"
    p.write_text(
        json.dumps(
            [
                {
                    "chapter_no": 1,
                    "title": "OK",
                    "page_start": 1,
                    "page_end": 5,
                    "level": 1,
                    "topic": "foundations",
                    "related_concepts": ["x"],
                    "summary": "s",
                    "target_folder": "L1_foundational",
                    "target_filename": "01.md",
                },
                "not a dict",
                {"chapter_no": 2, "level": 99, "title": "bad level"},
                {
                    "chapter_no": 3,
                    "title": "OK2",
                    "page_start": 6,
                    "page_end": 9,
                    "level": 2,
                    "topic": "atoms",
                    "related_concepts": [],
                    "summary": "",
                    "target_folder": "L2_atoms",
                    "target_filename": "03.md",
                },
            ]
        ),
        encoding="utf-8",
    )
    entries = load_toc(p)
    assert len(entries) == 2
    assert entries[0].chapter_no == 1
    assert entries[1].chapter_no == 3


def test_load_toc_raises_when_not_a_list(tmp_path: Path) -> None:
    p = tmp_path / "toc.json"
    p.write_text('{"not": "an array"}', encoding="utf-8")
    with pytest.raises(ValueError, match="JSON array"):
        load_toc(p)
