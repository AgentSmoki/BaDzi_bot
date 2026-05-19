"""Public entrypoint kept in its own module to avoid an ``__init__``
import cycle: callers do ``from ai.rag import load_knowledge_for_question``
and the inner pipeline modules stay free to import from each other."""

from __future__ import annotations

from ai.rag.extract import extract_concepts, extract_search_tokens
from ai.rag.format import format_knowledge_block
from ai.rag.retrieve import retrieve_nodes


def load_knowledge_for_question(question: str, *, top_k: int = 5) -> str:
    """End-to-end: question → concepts + title-tokens → graph hits →
    [KNOWLEDGE] body.

    Returns ``""`` when there's nothing to attach (no KB, no matches) —
    :func:`compose_messages` then omits the section so we don't ship a
    hollow heading. The signature mirrors the now-removed
    keyword-only loader so the ``temporal_context`` call site is unchanged.
    """
    concepts = extract_concepts(question)
    tokens = extract_search_tokens(question)
    if not concepts and not tokens:
        return ""
    nodes = retrieve_nodes(concepts, title_tokens=tokens, top_k=top_k)
    return format_knowledge_block(nodes)
