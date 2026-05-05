"""Symbolic Stars (神煞) detection for a Ba Zi chart.

Detects 60 classical stars via 7 detector families. See symbolic_stars_tables.py
for the data; this module is purely glue.

Skipped from v1 (deferred to v2 / separate tasks):
  - 元辰, 勾绞 — dynamic year-polarity formulas
  - 空亡 — Xun-based (separate task 2.1.5)
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from calculator.models import (
    Pillar,
    SymbolicStar,
    SymbolicStarCategory,
    SymbolicStarNature,
    SymbolicStarsOutput,
)
from calculator.symbolic_stars_tables import (
    DAY_BRANCH_TO_BRANCH,
    DAY_STEM_TO_BRANCH,
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

    return SymbolicStarsOutput(stars=stars)
