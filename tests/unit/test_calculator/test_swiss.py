"""Swiss Ephemeris wrapper tests.

Astronomical reference points (UTC):
  Summer solstice    2000-06-21 01:48 → λ ≈  90°
  Autumnal equinox   2000-09-22 17:27 → λ ≈ 180°
  Winter solstice    2000-12-21 13:37 → λ ≈ 270°
  Vernal equinox     2001-03-20 13:31 → λ ≈   0°/360°
"""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from calculator.swiss import julian_day, set_ephemeris_path, sun_longitude

_TOLERANCE_DEG: float = 1.0  # acceptable error for equinox/solstice tests


class TestJulianDay:
    def test_j2000_epoch(self) -> None:
        # J2000.0 = 2000-01-01 12:00:00 UTC → JD 2451545.0 (exact by definition)
        jd = julian_day(datetime(2000, 1, 1, 12, 0, 0, tzinfo=UTC))
        assert abs(jd - 2451545.0) < 1e-5

    def test_monotonically_increasing(self) -> None:
        jd1 = julian_day(datetime(2000, 1, 1, tzinfo=UTC))
        jd2 = julian_day(datetime(2000, 1, 2, tzinfo=UTC))
        assert jd2 - jd1 == pytest.approx(1.0, abs=1e-5)

    def test_naive_datetime_raises(self) -> None:
        with pytest.raises(ValueError, match="UTC"):
            julian_day(datetime(2000, 1, 1, 12, 0, 0))


class TestSunLongitude:
    def test_summer_solstice_approx_90(self) -> None:
        jd = julian_day(datetime(2000, 6, 21, 1, 48, tzinfo=UTC))
        lon = sun_longitude(jd)
        assert abs(lon - 90.0) < _TOLERANCE_DEG

    def test_autumnal_equinox_approx_180(self) -> None:
        jd = julian_day(datetime(2000, 9, 22, 17, 27, tzinfo=UTC))
        lon = sun_longitude(jd)
        assert abs(lon - 180.0) < _TOLERANCE_DEG

    def test_winter_solstice_approx_270(self) -> None:
        jd = julian_day(datetime(2000, 12, 21, 13, 37, tzinfo=UTC))
        lon = sun_longitude(jd)
        assert abs(lon - 270.0) < _TOLERANCE_DEG

    def test_vernal_equinox_approx_0(self) -> None:
        jd = julian_day(datetime(2001, 3, 20, 13, 31, tzinfo=UTC))
        lon = sun_longitude(jd)
        # longitude wraps 0°/360° — accept either side of wrap
        assert min(lon, abs(lon - 360.0)) < _TOLERANCE_DEG

    def test_result_in_range(self) -> None:
        jd = julian_day(datetime(1990, 6, 15, 12, 0, tzinfo=UTC))
        lon = sun_longitude(jd)
        assert 0.0 <= lon < 360.0


class TestSetEphemerisPath:
    def test_existing_path_does_not_raise(self, tmp_path: Path) -> None:
        set_ephemeris_path(tmp_path)  # tmp_path exists → no warning, no error

    def test_missing_path_does_not_raise(self, tmp_path: Path) -> None:
        # Non-existent path triggers a warning but must not raise
        missing = tmp_path / "no_such_dir"
        set_ephemeris_path(missing)

    def test_accepts_string(self, tmp_path: Path) -> None:
        set_ephemeris_path(str(tmp_path))
