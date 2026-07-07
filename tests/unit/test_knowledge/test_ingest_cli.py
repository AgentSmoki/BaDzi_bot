"""End-to-end smoke tests for the ingest CLI (knowledge.ingest.cli.main)."""

from __future__ import annotations

import json
from pathlib import Path

import kuzu
import pytest

from knowledge.ingest.cli import main

_DOC = """\
---
level: L5
topic: stars
title: Тест Звезда
related_concepts:
  - test_star
applicable_when:
  - always
source: test
source_authority: 8
last_updated: 2026-05-17
---

Body.
"""


@pytest.fixture
def kb(tmp_path: Path) -> Path:
    """Tiny KB with two docs in different L-folders."""
    root = tmp_path / "kb"
    (root / "L5_stars").mkdir(parents=True)
    (root / "L5_stars" / "a.md").write_text(_DOC, encoding="utf-8")
    (root / "L7_predictive_patterns" / "relationships").mkdir(parents=True)
    (root / "L7_predictive_patterns" / "relationships" / "b.md").write_text(
        _DOC.replace("level: L5", "level: L7").replace("test_star", "other_star"),
        encoding="utf-8",
    )
    return root


def test_cli_dry_run_does_not_create_db(
    kb: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = tmp_path / "kdb"
    rc = main(["--source", str(kb), "--db-path", str(db), "--dry-run"])
    assert rc == 0
    assert not db.exists()
    summary = json.loads(capsys.readouterr().out)
    assert summary["docs_ingested"] == 2
    assert summary["dry_run"] is True


def test_cli_full_run_writes_graph(
    kb: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = tmp_path / "kdb"
    rc = main(["--source", str(kb), "--db-path", str(db)])
    assert rc == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["docs_ingested"] == 2
    assert summary["edges_written"] == 2

    # Inspect: 2 real nodes + 2 stubs = 4
    db_handle = kuzu.Database(str(db))
    conn = kuzu.Connection(db_handle)
    r = conn.execute("MATCH (n:Node) RETURN count(n)")
    assert r.get_next()[0] == 4  # type: ignore[union-attr]


def test_cli_incremental_skips_unchanged(
    kb: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = tmp_path / "kdb"
    main(["--source", str(kb), "--db-path", str(db)])
    capsys.readouterr()  # discard first summary

    rc = main(["--source", str(kb), "--db-path", str(db), "--incremental"])
    assert rc == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["docs_skipped"] == 2
    assert summary["docs_ingested"] == 0


def test_cli_incremental_picks_up_body_edits(
    kb: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = tmp_path / "kdb"
    main(["--source", str(kb), "--db-path", str(db)])
    capsys.readouterr()

    # Edit one file's body — hash changes
    edited = (kb / "L5_stars" / "a.md").read_text(encoding="utf-8") + "\nMore body.\n"
    (kb / "L5_stars" / "a.md").write_text(edited, encoding="utf-8")

    rc = main(["--source", str(kb), "--db-path", str(db), "--incremental"])
    assert rc == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["docs_skipped"] == 1
    assert summary["docs_ingested"] == 1


def test_cli_single_file_mode(kb: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db = tmp_path / "kdb"
    target = kb / "L5_stars" / "a.md"
    rc = main(["--file", str(target), "--source", str(kb), "--db-path", str(db)])
    assert rc == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["docs_total"] == 1
    assert summary["docs_ingested"] == 1


def test_cli_single_file_invalid_returns_2(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bad = tmp_path / "garbage.md"
    bad.write_text("no frontmatter\n", encoding="utf-8")
    rc = main(["--file", str(bad), "--db-path", str(tmp_path / "kdb")])
    assert rc == 2


def test_cli_list_pending_extracts(
    kb: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    # Make one of the two files already have a sidecar
    sidecar = kb / "L5_stars" / "a.md.triplets.json"
    sidecar.write_text("[]", encoding="utf-8")

    rc = main(["--source", str(kb), "--list-pending-extracts"])
    assert rc == 0
    out = capsys.readouterr().out
    assert str(kb / "L7_predictive_patterns" / "relationships" / "b.md") in out
    assert str(kb / "L5_stars" / "a.md") not in out


def test_cli_state_file_lands_next_to_db(
    kb: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    db = tmp_path / "kdb"
    main(["--source", str(kb), "--db-path", str(db)])
    capsys.readouterr()

    # When db_path has no suffix, state lives in the dir; when it's a
    # file (Kuzu 0.11), state lives next to it. Either way it must exist.
    candidates = [
        db / "_ingest_state.json",
        db.parent / "_ingest_state.json",
    ]
    assert any(p.is_file() for p in candidates), candidates
