"""Day Master (日主) strength, element balance, and useful/harmful gods."""

from __future__ import annotations

from calculator.models import Branch, Pillar, Stem
from calculator.ten_gods import ten_god

# ── Element mapping ───────────────────────────────────────────────────────────
# Indices: 0=木 1=火 2=土 3=金 4=水

_ELEM_OF: dict[str, int] = {
    "甲": 0,
    "乙": 0,
    "丙": 1,
    "丁": 1,
    "戊": 2,
    "己": 2,
    "庚": 3,
    "辛": 3,
    "壬": 4,
    "癸": 4,
}

_ELEM_NAMES: tuple[str, ...] = ("木", "火", "土", "金", "水")

# Season element (chief qi) for each Earthly Branch
_BRANCH_SEASON: dict[str, int] = {
    "子": 4,
    "丑": 2,
    "寅": 0,
    "卯": 0,
    "辰": 2,
    "巳": 1,
    "午": 1,
    "未": 2,
    "申": 3,
    "酉": 3,
    "戌": 2,
    "亥": 4,
}

# element i generates element _GENERATES[i]: 木火土金水
_GENERATES: tuple[int, ...] = (1, 2, 3, 4, 0)
# element i controls element _CONTROLS[i]: 木→土 火→金 土→水 金→木 水→火
_CONTROLS: tuple[int, ...] = (2, 3, 4, 0, 1)

# Seasonal state scores (旺 peak strength → 死 dominated)
_SEASON_SCORES: dict[str, float] = {
    "旺": 5.0,
    "相": 3.0,
    "休": 0.0,
    "囚": -2.0,
    "死": -4.0,
}

# Ten god contribution to DM strength (positive = supports DM)
_TG_SCORES: dict[str, float] = {
    "比肩": 2.0,
    "劫财": 2.0,
    "正印": 1.5,
    "偏印": 1.0,
    "食神": -1.0,
    "伤官": -1.5,
    "正财": -1.5,
    "偏财": -1.0,
    "正官": -2.0,
    "七杀": -2.0,
}

# Heavenly stems contribute full weight; hidden stems are less prominent
_HEAVENLY_W: float = 1.0
_HIDDEN_W: float = 0.5


# ── Public API ────────────────────────────────────────────────────────────────


def dm_element(day_stem: Stem) -> str:
    """Element name (木/火/土/金/水) of the Day Master stem."""
    return _ELEM_NAMES[_ELEM_OF[day_stem]]


def seasonal_state(day_stem: Stem, month_branch: Branch) -> str:
    """Five seasonal states of DM element in the given month branch.

    Returns one of: 旺 (peak) / 相 (prime) / 休 (rest) / 囚 (imprisoned) / 死 (dying)
    """
    dm_e = _ELEM_OF[day_stem]
    s_e = _BRANCH_SEASON[month_branch]
    if dm_e == s_e:
        return "旺"
    if _GENERATES[s_e] == dm_e:  # season element generates DM
        return "相"
    if _GENERATES[dm_e] == s_e:  # DM generates season element
        return "休"
    if _CONTROLS[dm_e] == s_e:  # DM controls season (energy wasted)
        return "囚"
    return "死"  # season controls DM: _CONTROLS[s_e] == dm_e


def element_balance(
    pillars: list[Pillar],
    hidden: dict[str, list[Stem]],
) -> dict[str, float]:
    """Percentage of each element in the chart (values sum to 1.0).

    Heavenly stems contribute weight 1.0; hidden stems contribute 0.5 each.
    """
    weights: dict[int, float] = dict.fromkeys(range(5), 0.0)
    for p in pillars:
        weights[_ELEM_OF[p.stem]] += _HEAVENLY_W
        for hs in hidden.get(p.name, []):
            weights[_ELEM_OF[hs]] += _HIDDEN_W
    total = sum(weights.values())
    if total == 0.0:
        return dict.fromkeys(_ELEM_NAMES, 0.0)
    return {_ELEM_NAMES[i]: round(weights[i] / total, 4) for i in range(5)}


def dm_strength_score(
    pillars: list[Pillar],
    hidden: dict[str, list[Stem]],
) -> float:
    """Numeric DM strength score. Positive = strong (旺), negative = weak (弱).

    Combines seasonal state with support/drain contributions from all stems.
    """
    day_p = next(p for p in pillars if p.name == "day")
    month_p = next(p for p in pillars if p.name == "month")
    dm = day_p.stem

    score: float = _SEASON_SCORES[seasonal_state(dm, month_p.branch)]

    for p in pillars:
        if p.name != "day":
            score += _TG_SCORES[ten_god(dm, p.stem)] * _HEAVENLY_W
        for hs in hidden.get(p.name, []):
            score += _TG_SCORES[ten_god(dm, hs)] * _HIDDEN_W

    return score


def is_strong_dm(score: float) -> bool:
    """True if the Day Master is strong (score > 0)."""
    return score > 0.0


def yong_shen(is_strong: bool) -> list[str]:
    """Useful god (用神) ten god categories for the given DM strength.

    Weak DM → needs support (比/劫/印).
    Strong DM → needs draining (食/伤/财/官/杀).
    """
    if is_strong:
        return ["食神", "伤官", "正财", "偏财", "正官", "七杀"]
    return ["比肩", "劫财", "正印", "偏印"]


def ji_shen(is_strong: bool) -> list[str]:
    """Harmful god (忌神) ten god categories — the opposite of 用神."""
    return yong_shen(not is_strong)
