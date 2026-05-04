"""Four Pillars (四柱) generation for a Ba Zi chart."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from typing import cast

from calculator.models import BRANCHES, STEMS, Branch, ChartInput, Pillar, Stem
from calculator.solar_terms import MONTH_JIE_INDICES, solar_term_jd
from calculator.swiss import julian_day
from calculator.true_solar_time import true_solar_time

# ── Reference constants ───────────────────────────────────────────────────────

# 甲子 year = 1984 (most recent before J2000)
_YEAR_REF: int = 1984

# 甲子 day = 1900-01-31 (verified reference)
_DAY_REF_ORDINAL: int = date(1900, 1, 31).toordinal()

# BRANCHES tuple starts at 子(0), MONTH branches start at 寅(2)
_MONTH_BRANCH_OFFSET: int = 2


# ── Stem/branch index helpers ─────────────────────────────────────────────────


def _starting_hour_stem(day_stem_idx: int) -> int:
    """Stem index of 子时 based on day stem (甲己→甲, 乙庚→丙, ...)."""
    return (day_stem_idx % 5) * 2


def _month_starting_stem(year_stem_idx: int) -> int:
    """Stem index of 寅月 based on year stem (甲己→丙, 乙庚→戊, ...)."""
    return ((year_stem_idx % 5) * 2 + 2) % 10


# ── Year pillar ───────────────────────────────────────────────────────────────


def _year_stem_branch(birth_jd: float, gregorian_year: int) -> tuple[int, int]:
    liqian_jd = solar_term_jd(gregorian_year, 21)  # 立春 index 21
    bazi_year = gregorian_year if birth_jd >= liqian_jd else gregorian_year - 1
    idx = (bazi_year - _YEAR_REF) % 60
    return idx % 10, idx % 12


# ── Month pillar ──────────────────────────────────────────────────────────────


def _month_branch_from_yin(birth_jd: float, gregorian_year: int) -> int:
    """Month branch index (0=寅..11=丑) for the birth Julian day."""
    best_branch = 0
    best_jd = float("-inf")
    for y in (gregorian_year - 1, gregorian_year, gregorian_year + 1):
        for branch_idx, term_idx in enumerate(MONTH_JIE_INDICES):
            jd = solar_term_jd(y, term_idx)
            if jd <= birth_jd and jd > best_jd:
                best_jd = jd
                best_branch = branch_idx
    return best_branch


# ── Day pillar ────────────────────────────────────────────────────────────────


def _day_stem_branch(tst: datetime, early_rat: bool) -> tuple[int, int]:
    tst_date = tst.date()
    # Late Rat (default): 23:00 TST belongs to the NEXT calendar day
    if not early_rat and tst.hour >= 23:
        tst_date = tst_date + timedelta(days=1)
    idx = (tst_date.toordinal() - _DAY_REF_ORDINAL) % 60
    return idx % 10, idx % 12


# ── Hour pillar ───────────────────────────────────────────────────────────────


def _hour_branch_idx(tst: datetime) -> int:
    """Hour branch index (0=子..11=亥) from TST hour."""
    return ((tst.hour + 1) // 2) % 12


# ── Public API ────────────────────────────────────────────────────────────────


def calculate_pillars(inp: ChartInput) -> list[Pillar]:
    """Compute the Four Pillars for the given ChartInput.

    birth_datetime is treated as local civil time; tz_offset converts it to UTC.
    """
    # Local civil time → UTC
    if inp.birth_datetime.tzinfo is not None:
        utc_dt = inp.birth_datetime.astimezone(UTC).replace(tzinfo=UTC)
    else:
        utc_dt = (inp.birth_datetime - timedelta(hours=inp.tz_offset)).replace(tzinfo=UTC)

    tst = true_solar_time(utc_dt, longitude=inp.longitude)
    birth_jd = julian_day(utc_dt)
    gregorian_year = utc_dt.year

    # Year
    y_stem, y_branch = _year_stem_branch(birth_jd, gregorian_year)

    # Month
    m_branch_yin = _month_branch_from_yin(birth_jd, gregorian_year)
    m_stem = (_month_starting_stem(y_stem) + m_branch_yin) % 10
    m_branch = (m_branch_yin + _MONTH_BRANCH_OFFSET) % 12

    # Day
    d_stem, d_branch = _day_stem_branch(tst, inp.early_rat)

    # Hour
    h_branch = _hour_branch_idx(tst)
    h_stem = (_starting_hour_stem(d_stem) + h_branch) % 10

    def _s(i: int) -> Stem:
        return cast("Stem", STEMS[i])

    def _b(i: int) -> Branch:
        return cast("Branch", BRANCHES[i])

    return [
        Pillar(stem=_s(y_stem), branch=_b(y_branch), name="year"),
        Pillar(stem=_s(m_stem), branch=_b(m_branch), name="month"),
        Pillar(stem=_s(d_stem), branch=_b(d_branch), name="day"),
        Pillar(stem=_s(h_stem), branch=_b(h_branch), name="hour"),
    ]
