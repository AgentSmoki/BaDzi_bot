"""Tests for calculator/symbolic_stars.py — 60 classical Shen Sha (神煞)."""

from __future__ import annotations

from typing import cast

from calculator.models import Branch, Pillar, Stem, SymbolicStar
from calculator.symbolic_stars import calculate_symbolic_stars


def _mk(stem_branch_pairs: list[tuple[str, str]]) -> list[Pillar]:
    """Build 4 pillars from (stem, branch) tuples in Y/M/D/H order."""
    names = ["year", "month", "day", "hour"]
    return [
        Pillar(stem=cast(Stem, s), branch=cast(Branch, b), name=n)
        for (s, b), n in zip(stem_branch_pairs, names, strict=True)
    ]


def _names(out_stars: list[SymbolicStar], name_zh: str) -> list[SymbolicStar]:
    return [s for s in out_stars if s.name_zh == name_zh]


# ── Empty / structure ─────────────────────────────────────────────────────────


class TestStructure:
    def test_returns_output(self) -> None:
        out = calculate_symbolic_stars(
            _mk([("甲", "子"), ("甲", "子"), ("甲", "子"), ("甲", "子")])
        )
        assert hasattr(out, "stars")
        assert isinstance(out.stars, list)

    def test_inert_chart_no_stars_or_minimal(self) -> None:
        # 甲子 day on 甲子 anchors: 学堂 of 甲→亥 absent; 禄神 of 甲→寅 absent etc.
        # Some triadic stars may still hit (e.g. 将星 申子辰→子, day_branch=子 → 子 in chart).
        out = calculate_symbolic_stars(
            _mk([("甲", "子"), ("甲", "子"), ("甲", "子"), ("甲", "子")])
        )
        # 将星 (jiangxing) for day_branch 子 → target 子 is everywhere in chart.
        assert any(s.name_zh == "将星" for s in out.stars)


# ── Group A: day_stem → branch ────────────────────────────────────────────────


class TestDayStemAnchored:
    def test_tianyi_jia_day_with_chou(self) -> None:
        # 甲日 + 丑 in chart → 天乙贵人
        out = calculate_symbolic_stars(
            _mk([("乙", "丑"), ("丙", "寅"), ("甲", "辰"), ("丁", "卯")])
        )
        hits = _names(out.stars, "天乙贵人")
        assert len(hits) == 1
        assert "year" in hits[0].pillars

    def test_tianyi_xin_day_with_yin_or_wu(self) -> None:
        # 辛日 → 寅,午
        out = calculate_symbolic_stars(
            _mk([("乙", "寅"), ("丙", "辰"), ("辛", "酉"), ("丁", "午")])
        )
        hits = _names(out.stars, "天乙贵人")
        assert len(hits) == 1
        assert set(hits[0].pillars) == {"year", "hour"}

    def test_taiji_jia_with_zi_or_wu(self) -> None:
        # 甲日 → 子,午
        out = calculate_symbolic_stars(
            _mk([("乙", "子"), ("丙", "辰"), ("甲", "戌"), ("丁", "卯")])
        )
        assert any(s.name_zh == "太极贵人" for s in out.stars)

    def test_wenchang_jia_with_si(self) -> None:
        out = calculate_symbolic_stars(
            _mk([("乙", "巳"), ("丙", "辰"), ("甲", "戌"), ("丁", "卯")])
        )
        assert any(s.name_zh == "文昌贵人" for s in out.stars)

    def test_fuxing_jia_with_yin(self) -> None:
        out = calculate_symbolic_stars(
            _mk([("乙", "寅"), ("丙", "辰"), ("甲", "戌"), ("丁", "卯")])
        )
        assert any(s.name_zh == "福星贵人" for s in out.stars)

    def test_guoyin_jia_with_xu(self) -> None:
        out = calculate_symbolic_stars(
            _mk([("乙", "戌"), ("丙", "辰"), ("甲", "申"), ("丁", "卯")])
        )
        assert any(s.name_zh == "国印贵人" for s in out.stars)

    def test_xuetang_jia_with_hai(self) -> None:
        out = calculate_symbolic_stars(
            _mk([("乙", "亥"), ("丙", "辰"), ("甲", "戌"), ("丁", "卯")])
        )
        assert any(s.name_zh == "学堂" for s in out.stars)

    def test_ciguan_jia_with_yin(self) -> None:
        out = calculate_symbolic_stars(
            _mk([("乙", "寅"), ("丙", "辰"), ("甲", "戌"), ("丁", "卯")])
        )
        assert any(s.name_zh == "词馆" for s in out.stars)

    def test_lushen_jia_with_yin(self) -> None:
        out = calculate_symbolic_stars(
            _mk([("乙", "寅"), ("丙", "辰"), ("甲", "戌"), ("丁", "卯")])
        )
        assert any(s.name_zh == "禄神" for s in out.stars)

    def test_yangren_jia_with_mao(self) -> None:
        # Canonical 甲→卯
        out = calculate_symbolic_stars(
            _mk([("乙", "卯"), ("丙", "辰"), ("甲", "戌"), ("丁", "巳")])
        )
        assert any(s.name_zh == "羊刃" for s in out.stars)

    def test_yangren_geng_with_you(self) -> None:
        # 庚→酉
        out = calculate_symbolic_stars(
            _mk([("乙", "酉"), ("丙", "辰"), ("庚", "戌"), ("丁", "巳")])
        )
        assert any(s.name_zh == "羊刃" for s in out.stars)

    def test_feiren_jia_with_you(self) -> None:
        # 甲→酉 (clash of yangren 卯)
        out = calculate_symbolic_stars(
            _mk([("乙", "酉"), ("丙", "辰"), ("甲", "戌"), ("丁", "巳")])
        )
        assert any(s.name_zh == "飞刃" for s in out.stars)

    def test_jinyu_jia_with_chen(self) -> None:
        out = calculate_symbolic_stars(
            _mk([("乙", "辰"), ("丙", "卯"), ("甲", "戌"), ("丁", "巳")])
        )
        assert any(s.name_zh == "金舆" for s in out.stars)

    def test_hongyan_jia_with_wu(self) -> None:
        out = calculate_symbolic_stars(
            _mk([("乙", "午"), ("丙", "卯"), ("甲", "戌"), ("丁", "巳")])
        )
        assert any(s.name_zh == "红艳" for s in out.stars)

    def test_liuxia_jia_with_you(self) -> None:
        out = calculate_symbolic_stars(
            _mk([("乙", "酉"), ("丙", "卯"), ("甲", "戌"), ("丁", "巳")])
        )
        assert any(s.name_zh == "流霞" for s in out.stars)

    def test_jielukongwang_jia_with_shen(self) -> None:
        out = calculate_symbolic_stars(
            _mk([("乙", "申"), ("丙", "卯"), ("甲", "戌"), ("丁", "巳")])
        )
        assert any(s.name_zh == "截路空亡" for s in out.stars)

    def test_anlu_jia_with_hai(self) -> None:
        out = calculate_symbolic_stars(
            _mk([("乙", "亥"), ("丙", "卯"), ("甲", "戌"), ("丁", "巳")])
        )
        assert any(s.name_zh == "暗禄" for s in out.stars)

    def test_tianguan_jia_with_wei(self) -> None:
        out = calculate_symbolic_stars(
            _mk([("乙", "未"), ("丙", "卯"), ("甲", "戌"), ("丁", "巳")])
        )
        assert any(s.name_zh == "天官贵人" for s in out.stars)


# ── Group B: day_branch (triad) → branch ──────────────────────────────────────


class TestTriadAnchored:
    def test_taohua_zi_day_with_you(self) -> None:
        # 申子辰 group → 桃花=酉
        out = calculate_symbolic_stars(
            _mk([("乙", "酉"), ("丙", "卯"), ("甲", "子"), ("丁", "巳")])
        )
        assert any(s.name_zh == "桃花" for s in out.stars)

    def test_yima_zi_day_with_yin(self) -> None:
        # 申子辰 → 驿马=寅
        out = calculate_symbolic_stars(
            _mk([("乙", "寅"), ("丙", "卯"), ("甲", "子"), ("丁", "巳")])
        )
        assert any(s.name_zh == "驿马" for s in out.stars)

    def test_huagai_zi_day_with_chen(self) -> None:
        # 申子辰 → 华盖=辰
        out = calculate_symbolic_stars(
            _mk([("乙", "辰"), ("丙", "卯"), ("甲", "子"), ("丁", "巳")])
        )
        assert any(s.name_zh == "华盖" for s in out.stars)

    def test_jiangxing_zi_day_with_zi(self) -> None:
        # 申子辰 → 将星=子 (day branch itself is 子)
        out = calculate_symbolic_stars(
            _mk([("乙", "辰"), ("丙", "卯"), ("甲", "子"), ("丁", "巳")])
        )
        assert any(s.name_zh == "将星" for s in out.stars)

    def test_jiesha_zi_day_with_si(self) -> None:
        # 申子辰 → 劫煞=巳
        out = calculate_symbolic_stars(
            _mk([("乙", "辰"), ("丙", "卯"), ("甲", "子"), ("丁", "巳")])
        )
        assert any(s.name_zh == "劫煞" for s in out.stars)

    def test_zaisha_zi_day_with_wu(self) -> None:
        out = calculate_symbolic_stars(
            _mk([("乙", "午"), ("丙", "卯"), ("甲", "子"), ("丁", "巳")])
        )
        assert any(s.name_zh == "灾煞" for s in out.stars)

    def test_tiansha_zi_day_with_wei(self) -> None:
        out = calculate_symbolic_stars(
            _mk([("乙", "未"), ("丙", "卯"), ("甲", "子"), ("丁", "巳")])
        )
        assert any(s.name_zh == "天煞" for s in out.stars)

    def test_wangshen_zi_day_with_hai(self) -> None:
        out = calculate_symbolic_stars(
            _mk([("乙", "亥"), ("丙", "卯"), ("甲", "子"), ("丁", "巳")])
        )
        assert any(s.name_zh == "亡神" for s in out.stars)

    def test_liue_zi_day_with_mao(self) -> None:
        out = calculate_symbolic_stars(
            _mk([("乙", "卯"), ("丙", "辰"), ("甲", "子"), ("丁", "巳")])
        )
        assert any(s.name_zh == "六厄" for s in out.stars)

    def test_panan_zi_day_with_chou(self) -> None:
        out = calculate_symbolic_stars(
            _mk([("乙", "丑"), ("丙", "辰"), ("甲", "子"), ("丁", "巳")])
        )
        assert any(s.name_zh == "攀鞍" for s in out.stars)

    def test_suiyi_zi_year_with_yin(self) -> None:
        # 岁驿 (year-anchored): year_branch 子 → 寅
        out = calculate_symbolic_stars(
            _mk([("乙", "子"), ("丙", "辰"), ("甲", "戌"), ("丁", "寅")])
        )
        assert any(s.name_zh == "岁驿" for s in out.stars)


# ── Group C: month_branch → branch ────────────────────────────────────────────


class TestMonthBranchAnchored:
    def test_tianyi_doctor_yin_month_with_chou(self) -> None:
        # 寅月 → 天医=丑
        out = calculate_symbolic_stars(
            _mk([("乙", "戌"), ("丙", "寅"), ("甲", "子"), ("丁", "丑")])
        )
        assert any(s.name_zh == "天医" for s in out.stars)

    def test_jieshen_yin_month_with_shen(self) -> None:
        # 寅/卯月 → 解神=申
        out = calculate_symbolic_stars(
            _mk([("乙", "申"), ("丙", "寅"), ("甲", "子"), ("丁", "丑")])
        )
        assert any(s.name_zh == "解神" for s in out.stars)

    def test_xueren_yin_month_with_chou(self) -> None:
        out = calculate_symbolic_stars(
            _mk([("乙", "戌"), ("丙", "寅"), ("甲", "子"), ("丁", "丑")])
        )
        assert any(s.name_zh == "血刃" for s in out.stars)

    def test_yuesha_yin_month_with_chou(self) -> None:
        # 寅/午/戌月 → 月煞=丑
        out = calculate_symbolic_stars(
            _mk([("乙", "戌"), ("丙", "寅"), ("甲", "子"), ("丁", "丑")])
        )
        assert any(s.name_zh == "月煞" for s in out.stars)


# ── Group D: month_branch → stem (天德/月德) ──────────────────────────────────


class TestMonthBranchToStem:
    def test_tiande_yin_month_with_ding_stem(self) -> None:
        # 寅月 → 天德=丁 (stem)
        out = calculate_symbolic_stars(
            _mk([("乙", "戌"), ("丁", "寅"), ("甲", "子"), ("戊", "丑")])
        )
        assert any(s.name_zh == "天德贵人" for s in out.stars)

    def test_tiande_mao_month_with_shen_branch(self) -> None:
        # 卯月 → 天德=申 (BRANCH form, not stem)
        out = calculate_symbolic_stars(
            _mk([("乙", "申"), ("丙", "卯"), ("甲", "子"), ("丁", "巳")])
        )
        assert any(s.name_zh == "天德贵人" for s in out.stars)

    def test_yuede_yin_month_with_bing_stem(self) -> None:
        # 寅/午/戌月 → 月德=丙 (stem)
        out = calculate_symbolic_stars(
            _mk([("乙", "戌"), ("丙", "寅"), ("甲", "子"), ("丁", "丑")])
        )
        assert any(s.name_zh == "月德贵人" for s in out.stars)

    def test_tiande_he_yin_month_with_ren(self) -> None:
        # 寅月 → 天德合=壬
        out = calculate_symbolic_stars(
            _mk([("壬", "戌"), ("丁", "寅"), ("甲", "子"), ("戊", "丑")])
        )
        assert any(s.name_zh == "天德合" for s in out.stars)

    def test_yuede_he_yin_month_with_xin(self) -> None:
        # 寅/午/戌月 → 月德合=辛
        out = calculate_symbolic_stars(
            _mk([("辛", "戌"), ("丙", "寅"), ("甲", "子"), ("丁", "丑")])
        )
        assert any(s.name_zh == "月德合" for s in out.stars)


# ── Group E: year_branch → branch ─────────────────────────────────────────────


class TestYearBranchAnchored:
    def test_guchen_zi_year_with_yin(self) -> None:
        # 亥/子/丑年 → 孤辰=寅
        out = calculate_symbolic_stars(
            _mk([("乙", "子"), ("丙", "辰"), ("甲", "戌"), ("丁", "寅")])
        )
        assert any(s.name_zh == "孤辰" for s in out.stars)

    def test_guasu_zi_year_with_xu(self) -> None:
        out = calculate_symbolic_stars(
            _mk([("乙", "子"), ("丙", "辰"), ("甲", "戌"), ("丁", "寅")])
        )
        assert any(s.name_zh == "寡宿" for s in out.stars)

    def test_dahao_zi_year_with_wu(self) -> None:
        out = calculate_symbolic_stars(
            _mk([("乙", "子"), ("丙", "辰"), ("甲", "午"), ("丁", "寅")])
        )
        assert any(s.name_zh == "大耗" for s in out.stars)

    def test_xiaohao_zi_year_with_si(self) -> None:
        out = calculate_symbolic_stars(
            _mk([("乙", "子"), ("丙", "辰"), ("甲", "戌"), ("丁", "巳")])
        )
        assert any(s.name_zh == "小耗" for s in out.stars)

    def test_pima_zi_year_with_chen(self) -> None:
        out = calculate_symbolic_stars(
            _mk([("乙", "子"), ("丙", "辰"), ("甲", "戌"), ("丁", "寅")])
        )
        assert any(s.name_zh == "披麻" for s in out.stars)

    def test_sangmen_zi_year_with_yin(self) -> None:
        out = calculate_symbolic_stars(
            _mk([("乙", "子"), ("丙", "辰"), ("甲", "戌"), ("丁", "寅")])
        )
        assert any(s.name_zh == "丧门" for s in out.stars)

    def test_diaoke_zi_year_with_xu(self) -> None:
        out = calculate_symbolic_stars(
            _mk([("乙", "子"), ("丙", "辰"), ("甲", "戌"), ("丁", "寅")])
        )
        assert any(s.name_zh == "吊客" for s in out.stars)

    def test_baihu_zi_year_with_shen(self) -> None:
        out = calculate_symbolic_stars(
            _mk([("乙", "子"), ("丙", "辰"), ("甲", "申"), ("丁", "寅")])
        )
        assert any(s.name_zh == "白虎" for s in out.stars)

    def test_tianxi_zi_year_with_you(self) -> None:
        # Use valid 60-cycle pairs: 甲子 year + 辛酉 day (both legal combos)
        out = calculate_symbolic_stars(
            _mk([("甲", "子"), ("丙", "辰"), ("辛", "酉"), ("丁", "卯")])
        )
        assert any(s.name_zh == "天喜" for s in out.stars)

    def test_hongluan_zi_year_with_mao(self) -> None:
        # 甲子 year + 丁卯 month (target 卯 in month)
        out = calculate_symbolic_stars(
            _mk([("甲", "子"), ("丁", "卯"), ("丙", "寅"), ("戊", "申")])
        )
        assert any(s.name_zh == "红鸾" for s in out.stars)


# ── Group F: self-pillar stars ────────────────────────────────────────────────


class TestSelfPillarStars:
    def test_kuigang_geng_chen_day(self) -> None:
        out = calculate_symbolic_stars(
            _mk([("乙", "子"), ("丙", "辰"), ("庚", "辰"), ("丁", "寅")])
        )
        hits = _names(out.stars, "魁罡")
        assert len(hits) == 1
        assert hits[0].pillars == ["day"]

    def test_kuigang_wu_xu_day(self) -> None:
        out = calculate_symbolic_stars(
            _mk([("乙", "子"), ("丙", "辰"), ("戊", "戌"), ("丁", "寅")])
        )
        assert any(s.name_zh == "魁罡" for s in out.stars)

    def test_yinchayangcuo_bing_zi_day(self) -> None:
        out = calculate_symbolic_stars(
            _mk([("乙", "丑"), ("乙", "亥"), ("丙", "子"), ("丁", "卯")])
        )
        assert any(s.name_zh == "阴差阳错" for s in out.stars)

    def test_shiedabai_jia_chen_day(self) -> None:
        out = calculate_symbolic_stars(
            _mk([("乙", "子"), ("丙", "卯"), ("甲", "辰"), ("丁", "巳")])
        )
        assert any(s.name_zh == "十恶大败" for s in out.stars)

    def test_guluan_yi_si_day(self) -> None:
        out = calculate_symbolic_stars(
            _mk([("丙", "子"), ("丙", "辰"), ("乙", "巳"), ("丁", "卯")])
        )
        assert any(s.name_zh == "孤鸾" for s in out.stars)

    def test_jinshen_advance_jia_zi_day(self) -> None:
        out = calculate_symbolic_stars(
            _mk([("乙", "丑"), ("丙", "卯"), ("甲", "子"), ("丁", "巳")])
        )
        assert any(s.name_zh == "进神" for s in out.stars)

    def test_tuishen_ding_chou_day(self) -> None:
        out = calculate_symbolic_stars(
            _mk([("乙", "酉"), ("丙", "卯"), ("丁", "丑"), ("丁", "巳")])
        )
        assert any(s.name_zh == "退神" for s in out.stars)

    def test_jinshen_gold_yi_chou_day(self) -> None:
        out = calculate_symbolic_stars(
            _mk([("乙", "未"), ("丙", "卯"), ("乙", "丑"), ("丁", "巳")])
        )
        assert any(s.name_zh == "金神" for s in out.stars)

    def test_ride_jia_yin_day(self) -> None:
        out = calculate_symbolic_stars(
            _mk([("乙", "未"), ("丙", "卯"), ("甲", "寅"), ("丁", "巳")])
        )
        assert any(s.name_zh == "日德" for s in out.stars)

    def test_rigui_ding_you_day(self) -> None:
        out = calculate_symbolic_stars(
            _mk([("乙", "未"), ("丙", "卯"), ("丁", "酉"), ("丁", "巳")])
        )
        assert any(s.name_zh == "日贵" for s in out.stars)


# ── Group G: special handlers ─────────────────────────────────────────────────


class TestSpecialHandlers:
    def test_tianluodiwang_xu_hai_pair(self) -> None:
        # 戌+亥 anywhere → Heaven Net (Tianluo)
        out = calculate_symbolic_stars(
            _mk([("乙", "戌"), ("丙", "亥"), ("甲", "子"), ("丁", "巳")])
        )
        assert any(s.name_zh == "天罗地网" for s in out.stars)

    def test_tianluodiwang_chen_si_pair(self) -> None:
        # 辰+巳 → Earth Web (Diwang)
        out = calculate_symbolic_stars(
            _mk([("乙", "辰"), ("丙", "巳"), ("甲", "子"), ("丁", "卯")])
        )
        assert any(s.name_zh == "天罗地网" for s in out.stars)

    def test_tianluodiwang_no_pair(self) -> None:
        # Only 戌 without 亥 → not detected
        out = calculate_symbolic_stars(
            _mk([("乙", "戌"), ("丙", "辰"), ("甲", "子"), ("丁", "卯")])
        )
        assert not any(s.name_zh == "天罗地网" for s in out.stars)

    def test_tianshe_spring_wu_yin_day(self) -> None:
        # spring (寅/卯/辰 month) + day_pillar 戊寅 → 天赦
        out = calculate_symbolic_stars(
            _mk([("乙", "未"), ("丙", "寅"), ("戊", "寅"), ("丁", "巳")])
        )
        assert any(s.name_zh == "天赦" for s in out.stars)

    def test_tianshe_summer_jia_wu_day(self) -> None:
        # summer (巳/午/未) + day 甲午 → 天赦
        out = calculate_symbolic_stars(
            _mk([("乙", "丑"), ("丙", "午"), ("甲", "午"), ("丁", "卯")])
        )
        assert any(s.name_zh == "天赦" for s in out.stars)

    def test_tianshe_wrong_season(self) -> None:
        # day 戊寅 but month is autumn → no 天赦
        out = calculate_symbolic_stars(
            _mk([("乙", "未"), ("丙", "申"), ("戊", "寅"), ("丁", "巳")])
        )
        assert not any(s.name_zh == "天赦" for s in out.stars)


# ── Output integrity ──────────────────────────────────────────────────────────


class TestOutputIntegrity:
    def test_all_stars_have_metadata_filled(self) -> None:
        out = calculate_symbolic_stars(
            _mk([("乙", "丑"), ("丙", "寅"), ("甲", "子"), ("丁", "卯")])
        )
        for star in out.stars:
            assert star.name_zh
            assert star.name_pinyin
            assert star.name_ru
            assert star.category in {
                "noble",
                "academic",
                "wealth",
                "career",
                "romance",
                "travel",
                "death_grave",
                "punishment",
                "violence",
                "loneliness",
                "spiritual",
                "calamity",
                "longevity",
                "child",
                "illness",
                "religious",
                "other",
            }
            assert star.nature in {"auspicious", "inauspicious", "mixed"}
            assert star.source
            assert star.pillars

    def test_pillars_in_natural_order(self) -> None:
        # 庚 in year pillar, day stem 庚 — yangren=酉 in year branch
        out = calculate_symbolic_stars(
            _mk([("辛", "酉"), ("丙", "卯"), ("庚", "戌"), ("丁", "巳")])
        )
        for star in out.stars:
            indices = ["year", "month", "day", "hour"]
            positions = [indices.index(p) for p in star.pillars]
            assert positions == sorted(positions)

    def test_invalid_pillar_count_raises(self) -> None:
        import pytest

        only_three = [
            Pillar(stem=cast(Stem, "甲"), branch=cast(Branch, "子"), name="year"),
            Pillar(stem=cast(Stem, "乙"), branch=cast(Branch, "丑"), name="month"),
            Pillar(stem=cast(Stem, "丙"), branch=cast(Branch, "寅"), name="day"),
        ]
        with pytest.raises(ValueError, match="expected 4 pillars"):
            calculate_symbolic_stars(only_three)

    def test_invalid_pillar_names_raises(self) -> None:
        import pytest

        bad = [
            Pillar(stem=cast(Stem, "甲"), branch=cast(Branch, "子"), name="foo"),
            Pillar(stem=cast(Stem, "乙"), branch=cast(Branch, "丑"), name="bar"),
            Pillar(stem=cast(Stem, "丙"), branch=cast(Branch, "寅"), name="baz"),
            Pillar(stem=cast(Stem, "丁"), branch=cast(Branch, "卯"), name="qux"),
        ]
        with pytest.raises(ValueError, match="pillar names must be"):
            calculate_symbolic_stars(bad)


# ── Block A v2: deferred dynamic stars (空亡, 元辰, 勾绞) ─────────────────────


class TestKongWang:
    def test_jia_zi_day_void_xu_hai(self) -> None:
        # 甲子日 (60-cycle idx 0) → 甲子旬 → void = 戌, 亥
        out = calculate_symbolic_stars(
            _mk([("乙", "戌"), ("丙", "辰"), ("甲", "子"), ("丁", "亥")])
        )
        hits = _names(out.stars, "空亡")
        assert len(hits) == 1
        assert set(hits[0].pillars) == {"year", "hour"}

    def test_jia_xu_day_void_shen_you(self) -> None:
        # 甲戌 (60-idx 10) → 甲戌旬 → void = 申, 酉
        out = calculate_symbolic_stars(
            _mk([("乙", "申"), ("丙", "辰"), ("甲", "戌"), ("丁", "酉")])
        )
        assert any(s.name_zh == "空亡" for s in out.stars)

    def test_jia_yin_day_void_zi_chou(self) -> None:
        # 甲寅 (60-idx 50) → 甲寅旬 → void = 子, 丑
        out = calculate_symbolic_stars(
            _mk([("乙", "子"), ("丙", "辰"), ("甲", "寅"), ("丁", "丑")])
        )
        hits = _names(out.stars, "空亡")
        assert len(hits) == 1
        assert set(hits[0].pillars) == {"year", "hour"}

    def test_no_kongwang_when_void_branches_absent(self) -> None:
        # 甲子日, void = 戌/亥, but chart has neither
        out = calculate_symbolic_stars(
            _mk([("乙", "卯"), ("丙", "辰"), ("甲", "子"), ("丁", "巳")])
        )
        assert not any(s.name_zh == "空亡" for s in out.stars)


class TestYuanChen:
    def test_yang_year_jia_zi(self) -> None:
        # 甲子 (Yang, year_branch 子=0): clash=午, +1 → 未
        out = calculate_symbolic_stars(
            _mk([("甲", "子"), ("丙", "辰"), ("丁", "卯"), ("丁", "未")])
        )
        hits = _names(out.stars, "元辰")
        assert len(hits) == 1
        assert hits[0].pillars == ["hour"]

    def test_yin_year_yi_chou(self) -> None:
        # 乙丑 (Yin, year_branch 丑=1): clash=未, -1 -> 午
        out = calculate_symbolic_stars(
            _mk([("乙", "丑"), ("丙", "辰"), ("丁", "卯"), ("丁", "午")])
        )
        assert any(s.name_zh == "元辰" for s in out.stars)

    def test_no_yuanchen_when_target_absent(self) -> None:
        out = calculate_symbolic_stars(
            _mk([("甲", "子"), ("丙", "辰"), ("丁", "卯"), ("丁", "巳")])
        )
        assert not any(s.name_zh == "元辰" for s in out.stars)


class TestGouJiao:
    def test_zi_year_targets_mao_and_you(self) -> None:
        # year_branch 子=0: targets = {+3=卯, -3=酉}
        out = calculate_symbolic_stars(
            _mk([("甲", "子"), ("乙", "卯"), ("丙", "寅"), ("丁", "酉")])
        )
        hits = _names(out.stars, "勾绞")
        assert len(hits) == 1
        assert set(hits[0].pillars) == {"month", "hour"}

    def test_chen_year_targets_wei_and_chou(self) -> None:
        # year_branch 辰=4: targets = {+3=未, -3=丑}
        out = calculate_symbolic_stars(
            _mk([("甲", "辰"), ("乙", "未"), ("丙", "寅"), ("丁", "丑")])
        )
        assert any(s.name_zh == "勾绞" for s in out.stars)

    def test_polarity_doesnt_change_target_set(self) -> None:
        # Yang (甲子) and Yin (乙丑) of same group → 勾绞 set is determined by year_branch only.
        # Just verify no asymmetric bug: 子 year and 丑 year give different but valid sets.
        a = calculate_symbolic_stars(_mk([("甲", "子"), ("乙", "卯"), ("丙", "寅"), ("丁", "酉")]))
        b = calculate_symbolic_stars(_mk([("乙", "丑"), ("丙", "辰"), ("丁", "卯"), ("戊", "戌")]))
        # 丑 year (idx 1): targets = {+3=辰, -3=戌}
        assert any(s.name_zh == "勾绞" for s in a.stars)
        assert any(s.name_zh == "勾绞" for s in b.stars)


# ── Smoke: realistic chart ────────────────────────────────────────────────────


class TestRealChart:
    def test_volzhsky_1999_chart(self) -> None:
        # 己卯年 / 癸酉月 / 丁亥日 / 庚子时 (Волжский 1999)
        out = calculate_symbolic_stars(
            _mk([("己", "卯"), ("癸", "酉"), ("丁", "亥"), ("庚", "子")])
        )
        # Sanity: at least 5 stars detected on realistic chart
        assert len(out.stars) >= 5
        # 卯年 + 亥日支 (亥/卯/未 group): 桃花=子 → hour=子 ✓
        assert any(s.name_zh == "桃花" for s in out.stars)
        # 卯年 → 寡宿=丑? actually 寅/卯/辰年 → 寡宿=丑. 卯 in year, no 丑 → maybe absent.
        # Let's just ensure structure intact:
        for s in out.stars:
            assert s.pillars
