"""True Solar Time (TST) calculation.

TST = LMT + EoT
  LMT  — Local Mean Time: UTC shifted by longitude/15 hours
  EoT  — Equation of Time: pyswisseph (Jean Meeus precision)
"""

from __future__ import annotations

from datetime import datetime, timedelta

import swisseph as swe

from calculator.swiss import julian_day

_MINUTES_PER_DAY: float = 24.0 * 60.0


def equation_of_time(jd: float) -> float:
    """Return Equation of Time in minutes (Apparent Solar Time - Local Mean Time)."""
    eot_days: float = swe.time_equ(jd)
    return float(eot_days) * _MINUTES_PER_DAY


def true_solar_time(utc_dt: datetime, *, longitude: float) -> datetime:
    """Convert UTC datetime to True Solar Time (naive) at the given longitude.

    Args:
        utc_dt:    UTC-aware datetime of the birth moment.
        longitude: Geographic longitude in degrees (East positive).

    Returns:
        Naive datetime representing True Solar Time.
    """
    if utc_dt.tzinfo is None:
        raise ValueError("utc_dt must be UTC-aware (tzinfo must not be None)")

    lmt_offset = timedelta(hours=longitude / 15.0)
    lmt = utc_dt.replace(tzinfo=None) + lmt_offset

    jd = julian_day(utc_dt)
    eot_min = equation_of_time(jd)

    return lmt + timedelta(minutes=eot_min)
