"""Data models for the retrieval pipeline (Phase 3).

Frozen slots-dataclasses — there's no ORM here, KuzuDB returns plain
tuples, so these are just thin value objects to keep the surface
between modules typed and obvious."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RetrievedNode:
    """One scored hit from the graph retrieval."""

    node_id: str
    level: int
    topic: str
    title: str
    body: str
    summary: str
    source: str
    source_authority: int
    score: float
