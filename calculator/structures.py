"""Bazi 格局 (Special Structures) detection — 25 structures in 5 categories.

Cascade priority (canonical, from doc/research/structures_v2_perplexity_deep.md):
  1. 化气格 (Transformation, 5)   — adjacent stems form 五合 + month supports
  2. 从格 (Following, 5)           — DM uprooted + dominant element
  3. 一气格 (Mono-element, 5)     — chart concentrated in DM's element
  4. 月令-special (建禄/月刃, 2)   — month branch is DM's Lu or Yang Blade
  5. 正格 (Regular, 8)            — main qi of month branch + 10 Gods

The cascade returns the first match found. If none match, returns empty list.

Skipped from v1 (defer to v3 — Determinism Low/Very Low requiring expert layer):
  - 拱禄格 (27), 飞天禄马倒冲 (28), 两神成象 (29), 子辰双美格 (30)
  - 魁罡格 (26) — already detected as a Symbolic Star (魁罡), no duplication.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import cast

from calculator.models import (
    DeterminismLevel,
    Pillar,
    Structure,
    StructureCategory,
    StructuresOutput,
)
from calculator.structures_tables import (
    BRANCH_ELEMENT,
    EARTH_FOUR_STORAGE,
    ELEMENT_CONTROLLED_BY,
    ELEMENT_CONTROLS,
    ELEMENT_GENERATED_BY,
    ELEMENT_GENERATES,
    HIDDEN_STEMS,
    LU_POSITION,
    META,
    MONO_DIRECTIONALS,
    MONO_TRIADS,
    MONOELEMENT_STRUCTURE,
    STEM_COMBINATIONS,
    STEM_ELEMENT,
    STEM_POLARITY,
    TRANSFORMATION_STRUCTURE,
    TRANSFORMATION_SUPPORT_MONTHS,
    YANG_BLADE_POSITION,
    StructureMeta,
)

# ── Internal helpers ──────────────────────────────────────────────────────────


def _make_structure(structure_id: str) -> Structure:
    meta: StructureMeta = META[structure_id]
    return Structure(
        name_zh=meta.name_zh,
        name_pinyin=meta.name_pinyin,
        name_ru=meta.name_ru,
        category=cast("StructureCategory", meta.category),
        useful_god=meta.useful_god,
        harmful_god=meta.harmful_god,
        determinism=cast("DeterminismLevel", meta.determinism),
        source=meta.source,
    )


def _ten_god(dm_stem: str, target_stem: str) -> str:
    """Map (DM, target stem) → 10-God category id (used to pick structure)."""
    dm_el = STEM_ELEMENT[dm_stem]
    tgt_el = STEM_ELEMENT[target_stem]
    same_polarity = STEM_POLARITY[dm_stem] == STEM_POLARITY[target_stem]

    if dm_el == tgt_el:
        return "bi_jian" if same_polarity else "jie_cai"
    if ELEMENT_CONTROLS[dm_el] == tgt_el:
        return "pian_cai" if same_polarity else "zheng_cai"
    if ELEMENT_CONTROLS[tgt_el] == dm_el:
        return "qi_sha" if same_polarity else "zheng_guan"
    if ELEMENT_GENERATES[dm_el] == tgt_el:
        return "shi_shen" if same_polarity else "shang_guan"
    if ELEMENT_GENERATES[tgt_el] == dm_el:
        return "pian_yin" if same_polarity else "zheng_yin"
    raise ValueError(f"unreachable: ({dm_stem}, {target_stem})")


def _has_root(dm_stem: str, branches: Sequence[str]) -> bool:
    """True if DM-element appears in any branch's hidden stems."""
    dm_el = STEM_ELEMENT[dm_stem]
    return any(
        STEM_ELEMENT[hidden] == dm_el for branch in branches for hidden in HIDDEN_STEMS[branch]
    )


def _has_resource(dm_stem: str, stems: Sequence[str], branches: Sequence[str]) -> bool:
    """True if Resource (印 — element that generates DM) appears anywhere."""
    dm_el = STEM_ELEMENT[dm_stem]
    resource_el = ELEMENT_GENERATED_BY[dm_el]
    if any(STEM_ELEMENT[s] == resource_el for s in stems):
        return True
    return any(
        STEM_ELEMENT[hidden] == resource_el
        for branch in branches
        for hidden in HIDDEN_STEMS[branch]
    )


def _branch_element_counts(branches: Sequence[str]) -> dict[str, int]:
    counts = {"木": 0, "火": 0, "土": 0, "金": 0, "水": 0}
    for b in branches:
        counts[BRANCH_ELEMENT[b]] += 1
    return counts


# ── Detectors (in cascade priority order) ─────────────────────────────────────


def _detect_transformation(pillars: list[Pillar]) -> Structure | None:
    """化气格: DM combines with adjacent stem and month supports the new element."""
    dm = pillars[2].stem
    month_stem = pillars[1].stem
    hour_stem = pillars[3].stem
    month_branch = pillars[1].branch

    for partner in (month_stem, hour_stem):
        if partner == dm:
            continue
        pair = frozenset({dm, partner})
        if pair not in STEM_COMBINATIONS:
            continue
        transformed_el = STEM_COMBINATIONS[pair]
        if month_branch in TRANSFORMATION_SUPPORT_MONTHS[transformed_el]:
            return _make_structure(TRANSFORMATION_STRUCTURE[transformed_el])
    return None


def _detect_following(pillars: list[Pillar]) -> Structure | None:
    """从格: DM has no root + no resource + dominant non-DM element."""
    dm = pillars[2].stem
    stems_other = [p.stem for i, p in enumerate(pillars) if i != 2]
    branches = [p.branch for p in pillars]

    if _has_root(dm, branches):
        return None
    if _has_resource(dm, stems_other, branches):
        return None

    # Determine dominant element (by branches)
    counts = _branch_element_counts(branches)
    counts.pop(STEM_ELEMENT[dm], None)  # exclude DM's own (= 0 anyway when no root)
    if not counts:
        return None
    dominant = max(counts, key=lambda k: counts[k])
    if counts[dominant] < 2:
        return None  # No clear domination → ambiguous

    # Map dominant element back to 10-God category from DM's perspective
    dm_el = STEM_ELEMENT[dm]
    if ELEMENT_CONTROLS[dm_el] == dominant:
        return _make_structure("cong_cai")  # DM controls = Wealth
    if ELEMENT_CONTROLLED_BY[dm_el] == dominant:
        return _make_structure("cong_guan_sha")  # Controls DM = Officer/Killings
    if ELEMENT_GENERATES[dm_el] == dominant:
        return _make_structure("cong_er")  # DM generates = Output
    return _make_structure("cong_shi")  # mixed/momentum fallback


def _detect_monoelement(pillars: list[Pillar]) -> Structure | None:
    """一气格: chart concentrated in DM's own element (triad or directional)."""
    dm = pillars[2].stem
    dm_el = STEM_ELEMENT[dm]
    branches = [p.branch for p in pillars]
    branch_set = set(branches)

    # 稼穑 (Earth) requires all 4 storage branches — strict
    if dm_el == "土":
        if EARTH_FOUR_STORAGE.issubset(branch_set):
            return _make_structure(MONOELEMENT_STRUCTURE[dm_el])
        return None

    # Other 4 mono-elements: triad (三合) OR directional (方局), with no controller dominance
    triad = MONO_TRIADS.get(dm_el)
    directional = MONO_DIRECTIONALS.get(dm_el)
    has_triad = triad is not None and triad.issubset(branch_set)
    has_directional = directional is not None and directional.issubset(branch_set)
    if not (has_triad or has_directional):
        return None

    # Reject if controller (e.g., Metal for Wood) is too prominent
    counts = _branch_element_counts(branches)
    controller = ELEMENT_CONTROLLED_BY[dm_el]
    if counts[controller] >= 2:
        return None

    return _make_structure(MONOELEMENT_STRUCTURE[dm_el])


def _detect_month_special(pillars: list[Pillar]) -> Structure | None:
    """建禄格 (month_branch == DM's Lu) or 月刃格 (== Yang Blade, Yang DM only)."""
    dm = pillars[2].stem
    month_branch = pillars[1].branch
    if STEM_POLARITY[dm] == "yang" and YANG_BLADE_POSITION.get(dm) == month_branch:
        return _make_structure("yue_ren")
    if LU_POSITION[dm] == month_branch:
        return _make_structure("jian_lu")
    return None


_REGULAR_STRUCTURE_BY_GOD: dict[str, str] = {
    "zheng_guan": "zheng_guan",
    "qi_sha": "qi_sha",
    "zheng_cai": "zheng_cai",
    "pian_cai": "pian_cai",
    "zheng_yin": "zheng_yin",
    "pian_yin": "pian_yin",
    "shi_shen": "shi_shen",
    "shang_guan": "shang_guan",
    # 比肩/劫财 — handled by 月令-special, not by regular structures
}


def _detect_regular(pillars: list[Pillar]) -> Structure | None:
    """8 正格: main qi of 月支 → 10-Gods relation to DM → structure name.

    Priority within hidden stems: 主气 → 中气 → 余气. First god mapping not in
    {比肩, 劫财} wins. (When main qi == DM, the chart is already classified as
    建禄/月刃 in the cascade above.)
    """
    dm = pillars[2].stem
    month_branch = pillars[1].branch
    for hidden_stem in HIDDEN_STEMS[month_branch]:
        god = _ten_god(dm, hidden_stem)
        structure_id = _REGULAR_STRUCTURE_BY_GOD.get(god)
        if structure_id is not None:
            return _make_structure(structure_id)
    return None


# ── Public API ────────────────────────────────────────────────────────────────


def calculate_structures(pillars: list[Pillar]) -> StructuresOutput:
    """Detect the primary 格局 of a chart via cascade priority."""
    if len(pillars) != 4:
        raise ValueError(f"expected 4 pillars (year/month/day/hour), got {len(pillars)}")

    by_name = {p.name: p for p in pillars}
    if set(by_name) != {"year", "month", "day", "hour"}:
        raise ValueError(f"pillar names must be year/month/day/hour, got {set(by_name)}")

    ordered = [by_name["year"], by_name["month"], by_name["day"], by_name["hour"]]

    for detector in (
        _detect_transformation,
        _detect_following,
        _detect_monoelement,
        _detect_month_special,
        _detect_regular,
    ):
        result = detector(ordered)
        if result is not None:
            return StructuresOutput(structures=[result])

    return StructuresOutput(structures=[])
