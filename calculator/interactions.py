"""Branch and stem interactions (合沖刑害破) for a Ba Zi chart.

Five classical interaction families:
  - 五合 (5 stem combinations) → transforms to one of the 5 elements
  - 六沖 (6 branch clashes)
  - 六合 (6 branch six-harmonies) → transforms to an element
  - 三合 (4 branch triads, "three harmonies") → transforms to an element
  - 半合 (8 half-harmonies — pairs that include the central branch 子卯午酉)
  - 三刑 / 自刑 (3 mutual + 4 self-punishments)
  - 六害 (6 harms)
  - 六破 (6 breaks)

A triad (三合) suppresses its constituent half-harmony pairs to avoid noise.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from itertools import combinations

from calculator.models import (
    Interaction,
    InteractionsOutput,
    InteractionType,
    Pillar,
)

# ── Constants ─────────────────────────────────────────────────────────────────

# 五合 — stem combinations: frozenset of two stems → (name, element)
STEM_COMBINATIONS: dict[frozenset[str], tuple[str, str | None]] = {
    frozenset({"甲", "己"}): ("甲己合土", "土"),
    frozenset({"乙", "庚"}): ("乙庚合金", "金"),
    frozenset({"丙", "辛"}): ("丙辛合水", "水"),
    frozenset({"丁", "壬"}): ("丁壬合木", "木"),
    frozenset({"戊", "癸"}): ("戊癸合火", "火"),
}

# 六沖 — branch clashes (no transformation)
BRANCH_CLASHES: dict[frozenset[str], tuple[str, str | None]] = {
    frozenset({"子", "午"}): ("子午相沖", None),
    frozenset({"丑", "未"}): ("丑未相沖", None),
    frozenset({"寅", "申"}): ("寅申相沖", None),
    frozenset({"卯", "酉"}): ("卯酉相沖", None),
    frozenset({"辰", "戌"}): ("辰戌相沖", None),
    frozenset({"巳", "亥"}): ("巳亥相沖", None),
}

# 六合 — six branch harmonies (午未 conventionally → 火)
SIX_HARMONIES: dict[frozenset[str], tuple[str, str | None]] = {
    frozenset({"子", "丑"}): ("子丑合土", "土"),
    frozenset({"寅", "亥"}): ("寅亥合木", "木"),
    frozenset({"卯", "戌"}): ("卯戌合火", "火"),
    frozenset({"辰", "酉"}): ("辰酉合金", "金"),
    frozenset({"巳", "申"}): ("巳申合水", "水"),
    frozenset({"午", "未"}): ("午未合", "火"),
}

# 三合 — three branch triads (申子辰 etc.)
THREE_HARMONIES: dict[frozenset[str], tuple[str, str | None]] = {
    frozenset({"申", "子", "辰"}): ("申子辰三合水", "水"),
    frozenset({"亥", "卯", "未"}): ("亥卯未三合木", "木"),
    frozenset({"寅", "午", "戌"}): ("寅午戌三合火", "火"),
    frozenset({"巳", "酉", "丑"}): ("巳酉丑三合金", "金"),
}

# 半合 — half harmonies (must include the central branch of the triad)
HALF_HARMONIES: dict[frozenset[str], tuple[str, str | None]] = {
    frozenset({"申", "子"}): ("申子半合水", "水"),
    frozenset({"子", "辰"}): ("子辰半合水", "水"),
    frozenset({"亥", "卯"}): ("亥卯半合木", "木"),
    frozenset({"卯", "未"}): ("卯未半合木", "木"),
    frozenset({"寅", "午"}): ("寅午半合火", "火"),
    frozenset({"午", "戌"}): ("午戌半合火", "火"),
    frozenset({"巳", "酉"}): ("巳酉半合金", "金"),
    frozenset({"酉", "丑"}): ("酉丑半合金", "金"),
}

# 三刑 — mutual punishments (full triad required)
THREE_PUNISHMENTS: dict[frozenset[str], tuple[str, str | None]] = {
    frozenset({"寅", "巳", "申"}): ("寅巳申无恩之刑", None),
    frozenset({"丑", "戌", "未"}): ("丑戌未恃势之刑", None),
}
# 子卯 — pair-shaped punishment (无礼之刑); kept as pair table.
PAIR_PUNISHMENTS: dict[frozenset[str], tuple[str, str | None]] = {
    frozenset({"子", "卯"}): ("子卯无礼之刑", None),
}

# 自刑 — self-punishment branches (require ≥ 2 occurrences in chart)
SELF_PUNISHMENTS: dict[str, str] = {
    "辰": "辰辰自刑",
    "午": "午午自刑",
    "酉": "酉酉自刑",
    "亥": "亥亥自刑",
}

# 六害 — six harms
SIX_HARMS: dict[frozenset[str], tuple[str, str | None]] = {
    frozenset({"子", "未"}): ("子未相害", None),
    frozenset({"丑", "午"}): ("丑午相害", None),
    frozenset({"寅", "巳"}): ("寅巳相害", None),
    frozenset({"卯", "辰"}): ("卯辰相害", None),
    frozenset({"申", "亥"}): ("申亥相害", None),
    frozenset({"酉", "戌"}): ("酉戌相害", None),
}

# 六破 — six breaks
SIX_BREAKS: dict[frozenset[str], tuple[str, str | None]] = {
    frozenset({"子", "酉"}): ("子酉相破", None),
    frozenset({"卯", "午"}): ("卯午相破", None),
    frozenset({"寅", "亥"}): ("寅亥相破", None),
    frozenset({"巳", "申"}): ("巳申相破", None),
    frozenset({"辰", "丑"}): ("辰丑相破", None),
    frozenset({"戌", "未"}): ("戌未相破", None),
}

_PillarTagged = tuple[str, str]  # (character, pillar_name)
_PILLAR_ORDER: dict[str, int] = {"year": 0, "month": 1, "day": 2, "hour": 3}


# ── Internal helpers ──────────────────────────────────────────────────────────


def _sort_pillars(pillars: Iterable[str]) -> list[str]:
    return sorted(set(pillars), key=lambda p: _PILLAR_ORDER.get(p, 99))


def _detect_pairs(
    tagged: list[_PillarTagged],
    table: Mapping[frozenset[str], tuple[str, str | None]],
    type_: InteractionType,
    excluded_keys: set[frozenset[str]] | None = None,
) -> list[Interaction]:
    """Find all distinct pairs in `tagged` whose char-set is a key of `table`."""
    aggregated: dict[frozenset[str], tuple[str, str | None, set[str]]] = {}
    for (c1, p1), (c2, p2) in combinations(tagged, 2):
        if c1 == c2:
            continue
        key = frozenset({c1, c2})
        if excluded_keys and key in excluded_keys:
            continue
        if key not in table:
            continue
        name, transform = table[key]
        entry = aggregated.setdefault(key, (name, transform, set()))
        entry[2].update({p1, p2})
    return [
        Interaction(
            type=type_,
            name=n,
            members=sorted(k),
            transforms_to=t,
            pillars=_sort_pillars(ps),
        )
        for k, (n, t, ps) in aggregated.items()
    ]


def _detect_triads(
    tagged: list[_PillarTagged],
    table: Mapping[frozenset[str], tuple[str, str | None]],
    type_: InteractionType,
) -> list[Interaction]:
    """Find all distinct triads whose char-set is a key of `table`."""
    aggregated: dict[frozenset[str], tuple[str, str | None, set[str]]] = {}
    for combo in combinations(tagged, 3):
        chars = [c for c, _ in combo]
        if len(set(chars)) < 3:
            continue
        key = frozenset(chars)
        if key not in table:
            continue
        name, transform = table[key]
        entry = aggregated.setdefault(key, (name, transform, set()))
        entry[2].update(p for _, p in combo)
    return [
        Interaction(
            type=type_,
            name=n,
            members=sorted(k),
            transforms_to=t,
            pillars=_sort_pillars(ps),
        )
        for k, (n, t, ps) in aggregated.items()
    ]


def _detect_self_punishments(branches: list[_PillarTagged]) -> list[Interaction]:
    by_char: dict[str, list[str]] = {}
    for ch, pill in branches:
        if ch in SELF_PUNISHMENTS:
            by_char.setdefault(ch, []).append(pill)
    return [
        Interaction(
            type="self_punishment",
            name=SELF_PUNISHMENTS[ch],
            members=[ch, ch],
            transforms_to=None,
            pillars=_sort_pillars(ps),
        )
        for ch, ps in by_char.items()
        if len(ps) >= 2
    ]


# ── Public API ────────────────────────────────────────────────────────────────


def calculate_interactions(pillars: list[Pillar]) -> InteractionsOutput:
    """Detect all classical 合沖刑害破 interactions among the four pillars."""
    stems: list[_PillarTagged] = [(p.stem, p.name) for p in pillars]
    branches: list[_PillarTagged] = [(p.branch, p.name) for p in pillars]

    three_harmonies = _detect_triads(branches, THREE_HARMONIES, "three_harmony")
    triad_pair_keys = {
        frozenset(pair) for h in three_harmonies for pair in combinations(h.members, 2)
    }

    three_punishments = _detect_triads(branches, THREE_PUNISHMENTS, "three_punishment")
    pair_punishments = _detect_pairs(branches, PAIR_PUNISHMENTS, "three_punishment")

    return InteractionsOutput(
        stem_combinations=_detect_pairs(stems, STEM_COMBINATIONS, "stem_combination"),
        branch_clashes=_detect_pairs(branches, BRANCH_CLASHES, "branch_clash"),
        six_harmonies=_detect_pairs(branches, SIX_HARMONIES, "six_harmony"),
        three_harmonies=three_harmonies,
        half_harmonies=_detect_pairs(
            branches, HALF_HARMONIES, "half_harmony", excluded_keys=triad_pair_keys
        ),
        three_punishments=three_punishments + pair_punishments,
        self_punishments=_detect_self_punishments(branches),
        six_harms=_detect_pairs(branches, SIX_HARMS, "six_harm"),
        six_breaks=_detect_pairs(branches, SIX_BREAKS, "six_break"),
    )
