"""Auxiliary pillars 胎元 (Tai Yuan, Conception Pillar) and 命宫 (Ming Gong, Life Palace).

胎元 — symbolic conception pillar = month_pillar shifted by (+1 stem, +3 branches).
  Encodes the prenatal month according to the canonical 10-month gestation rule.

命宫 — Life Palace, anchor for personality and major life themes.
  Formula (中州派 canon): the 寅-system position where (month + hour) reflects to 14.
    mg_yin_idx = (14 - month_yin_idx - hour_zi_idx) mod 12
  Stem follows 五虎遁 starting from the year stem (same rule as month stems).

Both formulas verified against the canonical Mingli reference for chart
1999 / 己卯 / 癸酉 / 丁亥 / 庚子 → 胎元 = 甲子, 命宫 = 癸酉.
"""

from __future__ import annotations

from typing import cast

from calculator.models import (
    BRANCHES,
    STEMS,
    AuxiliaryPillars,
    Branch,
    Pillar,
    Stem,
)

# ── Constants ─────────────────────────────────────────────────────────────────

# Convert "standard" branch index (子=0) to/from "yin-base" index (寅=0).
# yin = (std - 寅_idx) mod 12 = (std - 2) mod 12
_YIN_OFFSET: int = 2
_TAI_YUAN_STEM_SHIFT: int = 1
_TAI_YUAN_BRANCH_SHIFT: int = 3
_MING_GONG_REFLECTION: int = 14


# ── Internal helpers ──────────────────────────────────────────────────────────


def _starting_yin_stem(year_stem_idx: int) -> int:
    """Stem of 寅 month for the given year stem (五虎遁年起月)."""
    return ((year_stem_idx % 5) * 2 + 2) % 10


def _std_to_yin(branch_idx: int) -> int:
    return (branch_idx - _YIN_OFFSET) % 12


def _yin_to_std(yin_idx: int) -> int:
    return (yin_idx + _YIN_OFFSET) % 12


# ── Public API ────────────────────────────────────────────────────────────────


def calculate_tai_yuan(month_pillar: Pillar) -> Pillar:
    """Conception pillar (胎元) = month + (1 stem, 3 branches)."""
    month_stem_idx = STEMS.index(month_pillar.stem)
    month_branch_idx = BRANCHES.index(month_pillar.branch)
    return Pillar(
        stem=cast("Stem", STEMS[(month_stem_idx + _TAI_YUAN_STEM_SHIFT) % 10]),
        branch=cast("Branch", BRANCHES[(month_branch_idx + _TAI_YUAN_BRANCH_SHIFT) % 12]),
        name="tai_yuan",
    )


def calculate_ming_gong(year_pillar: Pillar, month_pillar: Pillar, hour_pillar: Pillar) -> Pillar:
    """Life Palace (命宫) by 中州派 reflection rule."""
    month_yin = _std_to_yin(BRANCHES.index(month_pillar.branch))
    hour_zi = BRANCHES.index(hour_pillar.branch)  # 子=0
    mg_yin = (_MING_GONG_REFLECTION - month_yin - hour_zi) % 12
    mg_branch_idx = _yin_to_std(mg_yin)

    year_stem_idx = STEMS.index(year_pillar.stem)
    mg_stem_idx = (_starting_yin_stem(year_stem_idx) + mg_yin) % 10

    return Pillar(
        stem=cast("Stem", STEMS[mg_stem_idx]),
        branch=cast("Branch", BRANCHES[mg_branch_idx]),
        name="ming_gong",
    )


def calculate_auxiliary_pillars(pillars: list[Pillar]) -> AuxiliaryPillars:
    """Compute 胎元 and 命宫 from the four main pillars."""
    if len(pillars) != 4:
        raise ValueError(f"expected 4 pillars (year/month/day/hour), got {len(pillars)}")

    by_name = {p.name: p for p in pillars}
    if set(by_name) != {"year", "month", "day", "hour"}:
        raise ValueError(f"pillar names must be year/month/day/hour, got {set(by_name)}")

    return AuxiliaryPillars(
        tai_yuan=calculate_tai_yuan(by_name["month"]),
        ming_gong=calculate_ming_gong(by_name["year"], by_name["month"], by_name["hour"]),
    )
