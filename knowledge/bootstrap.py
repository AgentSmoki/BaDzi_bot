"""Idempotent KuzuDB bootstrap — creates the schema on a fresh DB and
no-ops if everything is already in place.

Usage:
    python -m knowledge.bootstrap                       # uses settings.kuzu_db_path
    python -m knowledge.bootstrap --db-path ./tmp/kdb   # explicit path
    python -m knowledge.bootstrap --recreate            # drop + recreate (LOCAL ONLY)

``--recreate`` exists for fast local iteration on schema design; it's
explicitly guarded so it can't be invoked without typing the flag, and
it never runs in CI because it shells through ``argparse`` (no env-var
short-cut).
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import kuzu

from knowledge.schema import ALL_DDL, MIGRATION_DDL, NODE_TABLE_NAME, REL_TABLE_NAMES

if TYPE_CHECKING:
    from collections.abc import Sequence

logger = logging.getLogger(__name__)


class BootstrapResult:
    """Tiny value object — keeps the CLI output and the test assertions
    speaking the same language without exposing a ``dict``."""

    __slots__ = ("created_statements", "db_path", "node_tables", "rel_tables")

    def __init__(
        self,
        *,
        db_path: Path,
        node_tables: Sequence[str],
        rel_tables: Sequence[str],
        created_statements: int,
    ) -> None:
        self.db_path = db_path
        self.node_tables = tuple(node_tables)
        self.rel_tables = tuple(rel_tables)
        self.created_statements = created_statements


def _list_tables(conn: kuzu.Connection) -> tuple[list[str], list[str]]:
    """Return (node_table_names, rel_table_names) currently in the DB.

    Uses ``SHOW_TABLES()`` (Kuzu 0.7+) which on 0.10/0.11 returns columns
    ``id, name, type, database name, comment``. We look up by column
    index after fetching ``get_column_names()`` so the parser survives
    Kuzu adding/reordering columns in future versions.
    """
    try:
        result = conn.execute("CALL SHOW_TABLES() RETURN *")
    except RuntimeError:
        # Older Kuzu fallback
        result = conn.execute("CALL show_tables() RETURN *")

    cols = result.get_column_names()  # type: ignore[union-attr]
    try:
        i_name = cols.index("name")
        i_type = cols.index("type")
    except ValueError:
        logger.warning("bootstrap.show_tables_columns_unexpected", extra={"cols": cols})
        return [], []

    nodes: list[str] = []
    rels: list[str] = []
    while result.has_next():  # type: ignore[union-attr]
        row = result.get_next()  # type: ignore[union-attr]
        name = row[i_name]
        kind = str(row[i_type]).upper()
        if kind == "NODE":
            nodes.append(name)
        elif kind == "REL":
            rels.append(name)
    return nodes, rels


def bootstrap(db_path: Path, *, recreate: bool = False) -> BootstrapResult:
    """Open (or create) the KuzuDB at ``db_path`` and apply the full
    schema. With ``recreate=True`` the directory is wiped first.

    Idempotent: every DDL uses ``IF NOT EXISTS`` so running this twice
    in a row produces the same result as running it once.
    """
    if recreate and db_path.exists():
        logger.warning("bootstrap.recreate", extra={"path": str(db_path)})
        # Kuzu 0.10 stored the DB as a directory, 0.11+ stores it as a
        # single file (plus a sibling .wal). Handle both shapes plus the
        # adjacent write-ahead log so a recreate is actually clean.
        if db_path.is_dir():
            shutil.rmtree(db_path)
        else:
            db_path.unlink()
            wal = db_path.with_suffix(db_path.suffix + ".wal")
            if wal.exists():
                wal.unlink()

    db_path.parent.mkdir(parents=True, exist_ok=True)

    db = kuzu.Database(str(db_path))
    conn = kuzu.Connection(db)
    created = 0
    for stmt in ALL_DDL:
        conn.execute(stmt)
        created += 1
        logger.info("bootstrap.ddl_ok", extra={"stmt": stmt.split("(", 1)[0].strip()})

    # Wave 7 Phase 5 — apply ALTER-style migrations with tolerance.
    # Kuzu has no «ADD COLUMN IF NOT EXISTS» so we catch the «already
    # exists» RuntimeError and log; any other error still propagates so
    # an actual schema bug doesn't pass silently.
    for stmt in MIGRATION_DDL:
        try:
            conn.execute(stmt)
            created += 1
            logger.info("bootstrap.migration_ok", extra={"stmt": stmt})
        except RuntimeError as exc:
            # Kuzu surfaces «Binder exception: ... already exists» when
            # the migration was applied on a previous run.
            msg = str(exc).lower()
            if "already exists" in msg or "already" in msg:
                logger.info("bootstrap.migration_skip", extra={"stmt": stmt})
            else:
                raise

    nodes, rels = _list_tables(conn)
    return BootstrapResult(
        db_path=db_path,
        node_tables=nodes,
        rel_tables=rels,
        created_statements=created,
    )


def _default_db_path() -> Path:
    """Resolve the default DB path from settings without importing the
    full bot stack at module load (keeps ``python -m knowledge.bootstrap``
    cheap and avoids pulling in aiogram for a schema script)."""
    try:
        from bot.config import get_settings

        return Path(get_settings().kuzu_db_path)
    except Exception:
        # Bootstrap script must work even when .env / pydantic validators
        # blow up — fall back to the documented default so the operator
        # can still smoke-test the schema on a fresh checkout.
        logger.warning("bootstrap.settings_unavailable")
        return Path("./knowledge/kuzu_db")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bootstrap the BaDzi KuzuDB schema.")
    parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help="Path to KuzuDB directory (defaults to settings.kuzu_db_path).",
    )
    parser.add_argument(
        "--recreate",
        action="store_true",
        help="Drop the existing DB directory before bootstrap (LOCAL ONLY).",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Emit INFO logs.",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )

    db_path = args.db_path or _default_db_path()
    result = bootstrap(db_path, recreate=args.recreate)

    # Plain-text status: this is meant to be eyeballed by the operator
    # right after a fresh deploy, not parsed.
    print(f"KuzuDB bootstrap OK  db={result.db_path}")
    print(f"  node tables ({len(result.node_tables)}): {', '.join(result.node_tables) or '-'}")
    print(f"  rel  tables ({len(result.rel_tables)}): {', '.join(result.rel_tables) or '-'}")
    print(f"  DDL statements applied: {result.created_statements}")

    expected_nodes = {NODE_TABLE_NAME}
    expected_rels = set(REL_TABLE_NAMES)
    missing_nodes = expected_nodes - set(result.node_tables)
    missing_rels = expected_rels - set(result.rel_tables)
    if missing_nodes or missing_rels:
        print(f"  WARNING missing nodes={missing_nodes} rels={missing_rels}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
