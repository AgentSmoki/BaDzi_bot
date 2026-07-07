"""Tests for date parsing in bot.routers.birth_data._parse_birth_date.

Wave 1a — добавлены ISO YYYY-MM-DD и 2-digit year forms (`88` → 1988).
The function is module-private but importable; we test it directly to
isolate parsing from FSM/handler concerns.
"""

from __future__ import annotations

from datetime import date

import pytest

from bot.routers.birth_data import _expand_2digit_year, _parse_birth_date

# ── 2-digit year cutoff ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("yy", "expected"),
    [
        (0, 2000),
        (15, 2015),
        (29, 2029),  # cutoff edge — last «modern»
        (30, 1930),  # cutoff edge — first «adult»
        (88, 1988),  # Bogdan's reference: 27.04.88
        (99, 1999),
    ],
)
def test_expand_2digit_year_cutoff_30(yy: int, expected: int) -> None:
    assert _expand_2digit_year(yy) == expected


# ── ISO format YYYY-MM-DD ────────────────────────────────────────────────


def test_iso_basic() -> None:
    assert _parse_birth_date("1990-05-15") == date(1990, 5, 15)


def test_iso_with_padding() -> None:
    assert _parse_birth_date("  1990-05-15  ") == date(1990, 5, 15)


def test_iso_single_digit_month_day() -> None:
    """Some users write 1990-5-7 instead of 1990-05-07."""
    assert _parse_birth_date("1990-5-7") == date(1990, 5, 7)


def test_iso_invalid_month_returns_none() -> None:
    assert _parse_birth_date("1990-13-15") is None


# ── Bogdan's case: 27.04.88 ──────────────────────────────────────────────


def test_dotted_2digit_year() -> None:
    """The exact format from Bogdan's roadmap pt 6 example."""
    assert _parse_birth_date("27.04.88") == date(1988, 4, 27)


def test_dotted_2digit_year_modern() -> None:
    """yy=15 stays in the 2000s."""
    assert _parse_birth_date("15.06.15") == date(2015, 6, 15)


def test_slashed_2digit_year() -> None:
    assert _parse_birth_date("27/04/88") == date(1988, 4, 27)


def test_dashed_2digit_year() -> None:
    assert _parse_birth_date("27-04-88") == date(1988, 4, 27)


def test_spaced_2digit_year() -> None:
    assert _parse_birth_date("27 04 88") == date(1988, 4, 27)


def test_packed_2digit_year() -> None:
    """ddmmyy (6 digits)."""
    assert _parse_birth_date("270488") == date(1988, 4, 27)


def test_packed_2digit_year_modern() -> None:
    """ddmmyy where yy<30 → 20XX."""
    assert _parse_birth_date("150615") == date(2015, 6, 15)


# ── Regression — existing 4-digit forms still work ───────────────────────


def test_full_4digit_year_dotted() -> None:
    assert _parse_birth_date("15.07.1990") == date(1990, 7, 15)


def test_full_4digit_year_packed() -> None:
    """ddmmyyyy (8 digits)."""
    assert _parse_birth_date("12091999") == date(1999, 9, 12)


def test_russian_words() -> None:
    """dateparser fallback path — natural language."""
    assert _parse_birth_date("15 июля 1990") == date(1990, 7, 15)


def test_empty_string_returns_none() -> None:
    assert _parse_birth_date("") is None


def test_garbage_returns_none() -> None:
    assert _parse_birth_date("привет мир") is None


# ── Edge cases ───────────────────────────────────────────────────────────


def test_iso_takes_precedence_over_dateparser() -> None:
    """1990-05-15 must be year-month-day, not parsed as DMY (5 May 1990
    vs 15 May 1990) which dateparser DMY mode would do wrong."""
    assert _parse_birth_date("1990-05-15") == date(1990, 5, 15)


def test_invalid_2digit_date_returns_none() -> None:
    """31.02.88 — Feb has no 31st."""
    assert _parse_birth_date("31.02.88") is None
