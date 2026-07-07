"""KuzuDB-backed retrieval pipeline (plan 1.9 Phase 3).

Replaces the previous keyword-only loader. Public surface is
``load_knowledge_for_question(question, *, top_k=...) -> str`` so the
:func:`ai.temporal_context.compose_messages` call site doesn't change.

Internally:
1. :mod:`ai.rag.extract` — concept extraction from the question.
2. :mod:`ai.rag.retrieve` — Cypher query over KuzuDB.
3. :mod:`ai.rag.format` — render the ``[KNOWLEDGE]`` block body.
"""

from ai.rag.extract import extract_concepts
from ai.rag.format import format_knowledge_block
from ai.rag.public import load_knowledge_for_question
from ai.rag.retrieve import retrieve_nodes
from ai.rag.store import get_concept_vocabulary, open_connection

__all__ = [
    "extract_concepts",
    "format_knowledge_block",
    "get_concept_vocabulary",
    "load_knowledge_for_question",
    "open_connection",
    "retrieve_nodes",
]
