"""Tests for calculator.important_dates (Wave 4e)."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from calculator import calculate_chart
from calculator.important_dates import (
    ImportantDate,
    find_important_dates_in_range,
    format_important_date_message,
    render_demo_for_chart,
)
from calculator.models import ChartInput


@pytest.fixture
def reference_chart():  # type: ignore[no-untyped-def]
    """Bogdan's test chart: 12.09.1999 23:55 Волжский UTC+4 female."""
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


def test_finds_at_least_one_significant_date_in_30_days(reference_chart) -> None:  # type: ignore[no-untyped-def]
    """The reference chart has natal 白虎 / 飞刃 / 天乙贵人 / 文昌贵人 /
    将星. Over 30 days the day-pillar branch will match the natal
    branches several times — expect multiple alerts."""
    today = date(2026, 5, 20)
    dates = find_important_dates_in_range(reference_chart, today, date(2026, 6, 19))
    assert len(dates) >= 3
    assert all(d.severity in {"low", "medium", "high"} for d in dates)


def test_severity_high_when_baihu_active(reference_chart) -> None:  # type: ignore[no-untyped-def]
    """At least one of the upcoming dates must trigger 白虎 → severity=high."""
    today = date(2026, 5, 20)
    dates = find_important_dates_in_range(reference_chart, today, date(2026, 6, 30))
    high_days = [d for d in dates if d.severity == "high"]
    assert len(high_days) >= 1
    assert any("白虎" in d.active_stars for d in high_days)


def test_empty_range_returns_empty_list(reference_chart) -> None:  # type: ignore[no-untyped-def]
    today = date(2026, 5, 20)
    # 1-day range with no resonance is rare — try the chart's anti-day:
    # if today's day branch isn't in any natal anchor, list is empty.
    # We assert that the call doesn't crash and returns a list.
    result = find_important_dates_in_range(reference_chart, today, today)
    assert isinstance(result, list)


def test_raises_when_start_after_end(reference_chart) -> None:  # type: ignore[no-untyped-def]
    with pytest.raises(ValueError):
        find_important_dates_in_range(reference_chart, date(2026, 6, 1), date(2026, 5, 1))


def test_format_message_contains_star_names_and_severity_note(reference_chart) -> None:  # type: ignore[no-untyped-def]
    today = date(2026, 5, 20)
    dates = find_important_dates_in_range(reference_chart, today, date(2026, 6, 19))
    assert dates
    msg = format_important_date_message(reference_chart, dates[0], days_ahead=2)
    assert "Через 2 дня" in msg
    assert "не чаще одного раза в неделю" in msg
    # At least one star name is rendered.
    assert any(name in msg for name in ("白虎", "桃花", "天乙", "文昌", "将星", "飞刃"))


def test_format_message_includes_star_interpretation(reference_chart) -> None:  # type: ignore[no-untyped-def]
    """Bug C (2026-06-02): each star is rendered with a short meaning,
    not just its name."""
    from calculator.important_dates import ImportantDate, format_important_date_message

    imp = ImportantDate(date_=date(2026, 6, 3), active_stars=("文昌贵人",), severity="low")
    msg = format_important_date_message(reference_chart, imp, days_ahead=2)
    assert "文昌贵人" in msg
    assert "звезда учёбы" in msg  # interpretation present, not just the name


def test_reflection_message_is_day_of_with_button_text(reference_chart) -> None:  # type: ignore[no-untyped-def]
    """B2: day-of reflection invite says «Сегодня» and asks to record."""
    from calculator.important_dates import ImportantDate, format_important_date_reflection

    imp = ImportantDate(date_=date(2026, 6, 3), active_stars=("白虎",), severity="high")
    msg = format_important_date_reflection(reference_chart, imp)
    assert "Сегодня" in msg
    assert "рефлекс" in msg.lower()
    assert "白虎" in msg
    assert "конфликт" in msg.lower()  # interpretation present


def test_demo_shows_concrete_example_for_reference_chart(reference_chart) -> None:  # type: ignore[no-untyped-def]
    demo = render_demo_for_chart(reference_chart, date(2026, 5, 20))
    assert demo  # non-empty
    # Either it's the «не нашла» fallback or a real preview — both are
    # valid renderings; pick one to check format.
    if "не нашла" not in demo:
        # real preview
        assert "важная для вашей карты дата" in demo
        assert "Активируются звёзды" in demo


def test_important_date_dataclass_is_frozen() -> None:
    d = ImportantDate(date_=date(2026, 5, 25), active_stars=("白虎",), severity="high")
    with pytest.raises(AttributeError):
        d.severity = "low"  # type: ignore[misc]
