"""Swiss Ephemeris wrapper — thin facade over pyswisseph."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import swisseph as swe

_log = logging.getLogger(__name__)

_FLG = swe.FLG_SWIEPH | swe.FLG_SPEED


def set_ephemeris_path(path: str | Path) -> None:
    """Point pyswisseph at JPL DE431 files.  Falls back to Moshier if path missing."""
    p = Path(path)
    if not p.exists():
        _log.warning("ephemeris path %s not found — using Moshier fallback", p)
    swe.set_ephe_path(str(p))


def julian_day(dt: datetime) -> float:
    """Convert a UTC-aware datetime to Julian Day Number (UT1)."""
    if dt.tzinfo is None:
        raise ValueError("datetime must be UTC-aware (tzinfo must not be None)")
    hour = dt.hour + dt.minute / 60.0 + dt.second / 3600.0 + dt.microsecond / 3_600_000_000.0
    return float(swe.julday(dt.year, dt.month, dt.day, hour, swe.GREG_CAL))


def sun_longitude(jd: float) -> float:
    """Return ecliptic longitude of the Sun in degrees [0, 360)."""
    result, _ = swe.calc_ut(jd, swe.SUN, _FLG)
    lon: float = result[0] % 360.0
    return lon
