"""Ten Gods (十神) mapping tests."""

from typing import ClassVar

from calculator.models import Pillar, Stem
from calculator.ten_gods import chart_ten_gods, ten_god

# ── Helpers ───────────────────────────────────────────────────────────────────


def _s(c: str) -> Stem:
    return c  # type: ignore[return-value]


# ── Full Ten Gods from 甲 (Yang Wood) DM ─────────────────────────────────────
# Reference: each of the 9 non-DM stems produces a distinct ten god


class TestTenGodsFromJia:
    DM: Stem = _s("甲")

    def test_yi_jiecai(self) -> None:
        # Same element (Wood), different polarity
        assert ten_god(self.DM, _s("乙")) == "劫财"

    def test_bing_shishen(self) -> None:
        # 甲 generates Fire, same polarity
        assert ten_god(self.DM, _s("丙")) == "食神"

    def test_ding_shangguan(self) -> None:
        # 甲 generates Fire, different polarity
        assert ten_god(self.DM, _s("丁")) == "伤官"

    def test_wu_piancai(self) -> None:
        # 甲 controls Earth, same polarity
        assert ten_god(self.DM, _s("戊")) == "偏财"

    def test_ji_zhengcai(self) -> None:
        # 甲 controls Earth, different polarity
        assert ten_god(self.DM, _s("己")) == "正财"

    def test_geng_qisha(self) -> None:
        # Metal controls 甲, same polarity
        assert ten_god(self.DM, _s("庚")) == "七杀"

    def test_xin_zhengguan(self) -> None:
        # Metal controls 甲, different polarity
        assert ten_god(self.DM, _s("辛")) == "正官"

    def test_ren_pianyin(self) -> None:
        # Water generates 甲, same polarity
        assert ten_god(self.DM, _s("壬")) == "偏印"

    def test_gui_zhengyin(self) -> None:
        # Water generates 甲, different polarity
        assert ten_god(self.DM, _s("癸")) == "正印"

    def test_jia_bisheng(self) -> None:
        # Same element, same polarity
        assert ten_god(self.DM, _s("甲")) == "比肩"


# ── Full Ten Gods from 丁 (Yin Fire) DM ──────────────────────────────────────
# User's Day Master — all 9 stems verified


class TestTenGodsFromDing:
    DM: Stem = _s("丁")

    def test_bing_jiecai(self) -> None:
        assert ten_god(self.DM, _s("丙")) == "劫财"

    def test_ji_shishen(self) -> None:
        assert ten_god(self.DM, _s("己")) == "食神"

    def test_wu_shangguan(self) -> None:
        assert ten_god(self.DM, _s("戊")) == "伤官"

    def test_xin_piancai(self) -> None:
        # 丁 controls Metal, same polarity (both Yin)
        assert ten_god(self.DM, _s("辛")) == "偏财"

    def test_geng_zhengcai(self) -> None:
        assert ten_god(self.DM, _s("庚")) == "正财"

    def test_gui_qisha(self) -> None:
        # Water controls Fire, same polarity (both Yin)
        assert ten_god(self.DM, _s("癸")) == "七杀"

    def test_ren_zhengguan(self) -> None:
        assert ten_god(self.DM, _s("壬")) == "正官"

    def test_yi_pianyin(self) -> None:
        # Wood generates Fire, same polarity (both Yin)
        assert ten_god(self.DM, _s("乙")) == "偏印"

    def test_jia_zhengyin(self) -> None:
        assert ten_god(self.DM, _s("甲")) == "正印"

    def test_ding_bisheng(self) -> None:
        assert ten_god(self.DM, _s("丁")) == "比肩"


# ── Symmetry: all 60 pairs produce one of 10 gods ────────────────────────────

_ALL_TEN_GODS = {"比肩", "劫财", "食神", "伤官", "偏财", "正财", "七杀", "正官", "偏印", "正印"}
_STEMS = ["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]


class TestAllPairsValid:
    def test_every_pair_returns_valid_ten_god(self) -> None:
        for dm in _STEMS:
            for target in _STEMS:
                result = ten_god(_s(dm), _s(target))
                assert result in _ALL_TEN_GODS, f"{dm}→{target} gave {result!r}"


# ── chart_ten_gods ────────────────────────────────────────────────────────────
# User's chart: 己卯 / 癸酉 / 丁卯 / 辛亥, DM = 丁


class TestChartTenGods:
    _PILLARS: ClassVar[list[Pillar]] = [
        Pillar(stem="己", branch="卯", name="year"),
        Pillar(stem="癸", branch="酉", name="month"),
        Pillar(stem="丁", branch="卯", name="day"),
        Pillar(stem="辛", branch="亥", name="hour"),
    ]
    _HIDDEN: ClassVar[dict[str, list[Stem]]] = {
        "year": ["乙"],  # 卯 → 乙
        "month": ["辛"],  # 酉 → 辛
        "day": ["乙"],  # 卯 → 乙
        "hour": ["壬", "甲"],  # 亥 → 壬, 甲
    }

    def test_keys(self) -> None:
        result = chart_ten_gods(self._PILLARS, self._HIDDEN)
        assert set(result.keys()) == {"year", "month", "day", "hour"}

    def test_year_stem_ji_is_shishen(self) -> None:
        result = chart_ten_gods(self._PILLARS, self._HIDDEN)
        assert result["year"][0] == "食神"

    def test_year_hidden_yi_is_pianyin(self) -> None:
        result = chart_ten_gods(self._PILLARS, self._HIDDEN)
        assert result["year"][1] == "偏印"

    def test_month_stem_gui_is_qisha(self) -> None:
        result = chart_ten_gods(self._PILLARS, self._HIDDEN)
        assert result["month"][0] == "七杀"

    def test_month_hidden_xin_is_piancai(self) -> None:
        result = chart_ten_gods(self._PILLARS, self._HIDDEN)
        assert result["month"][1] == "偏财"

    def test_day_stem_is_rimu(self) -> None:
        result = chart_ten_gods(self._PILLARS, self._HIDDEN)
        assert result["day"][0] == "日主"

    def test_day_hidden_yi_is_pianyin(self) -> None:
        result = chart_ten_gods(self._PILLARS, self._HIDDEN)
        assert result["day"][1] == "偏印"

    def test_hour_stem_xin_is_piancai(self) -> None:
        result = chart_ten_gods(self._PILLARS, self._HIDDEN)
        assert result["hour"][0] == "偏财"

    def test_hour_hidden_ren_is_zhengguan(self) -> None:
        result = chart_ten_gods(self._PILLARS, self._HIDDEN)
        assert result["hour"][1] == "正官"

    def test_hour_hidden_jia_is_zhengyin(self) -> None:
        result = chart_ten_gods(self._PILLARS, self._HIDDEN)
        assert result["hour"][2] == "正印"

    def test_each_pillar_has_stem_plus_hidden(self) -> None:
        result = chart_ten_gods(self._PILLARS, self._HIDDEN)
        assert len(result["year"]) == 2  # 己 + 乙
        assert len(result["month"]) == 2  # 癸 + 辛
        assert len(result["day"]) == 2  # DM + 乙
        assert len(result["hour"]) == 3  # 辛 + 壬 + 甲
