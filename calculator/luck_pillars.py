"""Luck Pillars (大運) generation for a Ba Zi chart.

Direction rule:
  Yang year + male   = forward (顺运)  Yang year + female = backward (逆运)
  Yin year  + male   = backward (逆运)  Yin year  + female = forward (顺运)

3:1 conversion (3 solar days = 1 year of life).
  Symbolic decomposition of starting age uses a 360-day year
  (12 x 30-day months → 1 day = 4 months, 1 hour = 5 days, 1 minute = 2 hours).
  Absolute pillar boundaries use the real Gregorian year (365.2425 days)
  so each Da Yun spans exactly 10 calendar years.
"""

from __future__ import annotations

from datetime import UTC, timedelta
from typing import cast

from calculator.models import (
    BRANCHES,
    STEMS,
    Branch,
    ChartInput,
    Gender,
    LuckPillar,
    LuckPillarsOutput,
    Stem,
)
from calculator.pillars import calculate_pillars
from calculator.solar_terms import MONTH_JIE_INDICES, solar_term_jd
from calculator.swiss import julian_day

# ── Constants ─────────────────────────────────────────────────────────────────

_DAYS_PER_LUCK_YEAR: float = 3.0  # 3 solar days = 1 year of big luck
_LUCK_COUNT: int = 8
_LUCK_YEARS_PER_PILLAR: int = 10

# Symbolic units for Y/M/D/H/Min decomposition (360-day year, 30-day month).
_SYM_MIN_PER_HOUR: int = 60
_SYM_MIN_PER_DAY: int = 24 * _SYM_MIN_PER_HOUR
_SYM_MIN_PER_MONTH: int = 30 * _SYM_MIN_PER_DAY
_SYM_MIN_PER_YEAR: int = 12 * _SYM_MIN_PER_MONTH

# Real Gregorian year (seconds) for absolute pillar-boundary datetimes.
_REAL_YEAR_SECONDS: float = 365.2425 * 86400.0
_PILLAR_DURATION_SECONDS: float = _LUCK_YEARS_PER_PILLAR * _REAL_YEAR_SECONDS


# ── Internal helpers ──────────────────────────────────────────────────────────


def _pillar_60_idx(stem_idx: int, branch_idx: int) -> int:
    """Find unique 60-cycle index for (stem_idx, branch_idx)."""
    for x in range(60):
        if x % 10 == stem_idx and x % 12 == branch_idx:
            return x
    raise ValueError(f"Invalid stem/branch indices: {stem_idx}, {branch_idx}")


def _is_forward(year_stem_idx: int, gender: Gender) -> bool:
    """True = forward (顺运), False = backward (逆运)."""
    is_yang = year_stem_idx % 2 == 0
    return (is_yang and gender == "male") or (not is_yang and gender == "female")


def _nearest_jie_jd(birth_jd: float, forward: bool, gregorian_year: int) -> float:
    """Return JD of next (forward) or previous (backward) Jie term."""
    best: float | None = None
    for y in range(gregorian_year - 1, gregorian_year + 2):
        for term_idx in MONTH_JIE_INDICES:
            jd = solar_term_jd(y, term_idx)
            if forward:
                if jd > birth_jd and (best is None or jd < best):
                    best = jd
            else:
                if jd < birth_jd and (best is None or jd > best):
                    best = jd
    if best is None:
        raise ValueError("No Jie term found near birth date")
    return best


def _decompose_age(days_to_jie: float) -> tuple[int, int, int, int, int]:
    """Return (years, months, days, hours, minutes) for a span of solar days.

    Uses the classical 360-day-year convention so days ∈ [0, 29], minutes ∈ [0, 59].
    """
    total_minutes = int(days_to_jie / _DAYS_PER_LUCK_YEAR * _SYM_MIN_PER_YEAR)
    years, rem = divmod(total_minutes, _SYM_MIN_PER_YEAR)
    months, rem = divmod(rem, _SYM_MIN_PER_MONTH)
    days, rem = divmod(rem, _SYM_MIN_PER_DAY)
    hours, minutes = divmod(rem, _SYM_MIN_PER_HOUR)
    return years, months, days, hours, minutes


# ── Public API ────────────────────────────────────────────────────────────────


def calculate_luck_pillars(inp: ChartInput) -> LuckPillarsOutput | None:
    """Return 8 Luck Pillars (大運) with minute-level precision, or None if no gender."""
    if inp.gender is None:
        return None

    gender: Gender = inp.gender

    four = calculate_pillars(inp)
    year_stem_idx = STEMS.index(four[0].stem)
    month_stem_idx = STEMS.index(four[1].stem)
    month_branch_idx = BRANCHES.index(four[1].branch)

    if inp.birth_datetime.tzinfo is not None:
        utc_dt = inp.birth_datetime.astimezone(UTC).replace(tzinfo=UTC)
    else:
        utc_dt = (inp.birth_datetime - timedelta(hours=inp.tz_offset)).replace(tzinfo=UTC)
    birth_jd = julian_day(utc_dt)

    forward = _is_forward(year_stem_idx, gender)
    jie_jd = _nearest_jie_jd(birth_jd, forward, utc_dt.year)
    days = abs(jie_jd - birth_jd)

    start_y, start_m, start_d, start_h, start_min = _decompose_age(days)
    offset_seconds = days / _DAYS_PER_LUCK_YEAR * _REAL_YEAR_SECONDS
    first_start = utc_dt + timedelta(seconds=offset_seconds)

    month_60 = _pillar_60_idx(month_stem_idx, month_branch_idx)

    luck_pillars: list[LuckPillar] = []
    for i in range(_LUCK_COUNT):
        step = i + 1 if forward else -(i + 1)
        idx = (month_60 + step) % 60
        pillar_start = first_start + timedelta(seconds=i * _PILLAR_DURATION_SECONDS)
        pillar_end = pillar_start + timedelta(seconds=_PILLAR_DURATION_SECONDS)
        luck_pillars.append(
            LuckPillar(
                stem=cast("Stem", STEMS[idx % 10]),
                branch=cast("Branch", BRANCHES[idx % 12]),
                name=f"luck_{i + 1}",
                start_age=start_y + i * _LUCK_YEARS_PER_PILLAR,
                start_datetime=pillar_start,
                end_datetime=pillar_end,
            )
        )

    return LuckPillarsOutput(
        gender=gender,
        direction="forward" if forward else "backward",
        start_age_years=start_y,
        start_age_months=start_m,
        start_age_days=start_d,
        start_age_hours=start_h,
        start_age_minutes=start_min,
        pillars=luck_pillars,
    )
