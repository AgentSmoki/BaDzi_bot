"""Tests for calculator.age_utils (Wave 7 — возрастные метафоры).

Pure functions, no I/O. ``today`` пиннится в каждом тесте — никакой
зависимости от даты прогона.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest

from calculator.age_utils import age_band_label, client_age_years


class TestClientAgeYears:
    def test_birthday_already_passed_this_year(self) -> None:
        born = datetime(1990, 3, 10, 12, 0)
        assert client_age_years(born, today=date(2026, 6, 10)) == 36

    def test_birthday_not_yet_this_year(self) -> None:
        born = datetime(1990, 9, 12, 23, 55)
        assert client_age_years(born, today=date(2026, 6, 10)) == 35

    def test_birthday_today_counts_full_year(self) -> None:
        born = datetime(1990, 6, 10, 8, 0)
        assert client_age_years(born, today=date(2026, 6, 10)) == 36

    def test_day_before_birthday_still_previous_age(self) -> None:
        born = datetime(1990, 6, 11, 8, 0)
        assert client_age_years(born, today=date(2026, 6, 10)) == 35

    def test_leap_day_birth_handled(self) -> None:
        # 29 февраля: в невисокосном году день рождения «наступает» 1 марта.
        born = datetime(2000, 2, 29, 10, 0)
        assert client_age_years(born, today=date(2026, 2, 28)) == 25
        assert client_age_years(born, today=date(2026, 3, 1)) == 26

    def test_future_birth_clamps_to_zero(self) -> None:
        # Defensive: данные карты могут быть кривыми — возраст не уходит
        # в минус.
        born = datetime(2030, 1, 1, 0, 0)
        assert client_age_years(born, today=date(2026, 6, 10)) == 0


class TestAgeBandLabel:
    @pytest.mark.parametrize(
        ("age", "label"),
        [
            (0, "до 25"),
            (24, "до 25"),
            (25, "25-35"),
            (34, "25-35"),
            (35, "35-45"),
            (44, "35-45"),
            (45, "45-60"),
            (59, "45-60"),
            (60, "60+"),
            (95, "60+"),
        ],
    )
    def test_band_boundaries(self, age: int, label: str) -> None:
        assert age_band_label(age) == label
