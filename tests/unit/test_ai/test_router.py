"""Tests for ai.router. Pure function, no I/O — easy to cover."""

from __future__ import annotations

import pytest

from ai.router import RouteDecision, route


def _decision_for(text: str) -> RouteDecision:
    return route(text)


@pytest.mark.parametrize(
    "text",
    [
        "Что такое день мастера?",
        "Кто я по карте Бацзы?",
        "Какой у меня день мастера?",
        "Помощь по интерпретации",
    ],
)
def test_short_factual_questions_route_to_simple(text: str) -> None:
    d = _decision_for(text)
    assert d.intent == "simple"
    # max_tokens sizing now lives in ai.budget (per-tier dynamic).
    # Router only classifies; budget knows how to scale.
    assert d.temperature < 0.55
    assert d.needs_temporal_context is False


@pytest.mark.parametrize(
    ("text", "expect_temporal"),
    [
        ("Расскажи про мою карту в общем.", False),
        ("Что меня ждёт в этом году?", True),
        ("Какие тенденции на ближайший период?", True),
        ("Что было в прошлом десятилетии?", True),
    ],
)
def test_normal_intent_with_or_without_temporal(text: str, expect_temporal: bool) -> None:
    d = _decision_for(text)
    assert d.intent == "normal"
    assert d.needs_temporal_context is expect_temporal


@pytest.mark.parametrize(
    "text",
    [
        "Почему у меня не складывается карьера несмотря на сильного Дневного Хозяина?",
        "В чём конфликт между моим столпом дня и месяцем?",
        "Сравни мои отношения с партнёром через десять лет.",
        "Если я перееду, что изменится в моём здоровье?",
    ],
)
def test_complex_questions_route_to_complex(text: str) -> None:
    d = _decision_for(text)
    assert d.intent == "complex"
    # max_tokens is sized in ai.budget per-tier — router only classifies.


def test_complex_question_with_temporal_keeps_temporal_context() -> None:
    d = _decision_for("Почему карьера сейчас тормозит, хотя ДМ сильный?")
    assert d.intent == "complex"
    assert d.needs_temporal_context is True


def test_decision_only_carries_intent_temperature_temporal() -> None:
    """RouteDecision is a *classifier* now — model + max_tokens belong
    in ai.fallback / ai.budget. Pin the shrunk surface so the next
    refactor doesn't accidentally re-attach model logic here."""
    d = _decision_for("Расскажи про карту.")
    fields = {f.name for f in d.__dataclass_fields__.values()}
    assert fields == {"intent", "temperature", "needs_temporal_context", "reason"}


def test_empty_text_routes_to_default_normal() -> None:
    d = _decision_for("")
    assert d.intent == "normal"
    assert d.needs_temporal_context is False


def test_yo_is_normalised() -> None:
    """`ё` and `е` should match the same keyword. Otherwise our
    Cyrillic dictionary would have to list both spellings."""
    a = _decision_for("Расскажи про прошлое в общем")
    b = _decision_for("Расскажи про прошлое в общем")
    assert a.intent == b.intent == "normal"
    assert a.needs_temporal_context is True


def test_decision_is_immutable() -> None:
    """RouteDecision is a frozen dataclass — callers can't mutate
    routing facts halfway through the request lifecycle."""
    from dataclasses import FrozenInstanceError

    d = _decision_for("Что такое 用神?")
    with pytest.raises(FrozenInstanceError):
        d.intent = "complex"  # type: ignore[misc]
