"""Data models for the ingestion pipeline (Phase 2).

These are frozen dataclasses, not Pydantic — there's no API boundary
here, the values are produced and consumed only inside the ingest CLI.
Frozen ⇒ usable as dict keys + safe to pass through threads.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Final, Literal

# The set of relations we store as separate REL TABLEs in KuzuDB. Anything
# else gets folded into REFERS_TO with a ``kind`` discriminator, so the
# extractor never has to add new tables on the fly.
RelationKind = Literal[
    "refers_to",
    "generates",
    "controls",
    "combines_with",
    "clashes_with",
    "example_of",
]

REL_KINDS: Final[tuple[RelationKind, ...]] = (
    "refers_to",
    "generates",
    "controls",
    "combines_with",
    "clashes_with",
    "example_of",
)

# Wave 7 Phase 5 — three coexisting interpretation schools (+ universal
# as the catch-all default for shared base theory).
SchoolValue = Literal["universal", "classic", "edoha", "modern"]
"""Frontmatter ``school:`` values accepted by the ingest pipeline.
Mirrors ``ai.prompts.SchoolName`` plus the ``universal`` bucket for
docs that apply across all schools (10 stems, 12 branches, cycles,
clashes — the shared theory)."""

VALID_SCHOOLS: Final[frozenset[str]] = frozenset({"universal", "classic", "edoha", "modern"})
"""Runtime guard for frontmatter validation — parser uses this to fall
back to ``universal`` on typos rather than ingest a bogus value."""


@dataclass(frozen=True, slots=True)
class IngestedDoc:
    """One parsed knowledge-base markdown file.

    ``content_hash`` is a sha256 of the *body* (not frontmatter). Frontmatter
    edits (typo in title, bumping ``last_updated``) shouldn't trigger a
    re-extract — only material changes to the text the LLM would reason
    over should invalidate the previous extraction.

    ``node_id`` is the stable graph identifier: posix-style relative path
    from the KB root, no extension. Easy to reason about, stable across
    machines, survives a ``mv`` only if you remember to rewrite the
    sidecar — which is a feature, not a bug (you'll want a fresh extract
    after a real rename anyway).
    """

    path: Path
    node_id: str
    level: int
    topic: str
    title: str
    body: str
    summary: str
    source: str
    source_authority: int
    applicable_when: tuple[str, ...]
    related_concepts: tuple[str, ...]
    last_updated: datetime
    content_hash: str
    # Wave 7 Phase 5 — interpretation school this doc belongs to.
    # Defaults to ``universal`` in the parser when frontmatter omits it,
    # so legacy docs ingested before Phase 5 (and test fixtures that
    # don't care about school) don't break. Placed at the end of the
    # field list so positional callers and KW-only callers both keep
    # working without rewrites.
    school: SchoolValue = "universal"


@dataclass(frozen=True, slots=True)
class Triplet:
    """A (subject, relation, object) edge produced by the extractor.

    ``source`` is either ``"frontmatter"`` (deterministic heuristic from
    related_concepts) or ``"subagent"`` (sidecar .triplets.json). We
    keep the provenance so retrieval can boost subagent-extracted edges
    if needed, and so we can audit later.

    ``object_node_id`` may point at a node that doesn't exist yet —
    the writer creates a stub Node for missing targets so edges are
    always insertable in one pass.
    """

    subject_node_id: str
    relation: RelationKind
    object_node_id: str
    source: Literal["frontmatter", "subagent"]


@dataclass(slots=True)
class IngestState:
    """Tracked in ``_ingest_state.json`` next to the KuzuDB. Used by
    ``--incremental`` to skip files whose body hash hasn't changed."""

    # path-as-posix-string -> content_hash
    hashes: dict[str, str] = field(default_factory=dict)
    last_run: str = ""
    schema_version: int = 1

    def needs_update(self, doc: IngestedDoc) -> bool:
        return self.hashes.get(doc.path.as_posix()) != doc.content_hash

    def mark_ingested(self, doc: IngestedDoc) -> None:
        self.hashes[doc.path.as_posix()] = doc.content_hash
