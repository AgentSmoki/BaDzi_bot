"""KuzuDB connection management for the retrieval hot path.

The bot is async (aiogram) but KuzuDB's Python client is sync. We keep
ONE :class:`kuzu.Database` instance per process — it owns the file lock
and can have many concurrent :class:`kuzu.Connection` siblings reading
through it. Opening a fresh ``Connection`` per query is cheap (~ms in
benchmarks), so we don't pool — the bookkeeping isn't worth it.

The database is opened in **read-only mode** in the bot. Ingestion
(:mod:`knowledge.ingest`) runs separately (local dev / cron / one-shot
container) and writes through a non-read-only Database; the produced
file is then rsynced to the VM where the bot mounts it RO.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from pathlib import Path

import kuzu

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_database() -> kuzu.Database | None:
    """Return the singleton :class:`kuzu.Database` or ``None`` if the
    KB doesn't exist yet (fresh deploys, tests without a bootstrapped
    DB). Callers must tolerate ``None`` — the retrieval pipeline
    degrades gracefully to an empty knowledge block in that case.
    """
    try:
        from bot.config import get_settings

        db_path = Path(get_settings().kuzu_db_path)
    except Exception:
        # Config not loadable (CI without .env). Fall back to the
        # documented default so smoke-tests can still hit the bundled DB.
        db_path = Path("./knowledge/kuzu_db")

    if not db_path.exists():
        logger.info("rag.store.db_missing", extra={"path": str(db_path)})
        return None

    try:
        return kuzu.Database(str(db_path), read_only=True)
    except RuntimeError as exc:
        # Another writer holds the lock, or the file is corrupt — log
        # and return None so requests don't crash. Operator sees this
        # in the logs and restarts the bot once the writer is done.
        logger.warning("rag.store.db_open_failed", extra={"path": str(db_path), "error": str(exc)})
        return None


def open_connection() -> kuzu.Connection | None:
    """Open a fresh connection through the singleton database. Returns
    ``None`` if the DB is unavailable so callers can no-op cleanly."""
    db = _get_database()
    if db is None:
        return None
    return kuzu.Connection(db)


def reset_cache() -> None:
    """Tests: drop the cached database so ``KUZU_DB_PATH`` overrides
    are honoured between cases. Also used by an operator command after
    redeploying the KB file.

    Robust against monkeypatching: tests sometimes replace the cached
    function with a plain callable, which has no ``cache_clear`` — we
    fall through cleanly in that case.
    """
    for fn in (_get_database, _get_concept_vocabulary):
        clear = getattr(fn, "cache_clear", None)
        if clear is not None:
            clear()


@lru_cache(maxsize=1)
def _get_concept_vocabulary() -> frozenset[str]:
    """Collect every distinct token that appears in any ``Node.related_concepts``
    array. Used by :mod:`ai.rag.extract` to filter the question's word
    bag down to tokens that actually exist as concepts in the graph.

    Rebuilt by ``reset_cache()`` — relatively cheap (one Cypher scan)
    but worth caching across requests.
    """
    conn = open_connection()
    if conn is None:
        return frozenset()
    try:
        r = conn.execute("MATCH (n:Node) UNWIND n.related_concepts AS c RETURN DISTINCT c")
        vocab: set[str] = set()
        while r.has_next():  # type: ignore[union-attr]
            (token,) = r.get_next()  # type: ignore[union-attr]
            if isinstance(token, str) and token:
                vocab.add(token.lower())
        return frozenset(vocab)
    except RuntimeError as exc:
        logger.warning("rag.store.vocab_query_failed", extra={"error": str(exc)})
        return frozenset()


def get_concept_vocabulary() -> frozenset[str]:
    """Public accessor — kept distinct from the cached impl so tests can
    monkeypatch :func:`_get_concept_vocabulary` without touching this name."""
    return _get_concept_vocabulary()
