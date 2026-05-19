"""Public entrypoint kept in its own module to avoid an ``__init__``
import cycle: callers do ``from ai.rag import load_knowledge_for_question``
and the inner pipeline modules stay free to import from each other."""

from __future__ import annotations

from ai.rag.extract import extract_concepts, extract_search_tokens
from ai.rag.format import format_knowledge_block
from ai.rag.retrieve import retrieve_nodes


def load_knowledge_for_question(
    question: str,
    *,
    top_k: int = 5,
    concept_hints: list[str] | None = None,
) -> str:
    """End-to-end: question → concepts + title-tokens → graph hits →
    [KNOWLEDGE] body.

    ``concept_hints`` — extra concepts supplied by the fast skill-router
    (Wave 6, ADR-010). They're unioned with vocabulary-matched concepts
    so domain-specific tokens the router noticed (``七殺``, ``桃花``,
    ``столп месяца``) participate in the KuzuDB Cypher join even when
    they don't appear verbatim in the question text.

    Returns ``""`` when there's nothing to attach (no KB, no matches) —
    :func:`compose_messages` then omits the section so we don't ship a
    hollow heading.
    """
    concepts = list(extract_concepts(question))
    if concept_hints:
        # Union preserving order — extracted concepts come first (they
        # came from the question text directly), router hints append.
        seen = set(concepts)
        for hint in concept_hints:
            hint_norm = hint.strip()
            if hint_norm and hint_norm not in seen:
                concepts.append(hint_norm)
                seen.add(hint_norm)
    tokens = extract_search_tokens(question)
    if not concepts and not tokens:
        return ""
    nodes = retrieve_nodes(concepts, title_tokens=tokens, top_k=top_k)
    return format_knowledge_block(nodes)
