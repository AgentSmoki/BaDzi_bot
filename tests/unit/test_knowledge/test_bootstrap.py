"""Integration tests for knowledge.bootstrap.

These spin up a real KuzuDB in a tmp dir — Kuzu is embedded, so this is
fast (~50 ms per test) and exercises the actual DDL the production
bootstrap will run."""

from __future__ import annotations

import contextlib
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import kuzu

from knowledge.bootstrap import bootstrap, main
from knowledge.schema import NODE_TABLE_NAME, REL_TABLE_NAMES

if TYPE_CHECKING:
    import pytest


def test_bootstrap_creates_all_tables(tmp_path: Path) -> None:
    db_path = tmp_path / "kuzu_db"
    result = bootstrap(db_path)
    assert db_path.exists()
    assert NODE_TABLE_NAME in result.node_tables
    for rel in REL_TABLE_NAMES:
        assert rel in result.rel_tables, f"missing rel table {rel}"
    assert result.created_statements == 1 + len(REL_TABLE_NAMES)


def test_bootstrap_is_idempotent(tmp_path: Path) -> None:
    """Running bootstrap twice on the same path must not raise."""
    db_path = tmp_path / "kuzu_db"
    first = bootstrap(db_path)
    second = bootstrap(db_path)
    assert set(first.rel_tables) == set(second.rel_tables)
    assert set(first.node_tables) == set(second.node_tables)


def test_bootstrap_recreate_wipes_existing(tmp_path: Path) -> None:
    """--recreate should drop the dir; new DB should still match schema."""
    db_path = tmp_path / "kuzu_db"
    bootstrap(db_path)

    # Insert one node so we can detect that --recreate actually wiped it
    db = kuzu.Database(str(db_path))
    conn = kuzu.Connection(db)
    conn.execute("CREATE (:Node {id: 'probe', level: 1, source_authority: 5})")
    del conn
    del db

    bootstrap(db_path, recreate=True)
    db2 = kuzu.Database(str(db_path))
    conn2 = kuzu.Connection(db2)
    result = conn2.execute("MATCH (n:Node) RETURN count(n)")
    while result.has_next():  # type: ignore[union-attr]
        (count,) = result.get_next()  # type: ignore[union-attr]
        assert count == 0, "node from before --recreate survived the wipe"


def test_node_can_be_inserted_and_queried(tmp_path: Path) -> None:
    """End-to-end: schema actually supports the columns we promised."""
    db_path = tmp_path / "kuzu_db"
    bootstrap(db_path)
    db = kuzu.Database(str(db_path))
    conn = kuzu.Connection(db)
    conn.execute(
        """
        CREATE (:Node {
            id: 'taohua-marriage-l7',
            level: 7,
            topic: 'relationships',
            title: 'Сигналы брака через 桃花',
            body: 'Тестовое тело правила',
            summary: 'tldr',
            source: 'teacher_lesson_2024_03_15',
            source_authority: 9,
            applicable_when: ['dm_yin_water'],
            related_concepts: ['taohua', 'zheng_cai'],
            embedding: CAST([] AS FLOAT[]),
            content_hash: 'abc123',
            last_updated: TIMESTAMP('2026-05-17 12:00:00')
        })
        """
    )
    result = conn.execute("MATCH (n:Node) WHERE n.level = 7 RETURN n.title, n.related_concepts")
    rows = []
    while result.has_next():  # type: ignore[union-attr]
        rows.append(result.get_next())  # type: ignore[union-attr]
    assert len(rows) == 1
    title, concepts = rows[0]
    assert title == "Сигналы брака через 桃花"
    assert "taohua" in concepts


def test_rel_table_accepts_edges(tmp_path: Path) -> None:
    """Insert two nodes + a REFERS_TO edge between them."""
    db_path = tmp_path / "kuzu_db"
    bootstrap(db_path)
    db = kuzu.Database(str(db_path))
    conn = kuzu.Connection(db)
    conn.execute("CREATE (:Node {id: 'a', level: 1, source_authority: 5})")
    conn.execute("CREATE (:Node {id: 'b', level: 7, source_authority: 9})")
    conn.execute(
        """
        MATCH (a:Node {id: 'a'}), (b:Node {id: 'b'})
        CREATE (a)-[:REFERS_TO {kind: 'supports'}]->(b)
        """
    )
    result = conn.execute("MATCH (a:Node)-[r:REFERS_TO]->(b:Node) RETURN a.id, r.kind, b.id")
    rows = []
    while result.has_next():  # type: ignore[union-attr]
        rows.append(tuple(result.get_next()))  # type: ignore[union-attr]
    assert rows == [("a", "supports", "b")]


def test_cli_main_exit_zero_on_fresh_db(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_path = tmp_path / "kuzu_db"
    rc = main(["--db-path", str(db_path), "--verbose"])
    assert rc == 0
    captured = capsys.readouterr()
    assert "KuzuDB bootstrap OK" in captured.out
    assert NODE_TABLE_NAME in captured.out


def test_cli_main_logging_does_not_crash_without_settings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If bot.config can't be imported (no .env at all), bootstrap should
    still work via explicit --db-path. Sanity check for CI / dev boxes."""
    db_path = tmp_path / "kuzu_db"
    # Strip env vars that pydantic-settings might pick up on
    for key in list(__import__("os").environ):
        if key.startswith(("BOT_", "REDIS_", "POSTGRES_", "OPENROUTER_", "YC_", "YUKASSA_")):
            with contextlib.suppress(KeyError):
                monkeypatch.delenv(key, raising=False)
    rc = main(["--db-path", str(db_path)])
    assert rc == 0


def test_bootstrap_logs_info_per_ddl(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    db_path = tmp_path / "kuzu_db"
    with caplog.at_level(logging.INFO, logger="knowledge.bootstrap"):
        bootstrap(db_path)
    assert sum(1 for r in caplog.records if r.message == "bootstrap.ddl_ok") == 7
