"""Ten Gods (十神) mapping for Ba Zi charts."""

from __future__ import annotations

from calculator.models import Pillar, Stem

# ── Element mapping ───────────────────────────────────────────────────────────
# Indices: 0=木 1=火 2=土 3=金 4=水

_ELEM: dict[str, int] = {
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

_IS_YANG: dict[str, bool] = {
    "甲": True,
    "乙": False,
    "丙": True,
    "丁": False,
    "戊": True,
    "己": False,
    "庚": True,
    "辛": False,
    "壬": True,
    "癸": False,
}

# _GENERATES[i] = element index that element i generates (木火土金水)
_GENERATES: tuple[int, ...] = (1, 2, 3, 4, 0)

# _CONTROLS[i] = element index that element i controls (木→土 火→金 土→水 金→木 水→火)
_CONTROLS: tuple[int, ...] = (2, 3, 4, 0, 1)

# (relationship, same_polarity) → ten god label
_MAP: dict[tuple[str, bool], str] = {
    ("same", True): "比肩",
    ("same", False): "劫财",
    ("dm_gen", True): "食神",
    ("dm_gen", False): "伤官",
    ("dm_ctrl", True): "偏财",
    ("dm_ctrl", False): "正财",
    ("t_ctrl", True): "七杀",
    ("t_ctrl", False): "正官",
    ("t_gen", True): "偏印",
    ("t_gen", False): "正印",
}


# ── Public API ────────────────────────────────────────────────────────────────


def ten_god(day_master: Stem, target: Stem) -> str:
    """Return the Ten God label of *target* relative to *day_master*."""
    dm_e = _ELEM[day_master]
    t_e = _ELEM[target]
    same_pol = _IS_YANG[day_master] == _IS_YANG[target]

    if t_e == dm_e:
        rel = "same"
    elif _GENERATES[dm_e] == t_e:
        rel = "dm_gen"
    elif _CONTROLS[dm_e] == t_e:
        rel = "dm_ctrl"
    elif _CONTROLS[t_e] == dm_e:
        rel = "t_ctrl"
    else:
        rel = "t_gen"

    return _MAP[(rel, same_pol)]


def chart_ten_gods(
    pillars: list[Pillar],
    hidden: dict[str, list[Stem]],
) -> dict[str, list[str]]:
    """For each pillar return [stem_god, *hidden_gods].

    The day pillar's heavenly stem is labeled "日主" instead of a ten god.
    """
    dm = next(p.stem for p in pillars if p.name == "day")
    result: dict[str, list[str]] = {}
    for p in pillars:
        stem_god = "日主" if p.name == "day" else ten_god(dm, p.stem)
        hidden_gods = [ten_god(dm, s) for s in hidden.get(p.name, [])]
        result[p.name] = [stem_god, *hidden_gods]
    return result
