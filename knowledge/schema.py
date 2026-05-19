"""KuzuDB schema for the fractal Bazi knowledge graph (ADR-004, plan 1.9).

Single ``Node`` table holds all knowledge units — teacher lessons, concepts,
classical rules, chart examples. ``level`` (L1-L7) marks abstraction tier
so the retriever can prefer applied heuristics (L7) over foundations (L1).

Six relationship tables cover the kinds of links that actually carry
meaning in Bazi reasoning: ``REFERS_TO`` is the generic catch-all,
``GENERATES`` / ``CONTROLS`` are the Five Elements cycles,
``COMBINES_WITH`` / ``CLASHES_WITH`` are 合 / 沖, ``EXAMPLE_OF`` links a
specific chart example to the rule it illustrates.

Schema lives as DDL strings (not ORM models) because Kuzu's Python client
takes raw Cypher and the DDL is short — keeping it as a list of statements
is the cheapest path to idempotent bootstrap (run all with ``IF NOT EXISTS``).

The ``embedding`` column is a variable-length ``FLOAT[]`` so it can stay
empty until Phase 2.5 turns on bge-m3 embeddings; once the embedding pass
runs, every node carries a 1024-d vector and retrieval can rank by
cosine similarity rather than keyword overlap.
"""

from __future__ import annotations

from typing import Final

NODE_TABLE_DDL: Final[str] = """
CREATE NODE TABLE IF NOT EXISTS Node(
    id STRING,
    level INT64,
    topic STRING,
    title STRING,
    body STRING,
    summary STRING,
    source STRING,
    source_authority INT64,
    applicable_when STRING[],
    related_concepts STRING[],
    embedding FLOAT[],
    content_hash STRING,
    last_updated TIMESTAMP,
    PRIMARY KEY (id)
)
""".strip()

# REL_TABLES_DDL stays in declaration order — ``Node`` must exist first
# (handled by listing NODE_TABLE_DDL before this in ALL_DDL).
#
# REFERS_TO carries a ``kind`` discriminator so we can encode the
# specific semantic without spawning yet another table for every
# variant the teacher introduces (e.g. "weakens", "is_prerequisite_of").
REL_TABLES_DDL: Final[tuple[str, ...]] = (
    "CREATE REL TABLE IF NOT EXISTS REFERS_TO(FROM Node TO Node, kind STRING)",
    "CREATE REL TABLE IF NOT EXISTS GENERATES(FROM Node TO Node)",
    "CREATE REL TABLE IF NOT EXISTS CONTROLS(FROM Node TO Node)",
    "CREATE REL TABLE IF NOT EXISTS COMBINES_WITH(FROM Node TO Node)",
    "CREATE REL TABLE IF NOT EXISTS CLASHES_WITH(FROM Node TO Node)",
    "CREATE REL TABLE IF NOT EXISTS EXAMPLE_OF(FROM Node TO Node)",
)

ALL_DDL: Final[tuple[str, ...]] = (NODE_TABLE_DDL, *REL_TABLES_DDL)

REL_TABLE_NAMES: Final[tuple[str, ...]] = (
    "REFERS_TO",
    "GENERATES",
    "CONTROLS",
    "COMBINES_WITH",
    "CLASHES_WITH",
    "EXAMPLE_OF",
)

NODE_TABLE_NAME: Final[str] = "Node"
