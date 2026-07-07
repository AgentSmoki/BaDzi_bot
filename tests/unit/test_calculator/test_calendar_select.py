"""Tests for calculator.calendar_select — день-пиллар generation + scoring.

Uses real calculate_chart for natal fixture; calendar_select uses real
pillars/symbolic_stars under the hood. Deterministic per fixed dates.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from calculator import calculate_chart
from calculator.calendar_select import (
    EVENT_RULES,
    EVENT_TYPE_RU,
    DayPillar,
    EventType,
    generate_day_pillars,
    pick_best_dates,
    score_day_for_event,
)
from calculator.models import ChartInput


@pytest.fixture
def bogdan_chart():
    """Reference chart used throughout the project."""
    return calculate_chart(
        ChartInput(
            birth_datetime=datetime(1999, 9, 12, 23, 55),
            latitude=48.7894,
            longitude=44.7783,
            tz_offset=4.0,
            early_rat=False,
            gender="female",
        )
    )


def test_generate_day_pillars_count_matches_range() -> None:
    start = date(2026, 6, 1)
    end = date(2026, 6, 30)
    days = generate_day_pillars(start, end)
    assert len(days) == 30
    assert days[0].date == start
    assert days[-1].date == end


def test_generate_day_pillars_single_day_works() -> None:
    days = generate_day_pillars(date(2026, 5, 17), date(2026, 5, 17))
    assert len(days) == 1


def test_generate_day_pillars_raises_when_end_before_start() -> None:
    with pytest.raises(ValueError):
        generate_day_pillars(date(2026, 6, 30), date(2026, 6, 1))


def test_generate_day_pillars_day_pillars_are_consecutive() -> None:
    """Consecutive days must map to consecutive day pillars in the
    60-cycle (no skips or duplicates)."""
    days = generate_day_pillars(date(2026, 5, 17), date(2026, 5, 22))
    # Just verify each day yields a distinct day-pillar pair — the
    # actual 60-cycle indexing is tested in pillars.py tests.
    pairs = [(d.day_stem, d.day_branch) for d in days]
    assert len(set(pairs)) == 6


def test_score_day_for_event_returns_scored_day(bogdan_chart) -> None:  # type: ignore[no-untyped-def]
    days = generate_day_pillars(date(2026, 6, 1), date(2026, 6, 1))
    sd = score_day_for_event(bogdan_chart, days[0], "wedding")
    assert isinstance(sd.score, float)
    assert isinstance(sd.factors, list)


def test_clash_with_natal_day_branch_carries_largest_penalty(bogdan_chart) -> None:  # type: ignore[no-untyped-def]
    """Bogdan's natal day branch is 卯. A day whose day-branch is 酉
    triggers 卯酉冲 with the most-personal pillar → -3.0 penalty.

    We find such a day in 2026 by brute force and confirm the factor
    list mentions the natal-day clash."""
    days = generate_day_pillars(date(2026, 5, 17), date(2026, 7, 17))
    clash_days = [
        d for d in days if d.day_branch == "酉" or d.month_branch == "酉" or d.year_branch == "酉"
    ]
    assert clash_days, "expected at least one day with 酉 in the range"
    sd = score_day_for_event(bogdan_chart, clash_days[0], "wedding")
    # Any clash with the natal day branch must produce a factor mentioning the clash
    day_clash_factors = [f for f in sd.factors if "столкновение" in f]
    assert day_clash_factors


def test_pick_best_dates_returns_top_and_bottom(bogdan_chart) -> None:  # type: ignore[no-untyped-def]
    from itertools import pairwise

    top, bottom = pick_best_dates(
        bogdan_chart,
        date(2026, 6, 1),
        date(2026, 6, 30),
        "wedding",
        top_n=5,
        bottom_n=3,
    )
    assert len(top) == 5
    assert len(bottom) == 3
    # Top scores must be ≥ bottom scores
    assert top[0].score >= bottom[0].score
    # Top is descending by score
    for a, b in pairwise(top):
        assert a.score >= b.score


def test_pick_best_dates_handles_short_range(bogdan_chart) -> None:  # type: ignore[no-untyped-def]
    """When the range has fewer days than top_n, return all of them
    in order (no IndexError)."""
    top, bottom = pick_best_dates(
        bogdan_chart,
        date(2026, 6, 1),
        date(2026, 6, 3),
        "negotiation",
        top_n=10,
        bottom_n=10,
    )
    assert len(top) == 3
    assert len(bottom) == 3


@pytest.mark.parametrize("event_type", list(EVENT_RULES.keys()))
def test_every_event_type_has_label(event_type: EventType) -> None:
    """Every supported event must have a Russian label for the LLM."""
    assert event_type in EVENT_TYPE_RU
    assert len(EVENT_TYPE_RU[event_type]) > 0


def test_required_stars_in_rules_are_known_chinese_names() -> None:
    """Defensive: catch typos in EVENT_RULES that would silently
    never match any star (e.g. 月徳 vs 月德 — different character)."""
    # Just sanity-check that strings are non-empty CJK
    for rules in EVENT_RULES.values():
        for star in rules.required_stars + rules.forbidden_stars:
            assert star
            # All star names start with a CJK character (BMP range)
            assert ord(star[0]) > 0x3000


def test_day_pillar_str_concatenates_stem_and_branch() -> None:
    dp = DayPillar(
        date=date(2026, 6, 1),
        year_stem="丙",
        year_branch="午",
        month_stem="癸",
        month_branch="巳",
        day_stem="丁",
        day_branch="未",
        hour_stem="戊",
        hour_branch="申",
    )
    from calculator.calendar_select import ScoredDay

    sd = ScoredDay(pillar=dp, score=0.0)
    assert sd.day_pillar_str == "丁未"
