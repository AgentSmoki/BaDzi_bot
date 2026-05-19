"""End-to-end tests for ai.rag.public — load_knowledge_for_question."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import kuzu
import pytest

from ai.rag import load_knowledge_for_question, store
from knowledge.bootstrap import bootstrap
from knowledge.ingest.models import IngestedDoc, Triplet
from knowledge.ingest.writer import upsert_doc


@pytest.fixture
def kb(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db_path = tmp_path / "kuzu_db"
    bootstrap(db_path)
    db = kuzu.Database(str(db_path))
    conn = kuzu.Connection(db)
    upsert_doc(
        conn,
        IngestedDoc(
            path=Path("/virtual/baihu.md"),
            node_id="L5_stars/baihu",
            level=5,
            topic="stars",
            title="Белый Тигр (白虎) — классическая трактовка",
            body="Белый Тигр — звезда категории насилия. Активация через 六冲 столкновение.",
            summary="",
            source="lesson_2024",
            source_authority=10,
            applicable_when=(),
            related_concepts=("baihu", "white tiger", "белый тигр"),
            last_updated=datetime(2026, 5, 17, tzinfo=UTC),
            content_hash="h1",
        ),
        [Triplet("L5_stars/baihu", "clashes_with", "concept:liuchong", "subagent")],
    )
    monkeypatch.setattr(store, "_get_database", lambda: kuzu.Database(str(db_path), read_only=True))
    store._get_concept_vocabulary.cache_clear()
    yield db_path
    store.reset_cache()


def test_question_with_concept_match(kb: Path) -> None:
    block = load_knowledge_for_question("Что у меня значит baihu в дне?")
    assert "Белый Тигр" in block
    assert "лесном" not in block  # sanity: no other doc bled in
    assert "10/10" in block


def test_question_with_russian_phrase(kb: Path) -> None:
    block = load_knowledge_for_question("Расскажи про Белый Тигр в моей карте")
    assert "Белый Тигр" in block


def test_question_with_no_matching_content_returns_empty(kb: Path) -> None:
    assert load_knowledge_for_question("Какая сегодня погода?") == ""


def test_empty_question_returns_empty(kb: Path) -> None:
    assert load_knowledge_for_question("") == ""


def test_no_db_returns_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """The bot must boot even on a VM that hasn't received the kuzu_db
    file yet — graceful degradation, not a crash."""
    store.reset_cache()
    monkeypatch.setattr(store, "_get_database", lambda: None)
    assert load_knowledge_for_question("baihu") == ""


def test_top_k_caps_results(kb: Path) -> None:
    """Even with a permissive query, top_k=0 returns empty (used as a
    feature-flag knob from settings)."""
    block = load_knowledge_for_question("baihu белый тигр", top_k=0)
    # top_k=0 means no direct hits — block is empty
    assert block == "" or "Белый Тигр" not in block


# ── Wave 6 / Phase 5: concept_hints from the skill-router ────────────────


def test_concept_hints_pull_in_doc_not_mentioned_in_question(kb: Path) -> None:
    """The skill-router supplies concept_hints like ``baihu`` that the
    user's question may not contain verbatim. They should still pull
    the relevant KB doc in."""
    block = load_knowledge_for_question(
        "Расскажи про мою сильную ветвь",
        concept_hints=["baihu"],
    )
    assert "Белый Тигр" in block


def test_concept_hints_deduplicated_with_extracted_concepts(kb: Path) -> None:
    """Passing a concept that's already in the question text is a no-op
    — no duplicate hit, no crash."""
    block = load_knowledge_for_question(
        "Расскажи про baihu в моей карте",
        concept_hints=["baihu"],
    )
    assert "Белый Тигр" in block
    # The block format has one entry per node — count occurrences of the
    # node title prefix (it appears once in the body header).
    assert block.count("Белый Тигр (白虎)") == 1


def test_concept_hints_none_equals_legacy_behavior(kb: Path) -> None:
    a = load_knowledge_for_question("baihu")
    b = load_knowledge_for_question("baihu", concept_hints=None)
    assert a == b
