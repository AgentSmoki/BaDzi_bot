"""Integration tests for knowledge.ingest.writer — real KuzuDB upserts."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import kuzu
import pytest

from knowledge.bootstrap import bootstrap
from knowledge.ingest.models import IngestedDoc, IngestState, Triplet
from knowledge.ingest.writer import load_state, save_state, upsert_doc


def _make_doc(node_id: str = "L7_predictive_patterns/relationships/01") -> IngestedDoc:
    return IngestedDoc(
        path=Path(f"/virtual/{node_id}.md"),
        node_id=node_id,
        level=7,
        topic="relationships",
        title="Тест",
        body="body",
        summary="",
        source="lesson_2024",
        source_authority=9,
        applicable_when=("dm_yin_water",),
        related_concepts=("taohua",),
        last_updated=datetime(2026, 5, 17, tzinfo=UTC),
        content_hash="hash-1",
    )


@pytest.fixture
def conn(tmp_path: Path) -> kuzu.Connection:
    bootstrap(tmp_path / "kdb")
    db = kuzu.Database(str(tmp_path / "kdb"))
    return kuzu.Connection(db)


def _count(conn: kuzu.Connection, query: str) -> int:
    r = conn.execute(query)
    rows = []
    while r.has_next():  # type: ignore[union-attr]
        rows.append(r.get_next())  # type: ignore[union-attr]
    return rows[0][0] if rows else 0


def test_upsert_creates_main_node_and_edges(conn: kuzu.Connection) -> None:
    doc = _make_doc()
    triplets = [
        Triplet(doc.node_id, "refers_to", "concept:taohua", "frontmatter"),
        Triplet(doc.node_id, "clashes_with", "concept:liuchong", "subagent"),
    ]
    edges = upsert_doc(conn, doc, triplets)
    assert edges == 2
    # 1 main + 2 stubs = 3
    assert _count(conn, "MATCH (n:Node) RETURN count(n)") == 3
    assert _count(conn, "MATCH ()-[r:REFERS_TO]->() RETURN count(r)") == 1
    assert _count(conn, "MATCH ()-[r:CLASHES_WITH]->() RETURN count(r)") == 1


def test_upsert_is_idempotent(conn: kuzu.Connection) -> None:
    doc = _make_doc()
    t = [Triplet(doc.node_id, "refers_to", "concept:x", "frontmatter")]
    upsert_doc(conn, doc, t)
    upsert_doc(conn, doc, t)
    upsert_doc(conn, doc, t)
    # Re-upsert must REPLACE outgoing edges, not accumulate them
    assert _count(conn, "MATCH ()-[r:REFERS_TO]->() RETURN count(r)") == 1
    assert _count(conn, "MATCH (n:Node) RETURN count(n)") == 2


def test_upsert_replaces_changed_triplets(conn: kuzu.Connection) -> None:
    """Second ingest with different triplets must drop the old edges."""
    doc = _make_doc()
    upsert_doc(conn, doc, [Triplet(doc.node_id, "refers_to", "concept:a", "frontmatter")])
    upsert_doc(conn, doc, [Triplet(doc.node_id, "refers_to", "concept:b", "frontmatter")])
    r = conn.execute(
        "MATCH (s:Node {id: $id})-[:REFERS_TO]->(o:Node) RETURN o.id",
    )
    r.add_parameters({"id": doc.node_id}) if hasattr(r, "add_parameters") else None
    # Re-execute with params the way the writer does
    r = conn.execute(
        "MATCH (s:Node)-[:REFERS_TO]->(o:Node) WHERE s.id = $id RETURN o.id",
        {"id": doc.node_id},
    )
    targets = []
    while r.has_next():  # type: ignore[union-attr]
        targets.append(r.get_next()[0])  # type: ignore[union-attr]
    assert targets == ["concept:b"]


def test_upsert_overwrites_main_node_fields(conn: kuzu.Connection) -> None:
    doc1 = _make_doc()
    upsert_doc(conn, doc1, [])
    doc2 = IngestedDoc(
        path=doc1.path,
        node_id=doc1.node_id,
        level=7,
        topic="relationships",
        title="Обновлённый заголовок",
        body="updated body",
        summary="tldr",
        source=doc1.source,
        source_authority=10,
        applicable_when=doc1.applicable_when,
        related_concepts=("taohua", "new_concept"),
        last_updated=datetime(2026, 6, 1, tzinfo=UTC),
        content_hash="hash-2",
    )
    upsert_doc(conn, doc2, [])
    r = conn.execute(
        "MATCH (n:Node {id: $id}) RETURN n.title, n.content_hash, n.source_authority",
        {"id": doc1.node_id},
    )
    row = r.get_next()  # type: ignore[union-attr]
    assert row == ["Обновлённый заголовок", "hash-2", 10]


def test_load_state_returns_empty_when_missing(tmp_path: Path) -> None:
    assert load_state(tmp_path / "missing.json").hashes == {}


def test_save_then_load_roundtrip(tmp_path: Path) -> None:
    state = IngestState(hashes={"a.md": "h1", "b.md": "h2"})
    p = tmp_path / "state.json"
    save_state(p, state)
    loaded = load_state(p)
    assert loaded.hashes == state.hashes
    assert loaded.last_run  # populated by save_state


def test_state_needs_update(tmp_path: Path) -> None:
    doc = _make_doc()
    state = IngestState()
    assert state.needs_update(doc) is True
    state.mark_ingested(doc)
    assert state.needs_update(doc) is False


def test_state_unreadable_file_returns_empty(tmp_path: Path) -> None:
    p = tmp_path / "broken.json"
    p.write_text("{ not json", encoding="utf-8")
    assert load_state(p).hashes == {}


def test_save_state_writes_valid_json(tmp_path: Path) -> None:
    state = IngestState(hashes={"a.md": "h"})
    p = tmp_path / "state.json"
    save_state(p, state)
    parsed = json.loads(p.read_text(encoding="utf-8"))
    assert parsed["hashes"] == {"a.md": "h"}
    assert "last_run" in parsed
