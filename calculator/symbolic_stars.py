"""Symbolic Stars (神煞) detection for a Ba Zi chart.

Detects 63 classical stars via 7 detector families + 3 dynamic special handlers
(空亡 Xun-based, 元辰 / 勾绞 year-polarity formulas).
See symbolic_stars_tables.py for the static data.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from calculator.models import (
    BRANCHES,
    STEMS,
    Pillar,
    SymbolicStar,
    SymbolicStarCategory,
    SymbolicStarNature,
    SymbolicStarsOutput,
)
from calculator.symbolic_stars_tables import (
    DAY_BRANCH_TO_BRANCH,
    DAY_STEM_TO_BRANCH,
    KONGWANG_BY_XUN,
    META,
    MONTH_BRANCH_TO_BRANCH,
    MONTH_BRANCH_TO_STEM,
    SEASON_OF_MONTH,
    SELF_PILLAR_STARS,
    TIANDE_BRANCH_FORM_MONTHS,
    TIANLUODIWANG_PAIRS,
    TIANSHE_BY_SEASON,
    YEAR_BRANCH_TO_BRANCH,
    YEAR_BRANCH_TO_BRANCH_TRIAD,
    StarMeta,
)

_PILLAR_ORDER: dict[str, int] = {"year": 0, "month": 1, "day": 2, "hour": 3}


# ── Internal helpers ──────────────────────────────────────────────────────────


def _sort_pillars(pillars: list[str]) -> list[str]:
    return sorted(set(pillars), key=lambda p: _PILLAR_ORDER.get(p, 99))


def _make_star(star_id: str, pillars: list[str]) -> SymbolicStar:
    meta: StarMeta = META[star_id]
    return SymbolicStar(
        name_zh=meta.name_zh,
        name_pinyin=meta.name_pinyin,
        name_ru=meta.name_ru,
        category=cast("SymbolicStarCategory", meta.category),
        nature=cast("SymbolicStarNature", meta.nature),
        source=meta.source,
        pillars=_sort_pillars(pillars),
    )


def _sixty_cycle_index(stem_idx: int, branch_idx: int) -> int:
    """Find unique 60-cycle index x with x%10=stem_idx and x%12=branch_idx."""
    for x in range(60):
        if x % 10 == stem_idx and x % 12 == branch_idx:
            return x
    raise ValueError(f"invalid stem/branch combination: ({stem_idx}, {branch_idx})")


def _detect_anchor_lookup(
    star_ids: Mapping[str, dict[str, tuple[str, ...]]],
    anchor_value: str,
    chart_targets: list[tuple[str, str]],
) -> list[SymbolicStar]:
    """Generic detector: for each star, look up anchor_value in its table,
    then collect pillars in chart whose target char matches.
    """
    found: list[SymbolicStar] = []
    for star_id, table in star_ids.items():
        targets = table.get(anchor_value)
        if not targets:
            continue
        target_set = set(targets)
        pillars = [p for ch, p in chart_targets if ch in target_set]
        if pillars:
            found.append(_make_star(star_id, pillars))
    return found


# ── Public API ────────────────────────────────────────────────────────────────


def calculate_symbolic_stars(pillars: list[Pillar]) -> SymbolicStarsOutput:
    """Detect all classical 神煞 (Symbolic Stars) in the four pillars."""
    if len(pillars) != 4:
        raise ValueError(f"expected 4 pillars (year/month/day/hour), got {len(pillars)}")

    by_name = {p.name: p for p in pillars}
    if set(by_name) != {"year", "month", "day", "hour"}:
        raise ValueError(f"pillar names must be year/month/day/hour, got {set(by_name)}")

    year_pillar = by_name["year"]
    month_pillar = by_name["month"]
    day_pillar = by_name["day"]

    stems_in_chart: list[tuple[str, str]] = [(p.stem, p.name) for p in pillars]
    branches_in_chart: list[tuple[str, str]] = [(p.branch, p.name) for p in pillars]

    stars: list[SymbolicStar] = []

    # A. Anchored on day stem → look in branches
    stars.extend(_detect_anchor_lookup(DAY_STEM_TO_BRANCH, day_pillar.stem, branches_in_chart))

    # B. Anchored on day branch (triad-based) → look in branches
    stars.extend(_detect_anchor_lookup(DAY_BRANCH_TO_BRANCH, day_pillar.branch, branches_in_chart))

    # B'. Anchored on year branch (triad) — 岁驿
    stars.extend(
        _detect_anchor_lookup(YEAR_BRANCH_TO_BRANCH_TRIAD, year_pillar.branch, branches_in_chart)
    )

    # C. Anchored on month branch → look in branches
    stars.extend(
        _detect_anchor_lookup(MONTH_BRANCH_TO_BRANCH, month_pillar.branch, branches_in_chart)
    )

    # D. Anchored on month branch → look in stems (天德, 月德, 天德合, 月德合)
    # Caveat: 天德 of months 卯/午/酉/子 produces a BRANCH target, not a stem.
    for star_id, table in MONTH_BRANCH_TO_STEM.items():
        targets = table.get(month_pillar.branch)
        if not targets:
            continue
        target_set = set(targets)
        # Look in both stems and branches for 天德 special months.
        if star_id == "tiande" and month_pillar.branch in TIANDE_BRANCH_FORM_MONTHS:
            hits = [p for ch, p in branches_in_chart if ch in target_set]
        else:
            hits = [p for ch, p in stems_in_chart if ch in target_set]
        if hits:
            stars.append(_make_star(star_id, hits))

    # E. Anchored on year branch → look in branches
    stars.extend(
        _detect_anchor_lookup(YEAR_BRANCH_TO_BRANCH, year_pillar.branch, branches_in_chart)
    )

    # F. Self-pillar stars: day-pillar string matches a constant set
    day_pillar_str = f"{day_pillar.stem}{day_pillar.branch}"
    for star_id, members in SELF_PILLAR_STARS.items():
        if day_pillar_str in members:
            stars.append(_make_star(star_id, ["day"]))

    # G. Special: 天罗地网 — pair must coexist
    chart_branch_set = {ch for ch, _ in branches_in_chart}
    for pair in TIANLUODIWANG_PAIRS:
        if pair.issubset(chart_branch_set):
            pillars_in = [p for ch, p in branches_in_chart if ch in pair]
            stars.append(_make_star("tianluodiwang", pillars_in))
            break  # one pair is enough; report once

    # G'. Special: 天赦 — day-pillar matches season-of-month code
    season = SEASON_OF_MONTH.get(month_pillar.branch)
    if season is not None and day_pillar_str == TIANSHE_BY_SEASON[season]:
        stars.append(_make_star("tianshe", ["day"]))

    # H. Special: 空亡 — Xun (decade) of day pillar gives 2 void branches
    day_stem_idx = STEMS.index(day_pillar.stem)
    day_branch_idx = BRANCHES.index(day_pillar.branch)
    xun = _sixty_cycle_index(day_stem_idx, day_branch_idx) // 10
    void_branches = set(KONGWANG_BY_XUN[xun])
    void_pillars = [p for ch, p in branches_in_chart if ch in void_branches]
    if void_pillars:
        stars.append(_make_star("kongwang", void_pillars))

    # I. Special: 元辰 — Yang year → clash+1; Yin year → clash-1.
    #    Equivalent: Yang → year_branch + 7; Yin → year_branch + 5 (mod 12).
    year_stem_idx = STEMS.index(year_pillar.stem)
    year_branch_idx = BRANCHES.index(year_pillar.branch)
    yang_year = year_stem_idx % 2 == 0
    yc_offset = 7 if yang_year else 5
    yc_target = BRANCHES[(year_branch_idx + yc_offset) % 12]
    yc_pillars = [p for ch, p in branches_in_chart if ch == yc_target]
    if yc_pillars:
        stars.append(_make_star("yuanchen", yc_pillars))

    # J. Special: 勾绞 — symmetric ±3 from year_branch (Hook + Loop union).
    gj_targets = {
        BRANCHES[(year_branch_idx + 3) % 12],
        BRANCHES[(year_branch_idx - 3) % 12],
    }
    gj_pillars = [p for ch, p in branches_in_chart if ch in gj_targets]
    if gj_pillars:
        stars.append(_make_star("goujiao", gj_pillars))

    return SymbolicStarsOutput(stars=stars)
