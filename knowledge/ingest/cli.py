"""Ingest CLI: parser → extract → writer orchestration (Phase 2.4).

Usage:
    python -m knowledge.ingest                          # full ingest, default paths
    python -m knowledge.ingest --source <kb-dir>        # custom KB root
    python -m knowledge.ingest --file <path/to/one.md>  # single file
    python -m knowledge.ingest --incremental            # skip unchanged docs
    python -m knowledge.ingest --dry-run                # parse + extract, no DB writes
    python -m knowledge.ingest --list-pending-extracts  # files without sidecar

The CLI is deliberately small — it just glues the three modules together.
Anything reusable (parser/extract/writer) lives in those modules so
other callers (a future watcher, a test harness) can use them directly.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import kuzu

from knowledge.bootstrap import bootstrap
from knowledge.ingest.extract import extract_triplets, files_pending_extract
from knowledge.ingest.models import IngestState
from knowledge.ingest.parser import parse_md_file, scan_kb
from knowledge.ingest.writer import load_state, save_state, upsert_doc

if TYPE_CHECKING:
    from collections.abc import Sequence

    from knowledge.ingest.models import IngestedDoc

logger = logging.getLogger(__name__)


def _default_kb_root() -> Path:
    """Repo root / База/teacher/. Keeps the CLI working when run without
    a configured project (developers, CI smoke)."""
    return Path(__file__).resolve().parents[2] / "База" / "teacher"


def _default_db_path() -> Path:
    """Same lazy-import dance as :mod:`knowledge.bootstrap` so this CLI
    doesn't drag aiogram in just to read a path."""
    try:
        from bot.config import get_settings

        return Path(get_settings().kuzu_db_path)
    except Exception:
        logger.warning("ingest.settings_unavailable")
        return Path("./knowledge/kuzu_db")


def _ingest_one(
    conn: kuzu.Connection,
    doc: IngestedDoc,
    state: IngestState,
    *,
    incremental: bool,
    dry_run: bool,
) -> tuple[str, int]:
    """Returns (verdict, edges_written). ``verdict`` is one of
    ``"ingested" | "skipped"`` for log-level reporting."""
    if incremental and not state.needs_update(doc):
        return "skipped", 0
    triplets = extract_triplets(doc)
    if dry_run:
        return "ingested", len(triplets)
    edges = upsert_doc(conn, doc, triplets)
    state.mark_ingested(doc)
    return "ingested", edges


def _state_path_for(db_path: Path) -> Path:
    """The state file lives next to the KuzuDB so a single dir holds
    the whole knowledge artefact set."""
    parent = db_path.parent if db_path.suffix else db_path
    return parent / "_ingest_state.json"


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest teacher KB → KuzuDB graph.")
    parser.add_argument(
        "--source",
        type=Path,
        default=None,
        help="KB root directory (defaults to <repo>/База/teacher).",
    )
    parser.add_argument(
        "--file",
        type=Path,
        default=None,
        help="Single .md file to ingest (overrides --source).",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help="KuzuDB directory (defaults to settings.kuzu_db_path).",
    )
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Skip documents whose body hash matches _ingest_state.json.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse + extract, but don't write to KuzuDB.",
    )
    parser.add_argument(
        "--list-pending-extracts",
        action="store_true",
        help="Print .md files without a sidecar .triplets.json (for subagent enrichment).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Emit INFO logs from the ingest modules.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    kb_root = args.source or _default_kb_root()

    if args.list_pending_extracts:
        for path in files_pending_extract(kb_root):
            print(path)
        return 0

    # Collect docs to ingest
    docs: list[IngestedDoc] = []
    if args.file is not None:
        doc = parse_md_file(args.file, kb_root=kb_root)
        if doc is None:
            print(f"ERROR: {args.file} is not a valid KB doc", file=sys.stderr)
            return 2
        docs = [doc]
    else:
        docs = scan_kb(kb_root)

    if not docs:
        print(f"No docs found under {kb_root}")
        return 0

    db_path = args.db_path or _default_db_path()
    state_path = _state_path_for(db_path)
    state = load_state(state_path)

    if not args.dry_run:
        # Ensure schema is in place — cheap, idempotent.
        bootstrap(db_path)

    db: kuzu.Database | None = None
    conn: kuzu.Connection | None = None
    if not args.dry_run:
        db = kuzu.Database(str(db_path))
        conn = kuzu.Connection(db)

    ingested = skipped = total_edges = 0
    for doc in docs:
        verdict, edges = _ingest_one(
            conn,  # type: ignore[arg-type]
            doc,
            state,
            incremental=args.incremental,
            dry_run=args.dry_run,
        )
        if verdict == "skipped":
            skipped += 1
        else:
            ingested += 1
            total_edges += edges

    if not args.dry_run:
        save_state(state_path, state)

    summary = {
        "kb_root": str(kb_root),
        "db_path": str(db_path),
        "docs_total": len(docs),
        "docs_ingested": ingested,
        "docs_skipped": skipped,
        "edges_written": total_edges,
        "dry_run": args.dry_run,
        "incremental": args.incremental,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
