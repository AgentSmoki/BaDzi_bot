"""Tests for calculator/auxiliary.py — 胎元 (Tai Yuan) and 命宫 (Ming Gong)."""

from __future__ import annotations

from typing import cast

import pytest

from calculator.auxiliary import (
    calculate_auxiliary_pillars,
    calculate_ming_gong,
    calculate_tai_yuan,
)
from calculator.models import (
    BRANCHES,
    STEMS,
    AuxiliaryPillars,
    Branch,
    Pillar,
    Stem,
)


def _mk(stem_branch_pairs: list[tuple[str, str]]) -> list[Pillar]:
    names = ["year", "month", "day", "hour"]
    return [
        Pillar(stem=cast(Stem, s), branch=cast(Branch, b), name=n)
        for (s, b), n in zip(stem_branch_pairs, names, strict=True)
    ]


def _p(stem: str, branch: str, name: str) -> Pillar:
    return Pillar(stem=cast(Stem, stem), branch=cast(Branch, branch), name=name)


# ── Tai Yuan (胎元) ───────────────────────────────────────────────────────────


class TestTaiYuan:
    def test_volzhsky_1999_month_gui_you_to_jia_zi(self) -> None:
        # Канонический эталон Mingli: month 癸酉 → 胎元 甲子
        out = calculate_tai_yuan(_p("癸", "酉", "month"))
        assert out.stem == "甲"
        assert out.branch == "子"
        assert out.name == "tai_yuan"

    def test_jia_zi_month_to_yi_mao(self) -> None:
        # 甲子 → stem +1=乙, branch +3=卯
        out = calculate_tai_yuan(_p("甲", "子", "month"))
        assert out.stem == "乙"
        assert out.branch == "卯"

    def test_gui_hai_month_wraps_correctly(self) -> None:
        # 癸亥 → stem 癸(9)+1 wraps to 甲(0), branch 亥(11)+3 wraps to 寅(2)
        out = calculate_tai_yuan(_p("癸", "亥", "month"))
        assert out.stem == "甲"
        assert out.branch == "寅"

    def test_bing_yin_month_to_ding_si(self) -> None:
        out = calculate_tai_yuan(_p("丙", "寅", "month"))
        assert out.stem == "丁"
        assert out.branch == "巳"

    def test_tai_yuan_has_name(self) -> None:
        out = calculate_tai_yuan(_p("癸", "酉", "month"))
        assert out.name == "tai_yuan"


# ── Ming Gong (命宫) ──────────────────────────────────────────────────────────


class TestMingGong:
    def test_volzhsky_1999_canonical(self) -> None:
        # Канонический эталон Mingli:
        #   year 己卯, month 癸酉, hour 庚子 → 命宫 癸酉
        out = calculate_ming_gong(
            _p("己", "卯", "year"),
            _p("癸", "酉", "month"),
            _p("庚", "子", "hour"),
        )
        assert out.stem == "癸"
        assert out.branch == "酉"
        assert out.name == "ming_gong"

    def test_yin_month_zi_hour_yields_chen(self) -> None:
        # month 寅 (yin=0), hour 子 (zi=0) → mg_yin = 14 → 14%12 = 2 → 辰
        # year 甲: starting_yin_stem = 2 (丙). mg_stem = (2+2)%10 = 4 = 戊 → 戊辰
        out = calculate_ming_gong(
            _p("甲", "子", "year"),
            _p("丙", "寅", "month"),
            _p("甲", "子", "hour"),
        )
        assert out.stem == "戊"
        assert out.branch == "辰"

    def test_zi_month_hai_hour(self) -> None:
        # month 子 (yin=10), hour 亥 (zi=11)
        # mg_yin = (14-10-11)%12 = -7 mod 12 = 5 → branch idx (5+2)%12 = 7 → 未
        # year 甲: stem = (2+5)%10 = 7 → 辛 → 辛未
        out = calculate_ming_gong(
            _p("甲", "子", "year"),
            _p("丙", "子", "month"),
            _p("乙", "亥", "hour"),
        )
        assert out.stem == "辛"
        assert out.branch == "未"

    def test_branch_in_valid_set(self) -> None:
        out = calculate_ming_gong(
            _p("乙", "丑", "year"),
            _p("丁", "卯", "month"),
            _p("丙", "辰", "hour"),
        )
        assert out.branch in BRANCHES
        assert out.stem in STEMS

    def test_ming_gong_has_name(self) -> None:
        out = calculate_ming_gong(
            _p("己", "卯", "year"),
            _p("癸", "酉", "month"),
            _p("庚", "子", "hour"),
        )
        assert out.name == "ming_gong"

    def test_year_stem_changes_only_stem_not_branch(self) -> None:
        # Same month + hour, year stems with DIFFERENT mod 5 → branch stays, stem differs.
        # 己 (idx 5, mod 5 = 0) and 乙 (idx 1, mod 5 = 1) → different 五虎遁 starting stems.
        m = _p("癸", "酉", "month")
        h = _p("庚", "子", "hour")
        a = calculate_ming_gong(_p("己", "卯", "year"), m, h)
        b = calculate_ming_gong(_p("乙", "卯", "year"), m, h)
        assert a.branch == b.branch
        assert a.stem != b.stem


# ── Combined API ──────────────────────────────────────────────────────────────


class TestAuxiliaryPillars:
    def test_volzhsky_full(self) -> None:
        out = calculate_auxiliary_pillars(
            _mk([("己", "卯"), ("癸", "酉"), ("丁", "亥"), ("庚", "子")])
        )
        assert isinstance(out, AuxiliaryPillars)
        assert out.tai_yuan.stem == "甲"
        assert out.tai_yuan.branch == "子"
        assert out.ming_gong.stem == "癸"
        assert out.ming_gong.branch == "酉"

    def test_returns_auxiliary_pillars_type(self) -> None:
        out = calculate_auxiliary_pillars(
            _mk([("甲", "子"), ("丙", "寅"), ("丁", "卯"), ("庚", "午")])
        )
        assert isinstance(out, AuxiliaryPillars)
        assert out.tai_yuan.name == "tai_yuan"
        assert out.ming_gong.name == "ming_gong"

    def test_invalid_pillar_count_raises(self) -> None:
        only_three = [
            _p("甲", "子", "year"),
            _p("乙", "丑", "month"),
            _p("丙", "寅", "day"),
        ]
        with pytest.raises(ValueError, match="expected 4 pillars"):
            calculate_auxiliary_pillars(only_three)

    def test_invalid_pillar_names_raises(self) -> None:
        bad = [
            _p("甲", "子", "foo"),
            _p("乙", "丑", "bar"),
            _p("丙", "寅", "baz"),
            _p("丁", "卯", "qux"),
        ]
        with pytest.raises(ValueError, match="pillar names must be"):
            calculate_auxiliary_pillars(bad)


# ── Cycle / wrap properties ───────────────────────────────────────────────────


class TestCycleProperties:
    def test_tai_yuan_branch_is_three_ahead_modular(self) -> None:
        for i, branch in enumerate(BRANCHES):
            month = _p("甲", cast(Branch, branch), "month")
            out = calculate_tai_yuan(month)
            expected = BRANCHES[(i + 3) % 12]
            assert out.branch == expected

    def test_tai_yuan_stem_is_one_ahead_modular(self) -> None:
        for i, stem in enumerate(STEMS):
            month = _p(cast(Stem, stem), "子", "month")
            out = calculate_tai_yuan(month)
            expected = STEMS[(i + 1) % 10]
            assert out.stem == expected
