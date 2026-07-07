"""Cypher retrieval over the fractal Bazi graph (Phase 3.2).

Strategy:
1. From the extracted concepts find every ``Node`` whose
   ``related_concepts`` array overlaps. Score by overlap count + a
   bonus for higher levels (L7 predictive heuristics outweigh L1
   foundations when both match) and source_authority.
2. Optional 1-hop expansion: pull cross-document edges from the top
   hits (a typed ``COMBINES_WITH`` / ``EXAMPLE_OF`` / ``CLASHES_WITH``
   to a real doc) so the LLM sees the supporting context, not just
   the directly-matched rule.
3. Always exclude stub nodes (``topic = 'stub'``) — they have empty
   bodies and only exist as edge targets.
4. Wave 7 Phase 5: filter by ``school`` — when the user picked a
   school, only ``universal`` + that school's docs are surfaced. ``None``
   = no filter (legacy callers and forecast generators that don't
   thread a school yet).
"""

from __future__ import annotations

import logging
from typing import Final, Literal

import kuzu

from ai.rag.models import RetrievedNode
from ai.rag.store import open_connection

logger = logging.getLogger(__name__)

# Mirrors ``ai.prompts.SchoolName`` (kept duplicated here to avoid an
# import from the bot stack into the RAG module — RAG must stay free
# of bot/ dependencies per ADR-001 layering).
SchoolFilter = Literal["classic", "edoha", "modern"]

# Score weights. Levels run 1..7; higher = more applied. The
# multiplier keeps a single-concept L7 match (3.7) ahead of a
# two-concept L1 match (2.1) — applied knowledge wins ties.
_LEVEL_WEIGHT: Final[float] = 0.4
_AUTHORITY_WEIGHT: Final[float] = 0.05


def _score(level: int, source_authority: int, overlap: int) -> float:
    return overlap + level * _LEVEL_WEIGHT + source_authority * _AUTHORITY_WEIGHT


def _as_int(v: object, default: int = 0) -> int:
    """Narrow KuzuDB row cell (typed as ``object``) into an int — Kuzu
    returns Python ints for INT64 columns, but mypy can't see that."""
    if isinstance(v, int):
        return v
    if isinstance(v, str | float):
        try:
            return int(v)
        except (TypeError, ValueError):
            return default
    return default


def _row_to_node(row: list[object], score: float) -> RetrievedNode:
    return RetrievedNode(
        node_id=str(row[0]),
        level=_as_int(row[1]),
        topic=str(row[2]),
        title=str(row[3]),
        body=str(row[4]),
        summary=str(row[5]),
        source=str(row[6]),
        source_authority=_as_int(row[7]),
        score=score,
    )


def _school_clause(school: SchoolFilter | None) -> str:
    """Build the school-filter WHERE fragment.

    ``None`` = no filter (every non-stub node is fair game).
    ``classic|edoha|modern`` = ``universal`` ∪ ``<chosen>``. The clause
    tolerates missing values (legacy DB rows pre-Phase-5 default to
    ``universal`` via the bootstrap migration; brand-new stubs created
    by ``_ensure_stub_node`` also start as ``universal``).
    """
    if school is None:
        return ""
    return " AND (n.school IS NULL OR n.school IN ['universal', $school])"


def _query_concept_hits(
    conn: kuzu.Connection,
    concepts: list[str],
    *,
    school: SchoolFilter | None = None,
) -> dict[str, tuple[list[object], int]]:
    """High-precision path — nodes whose ``related_concepts`` array
    intersects ``concepts``. Returns ``{node_id: (row, overlap)}``."""
    if not concepts:
        return {}
    school_clause = _school_clause(school)
    params: dict[str, object] = {"concepts": concepts}
    if school is not None:
        params["school"] = school
    result = conn.execute(
        f"""
        MATCH (n:Node)
        WHERE n.topic <> 'stub'{school_clause}
        UNWIND n.related_concepts AS c
        WITH n, c WHERE c IN $concepts
        WITH n, count(c) AS overlap
        RETURN n.id, n.level, n.topic, n.title, n.body, n.summary,
               n.source, n.source_authority, overlap
        """,
        params,
    )
    hits: dict[str, tuple[list[object], int]] = {}
    while result.has_next():  # type: ignore[union-attr]
        row = list(result.get_next())  # type: ignore[union-attr]
        overlap = _as_int(row[8])
        hits[str(row[0])] = (row, overlap)
    return hits


def _query_title_hits(
    conn: kuzu.Connection,
    tokens: list[str],
    *,
    school: SchoolFilter | None = None,
) -> dict[str, tuple[list[object], int]]:
    """High-recall path — every token (len ≥ 4) is checked as a
    substring of the lowercased title. We do one query per token rather
    than a single ``OR`` of N ``CONTAINS`` predicates because Kuzu's
    planner doesn't index ``CONTAINS`` patterns; running N short
    queries against ~33 real nodes is still trivial.
    """
    out: dict[str, tuple[list[object], int]] = {}
    if not tokens:
        return out
    school_clause = _school_clause(school)
    for tok in tokens:
        params: dict[str, object] = {"tok": tok}
        if school is not None:
            params["school"] = school
        result = conn.execute(
            f"""
            MATCH (n:Node)
            WHERE n.topic <> 'stub' AND lower(n.title) CONTAINS $tok{school_clause}
            RETURN n.id, n.level, n.topic, n.title, n.body, n.summary,
                   n.source, n.source_authority
            """,
            params,
        )
        while result.has_next():  # type: ignore[union-attr]
            row = list(result.get_next())  # type: ignore[union-attr]
            node_id = str(row[0])
            prev = out.get(node_id)
            if prev is None:
                out[node_id] = ([*row, 0], 1)
            else:
                # Bump the title-match count for this node
                out[node_id] = (prev[0], prev[1] + 1)
    return out


def _expand_neighbours(
    conn: kuzu.Connection,
    seed_ids: list[str],
    *,
    school: SchoolFilter | None = None,
) -> list[RetrievedNode]:
    """For each seed, pull neighbouring real-doc nodes one hop away on
    *typed* edges (COMBINES_WITH / EXAMPLE_OF / CLASHES_WITH /
    GENERATES / CONTROLS). Plain REFERS_TO is excluded — it's the
    bulk of the graph and would flood the result with noise.

    ``school`` filter applies to the *target* (b) — supporting context
    pulled into a school-scoped consultation must come from the same
    school's overlay (or ``universal``).
    """
    if not seed_ids:
        return []
    # The original WHERE binds ``b`` as the neighbour target — apply
    # school filter to it just like in the seed queries.
    school_extra = (
        " AND (b.school IS NULL OR b.school IN ['universal', $school])"
        if school is not None
        else ""
    )
    params: dict[str, object] = {"ids": seed_ids}
    if school is not None:
        params["school"] = school
    typed_edges = "['COMBINES_WITH','EXAMPLE_OF','CLASHES_WITH','GENERATES','CONTROLS']"
    result = conn.execute(
        f"""
        MATCH (a:Node)-[r]->(b:Node)
        WHERE a.id IN $ids
          AND b.topic <> 'stub'
          AND label(r) IN {typed_edges}{school_extra}
        RETURN DISTINCT b.id, b.level, b.topic, b.title, b.body, b.summary,
                        b.source, b.source_authority
        """,
        params,
    )
    out: list[RetrievedNode] = []
    while result.has_next():  # type: ignore[union-attr]
        row = result.get_next()  # type: ignore[union-attr]
        out.append(
            _row_to_node(
                [*row, 0],  # padding for the unused overlap column shape
                score=_score(
                    level=_as_int(row[1]),
                    source_authority=_as_int(row[7]),
                    overlap=0,
                )
                * 0.5,  # neighbours are supporting context, not the answer
            )
        )
    return out


def retrieve_nodes(
    concepts: list[str],
    *,
    title_tokens: list[str] | None = None,
    top_k: int = 5,
    expand_neighbours: bool = True,
    school: SchoolFilter | None = None,
) -> list[RetrievedNode]:
    """End-to-end retrieval.

    Two complementary paths are merged:

    1. **Concept-overlap** — high-precision, drives the score by how
       many of the question's vocabulary-matched concepts appear in
       the node's ``related_concepts`` array.
    2. **Title-substring** — high-recall fallback, catches natural
       Russian phrasings like "столпы удачи" → matches title
       *Столпы Удачи и циклы времени* even when the concepts list
       came back empty (English-leaning vocabulary missed them).

    Scores are summed across paths; ties broken by level then authority.
    Returns up to ``top_k`` real-doc hits plus, optionally, their typed
    neighbours (also capped at ``top_k``). ``[]`` if the KB is empty
    or unreachable — caller (``compose_messages``) then skips the
    [KNOWLEDGE] block.
    """
    if not concepts and not title_tokens:
        return []
    conn = open_connection()
    if conn is None:
        return []

    try:
        concept_hits = _query_concept_hits(conn, concepts, school=school)
        title_hits = _query_title_hits(conn, title_tokens or [], school=school)
    except RuntimeError as exc:
        logger.warning("rag.retrieve.query_failed", extra={"error": str(exc)})
        return []

    merged: dict[str, tuple[list[object], int, int]] = {}
    for node_id, (row, overlap) in concept_hits.items():
        merged[node_id] = (row, overlap, 0)
    for node_id, (row, title_match) in title_hits.items():
        if node_id in merged:
            existing_row, existing_overlap, _ = merged[node_id]
            merged[node_id] = (existing_row, existing_overlap, title_match)
        else:
            merged[node_id] = (row, 0, title_match)

    scored: list[RetrievedNode] = []
    for _, (row, overlap, title_match) in merged.items():
        level = _as_int(row[1])
        auth = _as_int(row[7])
        s = _score(level=level, source_authority=auth, overlap=overlap + title_match)
        scored.append(_row_to_node(row, s))
    scored.sort(key=lambda n: (-n.score, -n.level, -n.source_authority))
    direct = scored[:top_k]

    if not expand_neighbours or not direct:
        return direct

    try:
        neighbours = _expand_neighbours(conn, [n.node_id for n in direct], school=school)
    except RuntimeError as exc:
        logger.warning("rag.retrieve.expand_failed", extra={"error": str(exc)})
        return direct

    seen = {n.node_id for n in direct}
    extra = [n for n in neighbours if n.node_id not in seen][:top_k]
    return [*direct, *extra]
