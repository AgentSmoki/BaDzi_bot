"""Render retrieved nodes as the ``[KNOWLEDGE]`` block body (Phase 3.3).

Budget is in characters, not tokens — we don't want to drag a tokenizer
into the retrieval hot path. 15 000 chars maps to roughly 5 000 tokens
for our Russian + Chinese terminology mix, which matches the plan's
target. The Anthropic / OpenRouter wrappers see the final string and
charge by actual tokens; if we ever start clipping consultations we'll
revisit with a real tokenizer.
"""

from __future__ import annotations

from typing import Final

from ai.rag.models import RetrievedNode

_DEFAULT_BUDGET: Final[int] = 15_000


def _format_one(node: RetrievedNode, *, remaining: int) -> str | None:
    """Render a single node. Returns ``None`` if even the header
    wouldn't fit — that lets :func:`format_knowledge_block` stop early
    rather than emit a half-formed entry."""
    header = f"### {node.title} (источник: {node.source}, авторитет: {node.source_authority}/10)\n"
    if len(header) > remaining:
        return None
    body_budget = remaining - len(header) - 1  # -1 for trailing newline
    body = node.body
    if len(body) > body_budget:
        # Cut on a paragraph if we can — otherwise hard-cut + ellipsis.
        cut = body[:body_budget]
        nl = cut.rfind("\n\n")
        if nl > body_budget // 2:
            body = cut[:nl] + "\n\n…"
        else:
            body = cut + "…"
    return header + body + "\n"


def format_knowledge_block(nodes: list[RetrievedNode], *, max_chars: int = _DEFAULT_BUDGET) -> str:
    """Concatenate node renderings until the budget runs out. Empty
    list returns the empty string — :func:`compose_messages` then skips
    the [KNOWLEDGE] wrapper entirely so the prompt doesn't ship an
    empty stub heading."""
    if not nodes:
        return ""
    preamble = (
        "Релевантные правила и эвристики от учителя Богдана. Используй их\n"
        "как опору для интерпретации, ссылайся на конкретные пункты дословно:\n\n"
    )
    parts: list[str] = [preamble]
    used = len(preamble)
    for node in nodes:
        chunk = _format_one(node, remaining=max_chars - used)
        if chunk is None:
            break
        parts.append(chunk)
        used += len(chunk)
    return "".join(parts).rstrip()
