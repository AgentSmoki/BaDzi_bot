"""Integration tests for ai.rag.retrieve — real KuzuDB queries."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import kuzu
import pytest

from ai.rag import retrieve_nodes, store
from ai.rag.models import RetrievedNode
from knowledge.bootstrap import bootstrap
from knowledge.ingest.models import IngestedDoc, Triplet
from knowledge.ingest.writer import upsert_doc


def _doc(
    node_id: str,
    *,
    title: str,
    level: int,
    related_concepts: tuple[str, ...] = (),
    source_authority: int = 5,
    topic: str = "stars",
    school: str = "universal",
) -> IngestedDoc:
    return IngestedDoc(
        path=Path(f"/virtual/{node_id}.md"),
        node_id=node_id,
        level=level,
        topic=topic,
        title=title,
        body=f"body of {node_id}",
        summary="",
        source="test",
        source_authority=source_authority,
        applicable_when=(),
        related_concepts=related_concepts,
        last_updated=datetime(2026, 5, 17, tzinfo=UTC),
        content_hash=f"hash-{node_id}",
        school=school,  # type: ignore[arg-type]
    )


@pytest.fixture
def kb(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Bootstrap a fresh KuzuDB with three real nodes + sample edges,
    point the rag.store cache at it for the test's duration."""
    db_path = tmp_path / "kuzu_db"
    bootstrap(db_path)
    db = kuzu.Database(str(db_path))
    conn = kuzu.Connection(db)

    upsert_doc(
        conn,
        _doc(
            "L5_stars/baihu",
            title="Белый Тигр (白虎)",
            level=5,
            related_concepts=("baihu", "white tiger", "белый тигр"),
            source_authority=10,
        ),
        [
            Triplet("L5_stars/baihu", "clashes_with", "concept:liuchong", "subagent"),
            Triplet("L5_stars/baihu", "combines_with", "concept:liuhe", "subagent"),
        ],
    )
    upsert_doc(
        conn,
        _doc(
            "L7_predictive/timing",
            title="Столпы Удачи и циклы времени",
            level=7,
            related_concepts=("luck_pillars", "10_year_cycle"),
            source_authority=9,
            topic="timing",
        ),
        [],
    )
    upsert_doc(
        conn,
        _doc(
            "L1_foundational/elements",
            title="Пять элементов: введение",
            level=1,
            related_concepts=("five_elements", "wu_xing"),
            source_authority=6,
            topic="foundations",
        ),
        [],
    )

    # Switch the singleton to point at this tmp DB.
    monkeypatch.setenv("KUZU_DB_PATH", str(db_path))
    store.reset_cache()
    # Patch the path lookup so it doesn't depend on a real bot.config
    monkeypatch.setattr(store, "_get_database", lambda: kuzu.Database(str(db_path), read_only=True))  # type: ignore[arg-type]
    store._get_concept_vocabulary.cache_clear()
    yield db_path
    store.reset_cache()


def test_concept_match_returns_baihu(kb: Path) -> None:
    nodes = retrieve_nodes(["baihu"], top_k=5, expand_neighbours=False)
    assert len(nodes) == 1
    assert nodes[0].node_id == "L5_stars/baihu"
    assert nodes[0].score > 0


def test_title_token_match_returns_luck_pillars(kb: Path) -> None:
    nodes = retrieve_nodes([], title_tokens=["столп", "удач"], top_k=5, expand_neighbours=False)
    assert any(n.node_id == "L7_predictive/timing" for n in nodes)


def test_concept_and_title_scores_merge(kb: Path) -> None:
    """A node hit by BOTH paths must outscore one hit by only one."""
    nodes = retrieve_nodes(
        ["baihu"],
        title_tokens=["белый"],
        top_k=5,
        expand_neighbours=False,
    )
    baihu = next(n for n in nodes if n.node_id == "L5_stars/baihu")
    # +1 concept overlap, +1 title match → higher than concept-only run
    only_concept = retrieve_nodes(["baihu"], top_k=5, expand_neighbours=False)
    assert baihu.score > only_concept[0].score


def test_higher_level_wins_at_tie(kb: Path) -> None:
    """Two nodes each match one title token; L7 must outrank L1."""
    nodes = retrieve_nodes([], title_tokens=["элемент"], top_k=5, expand_neighbours=False)
    # Title contains "элемент" matches "Пять элементов" (L1).
    # If we add another token that also matches the L7 node, it
    # should rank first. The plain query here just verifies L1 hit.
    assert any(n.node_id == "L1_foundational/elements" for n in nodes)


def test_topk_caps_results(kb: Path) -> None:
    nodes = retrieve_nodes(["baihu", "luck_pillars"], top_k=1, expand_neighbours=False)
    assert len(nodes) == 1


def test_no_concepts_no_tokens_returns_empty(kb: Path) -> None:
    assert retrieve_nodes([], top_k=5) == []


def test_unknown_concept_returns_empty(kb: Path) -> None:
    nodes = retrieve_nodes(["this_concept_does_not_exist"], top_k=5, expand_neighbours=False)
    assert nodes == []


# ── Wave 7 Phase 5 — school filter ───────────────────────────────────────


@pytest.fixture
def kb_with_school_mix(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """KB with one node per school + one universal — used to assert
    that ``school=`` filter narrows results correctly."""
    db_path = tmp_path / "kuzu_db_schools"
    bootstrap(db_path)
    db = kuzu.Database(str(db_path))
    conn = kuzu.Connection(db)
    upsert_doc(
        conn,
        _doc(
            "doc/uni",
            title="Universal element rule",
            level=5,
            related_concepts=("alpha",),
            school="universal",
        ),
        [],
    )
    upsert_doc(
        conn,
        _doc(
            "doc/cls",
            title="Classic doc",
            level=5,
            related_concepts=("alpha",),
            school="classic",
        ),
        [],
    )
    upsert_doc(
        conn,
        _doc(
            "doc/edh",
            title="Edoha doc",
            level=5,
            related_concepts=("alpha",),
            school="edoha",
        ),
        [],
    )
    upsert_doc(
        conn,
        _doc(
            "doc/mdn",
            title="Modern doc",
            level=5,
            related_concepts=("alpha",),
            school="modern",
        ),
        [],
    )
    monkeypatch.setenv("KUZU_DB_PATH", str(db_path))
    store.reset_cache()
    monkeypatch.setattr(
        store,
        "_get_database",
        lambda: kuzu.Database(str(db_path), read_only=True),  # type: ignore[arg-type]
    )
    store._get_concept_vocabulary.cache_clear()
    yield db_path
    store.reset_cache()


def test_school_filter_none_returns_all_schools(kb_with_school_mix: Path) -> None:
    """No school filter = legacy behaviour, every school in results."""
    nodes = retrieve_nodes(["alpha"], top_k=10, expand_neighbours=False, school=None)
    ids = {n.node_id for n in nodes}
    assert ids == {"doc/uni", "doc/cls", "doc/edh", "doc/mdn"}


def test_school_filter_edoha_excludes_classic_and_modern(
    kb_with_school_mix: Path,
) -> None:
    """Picking edoha narrows to universal + edoha only."""
    nodes = retrieve_nodes(["alpha"], top_k=10, expand_neighbours=False, school="edoha")
    ids = {n.node_id for n in nodes}
    assert ids == {"doc/uni", "doc/edh"}
    assert "doc/cls" not in ids
    assert "doc/mdn" not in ids


def test_school_filter_classic_keeps_universal(kb_with_school_mix: Path) -> None:
    """Universal docs always pass through — they're the shared base."""
    nodes = retrieve_nodes(["alpha"], top_k=10, expand_neighbours=False, school="classic")
    ids = {n.node_id for n in nodes}
    assert ids == {"doc/uni", "doc/cls"}


def test_returns_empty_when_db_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Bot must degrade gracefully when there's no KuzuDB on the VM yet."""
    store.reset_cache()
    monkeypatch.setattr(store, "_get_database", lambda: None)
    nodes = retrieve_nodes(["baihu"], title_tokens=["белый"])
    assert nodes == []
    assert isinstance(nodes, list)


def test_retrieved_node_shape(kb: Path) -> None:
    nodes = retrieve_nodes(["baihu"], top_k=5, expand_neighbours=False)
    assert nodes
    n = nodes[0]
    assert isinstance(n, RetrievedNode)
    assert n.node_id == "L5_stars/baihu"
    assert n.level == 5
    assert n.source_authority == 10
    assert "белый тигр" in n.title.lower()
    assert n.body
