"""KuzuDB writer for the ingest pipeline (Phase 2.3).

Provides one composite operation, :func:`upsert_doc`: it inserts (or
updates) a ``Node`` for the document, ensures all referenced concept
nodes exist as stubs, and replaces the document's outgoing edges with
the fresh triplets. The operation is idempotent — running it twice on
the same ``IngestedDoc`` + ``triplets`` produces the same graph.

The writer is intentionally synchronous: KuzuDB Python is itself sync,
and the ingest CLI is not in the bot's request hot path.
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import kuzu

from knowledge.ingest.models import REL_KINDS, IngestedDoc, IngestState, Triplet
from knowledge.schema import NODE_TABLE_NAME

logger = logging.getLogger(__name__)

# Mapping ``RelationKind`` → KuzuDB REL TABLE name. The ``refers_to``
# table additionally carries a ``kind`` discriminator; right now we
# always set it to ``"default"`` because the dedicated REL tables cover
# the relation types the heuristic knows about. The discriminator is
# kept so future extractors can add fine-grained sub-types without
# spawning new tables.
_REL_TABLE: Final[dict[str, str]] = {
    "refers_to": "REFERS_TO",
    "generates": "GENERATES",
    "controls": "CONTROLS",
    "combines_with": "COMBINES_WITH",
    "clashes_with": "CLASHES_WITH",
    "example_of": "EXAMPLE_OF",
}


def _ensure_stub_node(conn: kuzu.Connection, node_id: str) -> None:
    """Create a placeholder Node iff one with this id doesn't exist.

    Stub fields are intentionally minimal — they'll be overwritten in
    full when (if ever) a .md file with this ``node_id`` is ingested."""
    conn.execute(
        f"""
        MERGE (n:{NODE_TABLE_NAME} {{id: $id}})
        ON CREATE SET
            n.level = 0,
            n.topic = 'stub',
            n.title = $id,
            n.body = '',
            n.summary = '',
            n.source = 'stub',
            n.source_authority = 0,
            n.applicable_when = [],
            n.related_concepts = [],
            n.embedding = CAST([] AS FLOAT[]),
            n.content_hash = '',
            n.last_updated = TIMESTAMP('1970-01-01 00:00:00')
        """,
        {"id": node_id},
    )


def _delete_outgoing_edges(conn: kuzu.Connection, node_id: str) -> None:
    """Drop every outgoing edge from ``node_id`` across all REL tables.

    Required for idempotency: re-ingesting the same doc replaces its
    edge set rather than accumulating duplicates."""
    for rel in REL_KINDS:
        table = _REL_TABLE[rel]
        conn.execute(
            f"""
            MATCH (a:{NODE_TABLE_NAME} {{id: $id}})-[r:{table}]->()
            DELETE r
            """,
            {"id": node_id},
        )


def _upsert_main_node(conn: kuzu.Connection, doc: IngestedDoc) -> None:
    """MERGE the doc Node and set / overwrite all data columns."""
    conn.execute(
        f"""
        MERGE (n:{NODE_TABLE_NAME} {{id: $id}})
        SET
            n.level = $level,
            n.topic = $topic,
            n.title = $title,
            n.body = $body,
            n.summary = $summary,
            n.source = $source,
            n.source_authority = $source_authority,
            n.applicable_when = $applicable_when,
            n.related_concepts = $related_concepts,
            n.embedding = CAST([] AS FLOAT[]),
            n.content_hash = $content_hash,
            n.last_updated = $last_updated
        """,
        {
            "id": doc.node_id,
            "level": doc.level,
            "topic": doc.topic,
            "title": doc.title,
            "body": doc.body,
            "summary": doc.summary,
            "source": doc.source,
            "source_authority": doc.source_authority,
            "applicable_when": list(doc.applicable_when),
            "related_concepts": list(doc.related_concepts),
            "content_hash": doc.content_hash,
            "last_updated": doc.last_updated,
        },
    )


def _insert_edges(conn: kuzu.Connection, doc_node_id: str, triplets: list[Triplet]) -> int:
    inserted = 0
    for t in triplets:
        _ensure_stub_node(conn, t.object_node_id)
        table = _REL_TABLE[t.relation]
        if t.relation == "refers_to":
            conn.execute(
                f"""
                MATCH (a:{NODE_TABLE_NAME} {{id: $sid}}),
                      (b:{NODE_TABLE_NAME} {{id: $oid}})
                CREATE (a)-[:{table} {{kind: $kind}}]->(b)
                """,
                {"sid": t.subject_node_id, "oid": t.object_node_id, "kind": "default"},
            )
        else:
            conn.execute(
                f"""
                MATCH (a:{NODE_TABLE_NAME} {{id: $sid}}),
                      (b:{NODE_TABLE_NAME} {{id: $oid}})
                CREATE (a)-[:{table}]->(b)
                """,
                {"sid": t.subject_node_id, "oid": t.object_node_id},
            )
        inserted += 1
    return inserted


def upsert_doc(conn: kuzu.Connection, doc: IngestedDoc, triplets: list[Triplet]) -> int:
    """Upsert the Node + replace its outgoing edges. Returns the number
    of edges actually written (== len(triplets) on success)."""
    _ensure_stub_node(conn, doc.node_id)
    _upsert_main_node(conn, doc)
    _delete_outgoing_edges(conn, doc.node_id)
    return _insert_edges(conn, doc.node_id, triplets)


# ── State persistence ─────────────────────────────────────────────────────


def load_state(path: Path) -> IngestState:
    """Load ``_ingest_state.json`` or return a fresh empty state."""
    if not path.is_file():
        return IngestState()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("ingest.state_unreadable", extra={"path": str(path), "error": str(exc)})
        return IngestState()
    return IngestState(
        hashes=dict(raw.get("hashes", {})),
        last_run=str(raw.get("last_run", "")),
        schema_version=int(raw.get("schema_version", 1)),
    )


def save_state(path: Path, state: IngestState) -> None:
    state.last_run = datetime.now(UTC).isoformat()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "hashes": state.hashes,
                "last_run": state.last_run,
                "schema_version": state.schema_version,
            },
            indent=2,
            sort_keys=True,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
