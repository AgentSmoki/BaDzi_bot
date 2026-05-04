"""Solar terms (24 Jie Qi) calculation tests."""

from datetime import UTC, datetime

import pytest

from calculator.solar_terms import (
    MONTH_JIE_INDICES,
    SOLAR_TERM_NAMES,
    solar_term_datetime,
    solar_term_jd,
)
from calculator.swiss import sun_longitude

_LON_TOLERANCE: float = 0.01  # degrees — precision of Newton-Raphson
_TIME_TOLERANCE_SEC: int = 300  # 5 minutes — acceptable datetime error


class TestSolarTermNames:
    def test_count(self) -> None:
        assert len(SOLAR_TERM_NAMES) == 24

    def test_first_is_chunfen(self) -> None:
        assert SOLAR_TERM_NAMES[0] == "春分"

    def test_liqian_at_index_21(self) -> None:
        # 立春 corresponds to λ = 315° = index 21
        assert SOLAR_TERM_NAMES[21] == "立春"

    def test_dongzhi_at_index_18(self) -> None:
        assert SOLAR_TERM_NAMES[18] == "冬至"

    def test_month_jie_count(self) -> None:
        assert len(MONTH_JIE_INDICES) == 12


class TestSolarTermJd:
    def test_vernal_equinox_2000_longitude(self) -> None:
        # 春分 λ = 0°
        jd = solar_term_jd(2000, 0)
        assert (
            abs(sun_longitude(jd) % 360.0) < _LON_TOLERANCE
            or abs(sun_longitude(jd) - 360.0) < _LON_TOLERANCE
        )

    def test_summer_solstice_2000_longitude(self) -> None:
        jd = solar_term_jd(2000, 6)
        assert abs(sun_longitude(jd) - 90.0) < _LON_TOLERANCE

    def test_autumnal_equinox_2000_longitude(self) -> None:
        jd = solar_term_jd(2000, 12)
        assert abs(sun_longitude(jd) - 180.0) < _LON_TOLERANCE

    def test_winter_solstice_2000_longitude(self) -> None:
        jd = solar_term_jd(2000, 18)
        assert abs(sun_longitude(jd) - 270.0) < _LON_TOLERANCE

    def test_liqian_2000_longitude(self) -> None:
        # 立春 λ = 315°
        jd = solar_term_jd(2000, 21)
        assert abs(sun_longitude(jd) - 315.0) < _LON_TOLERANCE

    def test_invalid_index_raises(self) -> None:
        with pytest.raises(ValueError, match="term_index"):
            solar_term_jd(2000, 24)

    def test_negative_index_raises(self) -> None:
        with pytest.raises(ValueError, match="term_index"):
            solar_term_jd(2000, -1)

    def test_terms_monotonically_increasing(self) -> None:
        # Each term JD must be greater than the previous within the same year
        # (terms 19-23 wrap before VE, so skip cross-year check)
        jds = [solar_term_jd(2000, i) for i in range(24)]
        # Terms 0..18 (spring to winter solstice) must be strictly increasing
        for i in range(1, 19):
            assert jds[i] > jds[i - 1], f"term {i} not after term {i - 1}"


class TestSolarTermDatetime:
    def test_vernal_equinox_2000_datetime(self) -> None:
        # 2000-03-20 07:35 UTC
        dt = solar_term_datetime(2000, 0)
        ref = datetime(2000, 3, 20, 7, 35, tzinfo=UTC)
        assert dt.tzinfo is not None
        assert abs((dt - ref).total_seconds()) < _TIME_TOLERANCE_SEC

    def test_summer_solstice_2000_datetime(self) -> None:
        dt = solar_term_datetime(2000, 6)
        ref = datetime(2000, 6, 21, 1, 48, tzinfo=UTC)
        assert abs((dt - ref).total_seconds()) < _TIME_TOLERANCE_SEC

    def test_winter_solstice_2000_datetime(self) -> None:
        dt = solar_term_datetime(2000, 18)
        ref = datetime(2000, 12, 21, 13, 37, tzinfo=UTC)
        assert abs((dt - ref).total_seconds()) < _TIME_TOLERANCE_SEC

    def test_liqian_2000_in_february(self) -> None:
        dt = solar_term_datetime(2000, 21)
        assert dt.year == 2000
        assert dt.month == 2
        assert dt.day == 4

    def test_result_is_utc(self) -> None:
        dt = solar_term_datetime(2000, 6)
        assert dt.tzinfo is UTC
