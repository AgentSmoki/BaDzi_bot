"""True Solar Time calculation tests.

Reference EoT values (Jean Meeus / NOAA):
  2000-02-12 12:00 UTC  →  EoT ≈ -14.24 min  (sundial behind clock)
  2000-11-03 12:00 UTC  →  EoT ≈ +16.43 min  (sundial ahead of clock)
  2000-04-15 12:00 UTC  →  EoT ≈   0.00 min  (near zero crossing)
"""

from datetime import UTC, datetime, timedelta

import pytest

from calculator.swiss import julian_day
from calculator.true_solar_time import equation_of_time, true_solar_time

_EoT_TOLERANCE_MIN: float = 0.5  # acceptable EoT error in minutes
_TST_TOLERANCE_SEC: float = 30.0  # acceptable TST error in seconds


class TestEquationOfTime:
    def test_february_negative(self) -> None:
        jd = julian_day(datetime(2000, 2, 12, 12, 0, tzinfo=UTC))
        assert abs(equation_of_time(jd) - (-14.24)) < _EoT_TOLERANCE_MIN

    def test_november_positive(self) -> None:
        jd = julian_day(datetime(2000, 11, 3, 12, 0, tzinfo=UTC))
        assert abs(equation_of_time(jd) - 16.43) < _EoT_TOLERANCE_MIN

    def test_april_near_zero(self) -> None:
        jd = julian_day(datetime(2000, 4, 15, 12, 0, tzinfo=UTC))
        assert abs(equation_of_time(jd)) < 1.0

    def test_range_bounded(self) -> None:
        # EoT never exceeds ±20 minutes
        for month in range(1, 13):
            jd = julian_day(datetime(2000, month, 15, 12, 0, tzinfo=UTC))
            assert abs(equation_of_time(jd)) < 20.0


class TestTrueSolarTime:
    def test_naive_datetime_raises(self) -> None:
        with pytest.raises(ValueError, match="UTC"):
            true_solar_time(datetime(2000, 1, 1, 12), longitude=0.0)

    def test_greenwich_longitude_zero(self) -> None:
        # At 0° longitude on Apr 15 (EoT ≈ 0), TST ≈ UTC
        utc = datetime(2000, 4, 15, 12, 0, 0, tzinfo=UTC)
        tst = true_solar_time(utc, longitude=0.0)
        diff_sec = abs((tst - utc.replace(tzinfo=None)).total_seconds())
        assert diff_sec < 60.0  # within 1 minute

    def test_east_longitude_offset(self) -> None:
        # Moscow 37.62°E → LMT offset = 37.62/15 = +2.508 h from UTC
        utc = datetime(2000, 4, 15, 12, 0, 0, tzinfo=UTC)
        tst = true_solar_time(utc, longitude=37.62)
        lmt_offset_hours = 37.62 / 15.0
        expected_lmt = utc.replace(tzinfo=None) + timedelta(hours=lmt_offset_hours)
        # On Apr 15 EoT ≈ 0, so TST ≈ LMT within 1 minute
        diff_sec = abs((tst - expected_lmt).total_seconds())
        assert diff_sec < 60.0

    def test_west_longitude_offset(self) -> None:
        # New York -74°W → LMT offset = -74/15 = -4.933 h
        utc = datetime(2000, 4, 15, 12, 0, 0, tzinfo=UTC)
        tst = true_solar_time(utc, longitude=-74.0)
        lmt_offset_hours = -74.0 / 15.0
        expected_lmt = utc.replace(tzinfo=None) + timedelta(hours=lmt_offset_hours)
        diff_sec = abs((tst - expected_lmt).total_seconds())
        assert diff_sec < 60.0

    def test_eot_applied(self) -> None:
        # Nov 3 EoT ≈ +16.4 min → TST should be ~16 min ahead of LMT
        utc = datetime(2000, 11, 3, 12, 0, 0, tzinfo=UTC)
        tst = true_solar_time(utc, longitude=0.0)
        lmt = utc.replace(tzinfo=None)
        diff_min = (tst - lmt).total_seconds() / 60.0
        assert abs(diff_min - 16.43) < _EoT_TOLERANCE_MIN

    def test_result_is_naive(self) -> None:
        utc = datetime(2000, 6, 15, 12, 0, tzinfo=UTC)
        tst = true_solar_time(utc, longitude=55.0)
        assert tst.tzinfo is None
