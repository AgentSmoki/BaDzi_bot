"""Day Master strength and useful/harmful god tests."""

from calculator.day_master import (
    dm_element,
    dm_strength_score,
    element_balance,
    is_strong_dm,
    ji_shen,
    seasonal_state,
    yong_shen,
)
from calculator.models import Pillar, Stem

# ── Fixtures ──────────────────────────────────────────────────────────────────

# User's chart: 己卯 / 癸酉 / 丁卯 / 辛亥  (DM = 丁, Yin Fire)
_PILLARS: list[Pillar] = [
    Pillar(stem="己", branch="卯", name="year"),
    Pillar(stem="癸", branch="酉", name="month"),
    Pillar(stem="丁", branch="卯", name="day"),
    Pillar(stem="辛", branch="亥", name="hour"),
]
_HIDDEN: dict[str, list[Stem]] = {
    "year": ["乙"],
    "month": ["辛"],
    "day": ["乙"],
    "hour": ["壬", "甲"],
}


# ── dm_element ────────────────────────────────────────────────────────────────


class TestDmElement:
    def test_jia_yi_are_wood(self) -> None:
        assert dm_element("甲") == "木"
        assert dm_element("乙") == "木"

    def test_bing_ding_are_fire(self) -> None:
        assert dm_element("丙") == "火"
        assert dm_element("丁") == "火"

    def test_wu_ji_are_earth(self) -> None:
        assert dm_element("戊") == "土"
        assert dm_element("己") == "土"

    def test_geng_xin_are_metal(self) -> None:
        assert dm_element("庚") == "金"
        assert dm_element("辛") == "金"

    def test_ren_gui_are_water(self) -> None:
        assert dm_element("壬") == "水"
        assert dm_element("癸") == "水"


# ── seasonal_state ────────────────────────────────────────────────────────────


class TestSeasonalState:
    def test_fire_dm_in_summer_is_wang(self) -> None:
        # 午 = Fire season → 丁 (Fire) is 旺
        assert seasonal_state("丁", "午") == "旺"

    def test_fire_dm_in_spring_is_xiang(self) -> None:
        # 寅 = Wood season → Wood generates Fire → 相
        assert seasonal_state("丁", "寅") == "相"

    def test_fire_dm_in_late_summer_is_xiu(self) -> None:
        # 未 = Earth season → Fire generates Earth → 休
        assert seasonal_state("丁", "未") == "休"

    def test_fire_dm_in_autumn_is_qiu(self) -> None:
        # 酉 = Metal season → Fire controls Metal → 囚 (wasted effort)
        assert seasonal_state("丁", "酉") == "囚"

    def test_fire_dm_in_winter_is_si(self) -> None:
        # 子 = Water season → Water controls Fire → 死
        assert seasonal_state("丁", "子") == "死"

    def test_wood_dm_in_spring_is_wang(self) -> None:
        assert seasonal_state("甲", "卯") == "旺"

    def test_wood_dm_in_winter_is_xiang(self) -> None:
        # 亥 = Water season → Water generates Wood → 相
        assert seasonal_state("甲", "亥") == "相"

    def test_water_dm_in_autumn_is_xiang(self) -> None:
        # 申 = Metal season → Metal generates Water → 相
        assert seasonal_state("壬", "申") == "相"

    def test_metal_dm_in_summer_is_si(self) -> None:
        # 午 = Fire season → Fire controls Metal → 死
        assert seasonal_state("庚", "午") == "死"

    def test_earth_dm_in_transitional_is_wang(self) -> None:
        # 辰 = Earth season → 戊 (Earth) is 旺
        assert seasonal_state("戊", "辰") == "旺"

    def test_user_chart_ding_in_you_is_qiu(self) -> None:
        # 酉月 = Metal, 丁 controls Metal → 囚
        assert seasonal_state("丁", "酉") == "囚"


# ── element_balance ───────────────────────────────────────────────────────────


class TestElementBalance:
    def test_keys_are_five_elements(self) -> None:
        bal = element_balance(_PILLARS, _HIDDEN)
        assert set(bal.keys()) == {"木", "火", "土", "金", "水"}

    def test_sums_to_one(self) -> None:
        bal = element_balance(_PILLARS, _HIDDEN)
        assert abs(sum(bal.values()) - 1.0) < 1e-9

    def test_fire_is_weakest_in_user_chart(self) -> None:
        # 丁 is the only Fire stem in the chart
        bal = element_balance(_PILLARS, _HIDDEN)
        assert bal["火"] == min(bal.values())

    def test_wood_is_present_from_hidden_stems(self) -> None:
        # 卯x2 (乙,乙) and 亥(甲) give Wood presence
        bal = element_balance(_PILLARS, _HIDDEN)
        assert bal["木"] > 0

    def test_empty_pillars_returns_zeros(self) -> None:
        # Covers the zero-total guard (day_master.py line 116)
        bal = element_balance([], {})
        assert set(bal.keys()) == {"木", "火", "土", "金", "水"}
        assert all(v == 0.0 for v in bal.values())


# ── dm_strength_score ─────────────────────────────────────────────────────────


class TestDmStrengthScore:
    def test_user_chart_ding_is_weak(self) -> None:
        score = dm_strength_score(_PILLARS, _HIDDEN)
        assert score < 0  # 丁 in 酉月 with heavy Metal/Water pressure = weak

    def test_strong_dm_chart(self) -> None:
        # 甲 DM in spring (寅月), surrounded by Wood and Water
        pillars = [
            Pillar(stem="甲", branch="寅", name="year"),
            Pillar(stem="壬", branch="寅", name="month"),
            Pillar(stem="甲", branch="子", name="day"),
            Pillar(stem="乙", branch="卯", name="hour"),
        ]
        hidden: dict[str, list[Stem]] = {
            "year": ["甲", "丙", "戊"],
            "month": ["甲", "丙", "戊"],
            "day": ["癸"],
            "hour": ["乙"],
        }
        score = dm_strength_score(pillars, hidden)
        assert score > 0

    def test_score_is_float(self) -> None:
        score = dm_strength_score(_PILLARS, _HIDDEN)
        assert isinstance(score, float)


# ── is_strong_dm ──────────────────────────────────────────────────────────────


class TestIsStrongDm:
    def test_positive_score_is_strong(self) -> None:
        assert is_strong_dm(1.0) is True

    def test_zero_is_not_strong(self) -> None:
        assert is_strong_dm(0.0) is False

    def test_negative_is_not_strong(self) -> None:
        assert is_strong_dm(-3.5) is False

    def test_user_chart_is_weak(self) -> None:
        score = dm_strength_score(_PILLARS, _HIDDEN)
        assert is_strong_dm(score) is False


# ── yong_shen / ji_shen ───────────────────────────────────────────────────────


class TestYongShenJiShen:
    def test_weak_dm_yong_shen_are_support_gods(self) -> None:
        ys = yong_shen(is_strong=False)
        assert "比肩" in ys
        assert "劫财" in ys
        assert "正印" in ys
        assert "偏印" in ys

    def test_weak_dm_yong_shen_excludes_drain_gods(self) -> None:
        ys = yong_shen(is_strong=False)
        assert "七杀" not in ys
        assert "正官" not in ys
        assert "正财" not in ys

    def test_strong_dm_yong_shen_are_drain_gods(self) -> None:
        ys = yong_shen(is_strong=True)
        assert "食神" in ys
        assert "七杀" in ys
        assert "正财" in ys

    def test_strong_dm_yong_shen_excludes_support_gods(self) -> None:
        ys = yong_shen(is_strong=True)
        assert "比肩" not in ys
        assert "正印" not in ys

    def test_ji_shen_is_complement_of_yong_shen(self) -> None:
        all_gods = {
            "比肩",
            "劫财",
            "食神",
            "伤官",
            "正财",
            "偏财",
            "正官",
            "七杀",
            "正印",
            "偏印",
        }
        ys = set(yong_shen(is_strong=False))
        js = set(ji_shen(is_strong=False))
        assert ys | js == all_gods
        assert ys & js == set()

    def test_user_chart_yong_shen(self) -> None:
        score = dm_strength_score(_PILLARS, _HIDDEN)
        strong = is_strong_dm(score)
        ys = yong_shen(strong)
        assert "偏印" in ys  # 乙木(偏印) in 卯 = helpful for weak 丁
