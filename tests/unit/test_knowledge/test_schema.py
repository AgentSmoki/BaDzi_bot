"""Sanity tests for knowledge.schema — DDL strings stay in sync with the
table-name constants and contain the expected primary keys / FROM-TO edges."""

from __future__ import annotations

from knowledge.schema import (
    ALL_DDL,
    NODE_TABLE_DDL,
    NODE_TABLE_NAME,
    REL_TABLE_NAMES,
    REL_TABLES_DDL,
)


def test_node_table_ddl_declares_primary_key() -> None:
    assert "PRIMARY KEY" in NODE_TABLE_DDL.upper()
    assert NODE_TABLE_NAME in NODE_TABLE_DDL


def test_node_table_ddl_has_all_planned_columns() -> None:
    """Plan 1.1 lists these columns explicitly — guard against drift."""
    required = (
        "id ",
        "level ",
        "topic ",
        "title ",
        "body ",
        "summary ",
        "source ",
        "source_authority ",
        "applicable_when ",
        "related_concepts ",
        "embedding ",
        "content_hash ",
        "last_updated ",
    )
    for col in required:
        assert col in NODE_TABLE_DDL, f"missing column declaration: {col!r}"


def test_rel_table_names_match_ddl() -> None:
    for name, ddl in zip(REL_TABLE_NAMES, REL_TABLES_DDL, strict=True):
        assert name in ddl
        assert "FROM Node TO Node" in ddl


def test_all_ddl_uses_if_not_exists() -> None:
    """Idempotent bootstrap relies on every statement being IF NOT EXISTS."""
    for stmt in ALL_DDL:
        assert "IF NOT EXISTS" in stmt.upper(), stmt


def test_all_ddl_starts_with_node_table() -> None:
    """Node must be created before any REL table references it."""
    assert ALL_DDL[0] is NODE_TABLE_DDL
    assert "CREATE NODE TABLE" in ALL_DDL[0].upper()
    for stmt in ALL_DDL[1:]:
        assert "CREATE REL TABLE" in stmt.upper()
