"""Tests for ai.calendar_parse — intent detection + date range parsing.

Pure-function module, deterministic given a fixed ``now`` date.
"""

from __future__ import annotations

from datetime import date

import pytest

from ai.calendar_parse import detect_calendar_request

_NOW = date(2026, 5, 17)


def test_returns_none_for_non_calendar_question() -> None:
    assert detect_calendar_request("что значит мой Господин дня?", now=_NOW) is None
    assert detect_calendar_request("расскажи про карму", now=_NOW) is None


def test_detects_wedding_with_next_3_months() -> None:
    req = detect_calendar_request("Какие лучшие даты для свадьбы в ближайшие 3 месяца?", now=_NOW)
    assert req is not None
    assert req.event_type == "wedding"
    assert req.start == _NOW
    assert req.end == date(2026, 5, 17) + (date(2026, 8, 15) - date(2026, 5, 17))


def test_detects_negotiation_with_explicit_month() -> None:
    req = detect_calendar_request("когда лучше провести переговоры в июне?", now=_NOW)
    assert req is not None
    assert req.event_type == "negotiation"
    assert req.start.month == 6
    assert req.end.month == 6
    assert req.end.day == 30


def test_detects_surgery_with_default_horizon() -> None:
    req = detect_calendar_request("когда лучше планировать операцию?", now=_NOW)
    assert req is not None
    assert req.event_type == "surgery"
    # Default 30-day window when no horizon given
    assert (req.end - req.start).days == 30


def test_detects_contract_with_until_end_of_year() -> None:
    req = detect_calendar_request(
        "подскажи хорошие даты для подписания контракта до конца года",
        now=_NOW,
    )
    assert req is not None
    assert req.event_type == "contract"
    assert req.end == date(2026, 12, 31)


def test_detects_move_with_next_2_weeks() -> None:
    req = detect_calendar_request("когда лучше переезжать в следующие 2 недели?", now=_NOW)
    assert req is not None
    assert req.event_type == "move"
    assert (req.end - req.start).days == 14


def test_detects_launch_intent() -> None:
    req = detect_calendar_request("когда лучше запустить новый проект?", now=_NOW)
    assert req is not None
    assert req.event_type == "launch"


def test_calendar_intent_without_event_type_returns_event_type_none() -> None:
    """User asks 'когда лучшие дни в июне' without saying for what.
    Intent is detected, event_type stays None — handler can clarify."""
    req = detect_calendar_request("какие лучшие дни в июне?", now=_NOW)
    assert req is not None
    assert req.event_type is None
    assert req.start.month == 6


def test_horizon_clamped_to_max_when_excessive() -> None:
    """«следующие 24 месяца» should be capped to 365 days."""
    req = detect_calendar_request("лучшие даты для свадьбы в следующие 24 месяца", now=_NOW)
    assert req is not None
    assert (req.end - req.start).days <= 365


@pytest.mark.parametrize(
    ("text", "expected_type"),
    [
        ("когда лучше выйти замуж?", "wedding"),
        ("в какой день лучше всего подписать договор?", "contract"),
        ("лучшие даты для встречи с инвестором", "negotiation"),
        ("когда лучше операция", "surgery"),
        ("на какую дату лучше переезд", "move"),
        ("когда лучше открытие магазина", "launch"),
    ],
)
def test_each_event_type_keyword_set(text: str, expected_type: str) -> None:
    req = detect_calendar_request(text, now=_NOW)
    assert req is not None
    assert req.event_type == expected_type
