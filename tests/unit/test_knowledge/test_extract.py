"""Tests for knowledge.ingest.extract — heuristic + sidecar modes."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from knowledge.ingest.extract import (
    concept_node_id,
    extract_triplets,
    files_pending_extract,
    render_subagent_prompt,
    sidecar_path_for,
)
from knowledge.ingest.parser import parse_md_file

_DOC = """\
---
level: L7
topic: relationships
title: Тест
related_concepts:
  - taohua
  - day master strength
applicable_when:
  - dm_yin_water
source: t
source_authority: 7
last_updated: 2026-05-17
---

Body.
"""


@pytest.fixture
def doc_path(tmp_path: Path) -> Path:
    p = tmp_path / "L7_predictive_patterns/relationships/01.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_DOC, encoding="utf-8")
    return p


def test_heuristic_one_edge_per_concept(doc_path: Path) -> None:
    doc = parse_md_file(doc_path, kb_root=doc_path.parents[2])
    assert doc is not None
    triplets = extract_triplets(doc)
    assert len(triplets) == 2
    assert all(t.relation == "refers_to" for t in triplets)
    assert all(t.source == "frontmatter" for t in triplets)
    assert {t.object_node_id for t in triplets} == {
        "concept:taohua",
        "concept:day_master_strength",
    }


def test_concept_slug_normalises_spaces_and_unicode() -> None:
    assert concept_node_id("Day Master Strength") == "concept:day_master_strength"
    assert concept_node_id("Белый Тигр") == "concept:белый_тигр"
    assert concept_node_id("白虎") == "concept:白虎"
    assert concept_node_id("  ") == "concept:unknown"


def test_sidecar_overrides_heuristic(doc_path: Path) -> None:
    doc = parse_md_file(doc_path, kb_root=doc_path.parents[2])
    assert doc is not None
    side = sidecar_path_for(doc_path)
    side.write_text(
        json.dumps(
            [
                {"subject": doc.node_id, "relation": "clashes_with", "object": "concept:liuchong"},
                {"subject": doc.node_id, "relation": "example_of", "object": "concept:taohua"},
            ]
        ),
        encoding="utf-8",
    )
    triplets = extract_triplets(doc)
    assert len(triplets) == 2
    assert {t.relation for t in triplets} == {"clashes_with", "example_of"}
    assert all(t.source == "subagent" for t in triplets)


def test_sidecar_bad_json_falls_back_to_heuristic(doc_path: Path) -> None:
    doc = parse_md_file(doc_path, kb_root=doc_path.parents[2])
    assert doc is not None
    sidecar_path_for(doc_path).write_text("{ not json", encoding="utf-8")
    triplets = extract_triplets(doc)
    assert len(triplets) == 2
    assert all(t.source == "frontmatter" for t in triplets)


def test_sidecar_drops_invalid_rows(doc_path: Path) -> None:
    """Rows with unknown relation or missing object are silently dropped."""
    doc = parse_md_file(doc_path, kb_root=doc_path.parents[2])
    assert doc is not None
    sidecar_path_for(doc_path).write_text(
        json.dumps(
            [
                {"subject": doc.node_id, "relation": "invented_relation", "object": "x"},
                {"subject": doc.node_id, "relation": "refers_to"},  # no object
                {"subject": doc.node_id, "relation": "refers_to", "object": "concept:good"},
            ]
        ),
        encoding="utf-8",
    )
    triplets = extract_triplets(doc)
    assert len(triplets) == 1
    assert triplets[0].object_node_id == "concept:good"


def test_files_pending_extract_excludes_sidecar_owners(doc_path: Path) -> None:
    kb_root = doc_path.parents[2]
    other = kb_root / "L5_stars" / "x.md"
    other.parent.mkdir(parents=True, exist_ok=True)
    other.write_text(_DOC, encoding="utf-8")
    sidecar_path_for(other).write_text("[]", encoding="utf-8")

    pending = files_pending_extract(kb_root)
    assert doc_path in pending
    assert other not in pending


def test_render_subagent_prompt_contains_contract(doc_path: Path) -> None:
    doc = parse_md_file(doc_path, kb_root=doc_path.parents[2])
    assert doc is not None
    prompt = render_subagent_prompt(doc)
    assert doc.node_id in prompt
    # Each relation kind must appear in the prompt's allow-list
    for rel in (
        "refers_to",
        "generates",
        "controls",
        "combines_with",
        "clashes_with",
        "example_of",
    ):
        assert rel in prompt
    assert str(sidecar_path_for(doc_path)) in prompt
