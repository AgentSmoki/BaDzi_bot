"""24 Solar Terms (Jie Qi, 节气) calculation via Newton-Raphson search."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from calculator.swiss import sun_longitude

# ── Constants ─────────────────────────────────────────────────────────────────

_MEAN_TROPICAL_YEAR: float = 365.24219  # days
_SUN_MEAN_SPEED: float = 360.0 / _MEAN_TROPICAL_YEAR  # ~0.9856 deg/day

# JD of vernal equinox 2000-03-20 07:35 UTC (λ = 0°)
_VE_2000_JD: float = 2451623.815

# Reference for JD → datetime conversion
_J2000_EPOCH: datetime = datetime(2000, 1, 1, 12, 0, 0, tzinfo=UTC)
_J2000_JD: float = 2451545.0

# 24 solar terms in order of ecliptic longitude (index i → λ = i * 15°)
SOLAR_TERM_NAMES: tuple[str, ...] = (
    "春分",
    "清明",
    "谷雨",
    "立夏",
    "小满",
    "芒种",
    "夏至",
    "小暑",
    "大暑",
    "立秋",
    "处暑",
    "白露",
    "秋分",
    "寒露",
    "霜降",
    "立冬",
    "小雪",
    "大雪",
    "冬至",
    "小寒",
    "大寒",
    "立春",
    "雨水",
    "惊蛰",
)

# Indices of 12 "Jie" (节) that open each Ba Zi month (branch order 寅..丑)
MONTH_JIE_INDICES: tuple[int, ...] = (21, 23, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19)


# ── Internal helpers ──────────────────────────────────────────────────────────


def _approx_jd(year: int, term_index: int) -> float:
    """Rough JD for term `term_index` in Gregorian year `year`."""
    ve_jd = _VE_2000_JD + (year - 2000) * _MEAN_TROPICAL_YEAR
    lon = term_index * 15.0
    days_from_ve = lon / _SUN_MEAN_SPEED
    # Terms with λ > 270° (小寒..惊蛰) fall before the vernal equinox
    if lon > 270.0:
        days_from_ve -= _MEAN_TROPICAL_YEAR
    return ve_jd + days_from_ve


def _find_solar_term_jd(target_lon: float, approx_jd: float) -> float:
    """Newton-Raphson refinement until sun longitude equals target_lon."""
    jd = approx_jd
    for _ in range(50):
        current = sun_longitude(jd)
        diff = (target_lon - current + 180.0) % 360.0 - 180.0
        step = diff / _SUN_MEAN_SPEED
        jd += step
        if abs(step) < 1e-7:  # ~8.6 ms precision
            break
    return jd


def _jd_to_utc(jd: float) -> datetime:
    return _J2000_EPOCH + timedelta(days=jd - _J2000_JD)


# ── Public API ────────────────────────────────────────────────────────────────


def solar_term_jd(year: int, term_index: int) -> float:
    """JD when sun longitude equals term_index * 15° in Gregorian year `year`.

    Args:
        year:       Gregorian year.
        term_index: 0 (春分, λ=0°) … 23 (惊蛰, λ=345°).
    """
    if not 0 <= term_index < 24:
        raise ValueError(f"term_index must be 0..23, got {term_index}")
    approx = _approx_jd(year, term_index)
    return _find_solar_term_jd(term_index * 15.0, approx)


def solar_term_datetime(year: int, term_index: int) -> datetime:
    """UTC datetime of solar term `term_index` in Gregorian year `year`."""
    jd = solar_term_jd(year, term_index)
    return _jd_to_utc(jd)
