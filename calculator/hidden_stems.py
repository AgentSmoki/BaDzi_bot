"""Hidden stems (藏干) — Heavenly Stems concealed inside each Earthly Branch.

Three schools are supported:
  traditional — classical texts (渊海子平, 三命通会)
  modern      — 子 carries both 壬 and 癸; reordered middle/residual qi
  ken_lai     — traditional except 午 contains 丁 only (no 己)
"""

from __future__ import annotations

from typing import Any, cast

from calculator.models import Branch, HiddenStemsSchool, Stem

# ── Hidden-stems tables ───────────────────────────────────────────────────────
# Each entry: (chief qi, [middle qi], [residual qi]) collapsed to ordered list.
# Order = chief → middle → residual (important for Ten Gods weighting).

_TRADITIONAL: dict[str, list[str]] = {
    "子": ["癸"],
    "丑": ["己", "癸", "辛"],
    "寅": ["甲", "丙", "戊"],
    "卯": ["乙"],
    "辰": ["戊", "乙", "癸"],
    "巳": ["丙", "戊", "庚"],
    "午": ["丁", "己"],
    "未": ["己", "丁", "乙"],
    "申": ["庚", "壬", "戊"],
    "酉": ["辛"],
    "戌": ["戊", "辛", "丁"],
    "亥": ["壬", "甲"],
}

# Modern school: 子 gains 壬 as chief qi; several branches reorder middle/residual.
_MODERN: dict[str, list[str]] = {
    "子": ["壬", "癸"],
    "丑": ["己", "辛", "癸"],
    "寅": ["甲", "戊", "丙"],
    "卯": ["乙"],
    "辰": ["戊", "癸", "乙"],
    "巳": ["丙", "戊", "庚"],
    "午": ["丁", "己"],
    "未": ["己", "乙", "丁"],
    "申": ["庚", "戊", "壬"],
    "酉": ["辛"],
    "戌": ["戊", "丁", "辛"],
    "亥": ["壬", "甲"],
}

# Ken Lai school: same as traditional except 午 = 丁 only.
_KEN_LAI: dict[str, list[str]] = {
    **_TRADITIONAL,
    "午": ["丁"],
}

_TABLES: dict[HiddenStemsSchool, dict[str, list[str]]] = {
    "traditional": _TRADITIONAL,
    "modern": _MODERN,
    "ken_lai": _KEN_LAI,
}


# ── Public API ────────────────────────────────────────────────────────────────


def hidden_stems(branch: Branch, school: HiddenStemsSchool = "traditional") -> list[Stem]:
    """Return the hidden stems for *branch* under the given *school*.

    The list is ordered chief → middle → residual qi.
    """
    raw = _TABLES[school][branch]
    return [cast("Stem", s) for s in raw]


def chart_hidden_stems(
    pillars: list[Any],
    school: HiddenStemsSchool = "traditional",
) -> dict[str, list[Stem]]:
    """Map each pillar's branch to its hidden stems under *school*.

    Returns a dict keyed by pillar name (year/month/day/hour).
    """
    return {p.name: hidden_stems(p.branch, school) for p in pillars}
