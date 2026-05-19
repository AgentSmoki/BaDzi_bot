"""Tests for ai.rag.format — knowledge block rendering + budget."""

from __future__ import annotations

from ai.rag.format import format_knowledge_block
from ai.rag.models import RetrievedNode


def _node(
    title: str = "T",
    body: str = "B",
    source_authority: int = 5,
    node_id: str = "n",
    score: float = 1.0,
) -> RetrievedNode:
    return RetrievedNode(
        node_id=node_id,
        level=5,
        topic="stars",
        title=title,
        body=body,
        summary="",
        source="test",
        source_authority=source_authority,
        score=score,
    )


def test_empty_list_returns_empty_string() -> None:
    assert format_knowledge_block([]) == ""


def test_single_node_renders_title_source_authority() -> None:
    node = _node(title="Белый Тигр", source_authority=10, body="Тело правила")
    out = format_knowledge_block([node])
    assert "Белый Тигр" in out
    assert "test" in out
    assert "10/10" in out
    assert "Тело правила" in out


def test_preamble_present() -> None:
    out = format_knowledge_block([_node()])
    assert "Релевантные правила" in out
    assert "учителя" in out


def test_budget_truncates_body() -> None:
    big_body = "AAA " * 5_000  # 20k chars
    out = format_knowledge_block([_node(body=big_body)], max_chars=2_000)
    assert len(out) <= 2_000 + 50  # tolerate small framing overhead
    assert "…" in out  # ellipsis marker


def test_budget_drops_later_nodes_cleanly() -> None:
    """If a later node's header alone wouldn't fit, the formatter
    must stop rather than emit a torn half-entry."""
    big = _node(title="first", body="A" * 1_800)
    second = _node(title="second", body="B" * 1_800)
    out = format_knowledge_block([big, second], max_chars=2_100)
    assert "first" in out
    # second's header may or may not fit, but the output must be a
    # complete prefix — no dangling `### second` without body.
    if "second" in out:
        assert "B" in out  # at least some body landed


def test_node_order_preserved() -> None:
    a = _node(title="alpha", node_id="a")
    b = _node(title="beta", node_id="b")
    out = format_knowledge_block([a, b], max_chars=100_000)
    assert out.index("alpha") < out.index("beta")


def test_chinese_terminology_survives() -> None:
    out = format_knowledge_block([_node(title="白虎", body="六冲 六合")], max_chars=100_000)
    assert "白虎" in out
    assert "六冲" in out
