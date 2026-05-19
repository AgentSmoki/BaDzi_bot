"""Ingestion pipeline for the teacher knowledge base (plan 1.9 Phase 2).

Public surface:
- ``parse_md_file`` / ``scan_kb`` from :mod:`knowledge.ingest.parser`
- ``IngestedDoc``, ``Triplet`` from :mod:`knowledge.ingest.models`
- ``extract_triplets`` from :mod:`knowledge.ingest.extract`
- ``upsert_doc`` from :mod:`knowledge.ingest.writer`
- ``main`` (CLI entry) from :mod:`knowledge.ingest.cli`
"""

from knowledge.ingest.extract import extract_triplets, sidecar_path_for
from knowledge.ingest.models import IngestedDoc, IngestState, Triplet
from knowledge.ingest.parser import parse_md_file, scan_kb
from knowledge.ingest.writer import upsert_doc

__all__ = [
    "IngestState",
    "IngestedDoc",
    "Triplet",
    "extract_triplets",
    "parse_md_file",
    "scan_kb",
    "sidecar_path_for",
    "upsert_doc",
]
