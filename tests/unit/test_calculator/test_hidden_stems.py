"""Hidden stems (藏干) tests -- all 12 branches x 3 schools."""

from typing import ClassVar

from calculator.hidden_stems import chart_hidden_stems, hidden_stems
from calculator.models import BRANCHES, Branch, HiddenStemsSchool, Pillar

# ── Helpers ───────────────────────────────────────────────────────────────────


def _b(s: str) -> Branch:
    assert s in BRANCHES
    return s  # type: ignore[return-value]


# ── Traditional school — all 12 branches ─────────────────────────────────────


class TestTraditional:
    S: HiddenStemsSchool = "traditional"

    def test_zi(self) -> None:
        assert hidden_stems(_b("子"), self.S) == ["癸"]

    def test_chou(self) -> None:
        assert hidden_stems(_b("丑"), self.S) == ["己", "癸", "辛"]

    def test_yin(self) -> None:
        assert hidden_stems(_b("寅"), self.S) == ["甲", "丙", "戊"]

    def test_mao(self) -> None:
        assert hidden_stems(_b("卯"), self.S) == ["乙"]

    def test_chen(self) -> None:
        assert hidden_stems(_b("辰"), self.S) == ["戊", "乙", "癸"]

    def test_si(self) -> None:
        assert hidden_stems(_b("巳"), self.S) == ["丙", "庚", "戊"]

    def test_wu(self) -> None:
        assert hidden_stems(_b("午"), self.S) == ["丁", "己"]

    def test_wei(self) -> None:
        assert hidden_stems(_b("未"), self.S) == ["己", "丁", "乙"]

    def test_shen(self) -> None:
        assert hidden_stems(_b("申"), self.S) == ["庚", "壬", "戊"]

    def test_you(self) -> None:
        assert hidden_stems(_b("酉"), self.S) == ["辛"]

    def test_xu(self) -> None:
        assert hidden_stems(_b("戌"), self.S) == ["戊", "辛", "丁"]

    def test_hai(self) -> None:
        assert hidden_stems(_b("亥"), self.S) == ["壬", "甲"]


# ── Modern school — spot-check differences ────────────────────────────────────


class TestModern:
    S: HiddenStemsSchool = "modern"

    def test_zi_has_ren_gui(self) -> None:
        # Key difference vs traditional: 子 = 壬, 癸 (not just 癸)
        assert hidden_stems(_b("子"), self.S) == ["壬", "癸"]

    def test_wu_same_as_traditional(self) -> None:
        assert hidden_stems(_b("午"), self.S) == ["丁", "己"]

    def test_yin_reordered(self) -> None:
        # Modern reorders: 甲, 戊, 丙 instead of 甲, 丙, 戊
        assert hidden_stems(_b("寅"), self.S) == ["甲", "戊", "丙"]

    def test_shen_reordered(self) -> None:
        assert hidden_stems(_b("申"), self.S) == ["庚", "戊", "壬"]

    def test_mao_unchanged(self) -> None:
        assert hidden_stems(_b("卯"), self.S) == ["乙"]

    def test_you_unchanged(self) -> None:
        assert hidden_stems(_b("酉"), self.S) == ["辛"]


# ── Ken Lai school — spot-check differences ───────────────────────────────────


class TestKenLai:
    S: HiddenStemsSchool = "ken_lai"

    def test_wu_only_ding(self) -> None:
        # Key difference: 午 = 丁 only (no 己)
        assert hidden_stems(_b("午"), self.S) == ["丁"]

    def test_zi_same_as_traditional(self) -> None:
        assert hidden_stems(_b("子"), self.S) == ["癸"]

    def test_yin_same_as_traditional(self) -> None:
        assert hidden_stems(_b("寅"), self.S) == ["甲", "丙", "戊"]

    def test_hai_same_as_traditional(self) -> None:
        assert hidden_stems(_b("亥"), self.S) == ["壬", "甲"]


# ── Cross-school differences ─────────────────────────────────────────────────


class TestCrossSchool:
    def test_zi_differs_traditional_vs_modern(self) -> None:
        t = hidden_stems(_b("子"), "traditional")
        m = hidden_stems(_b("子"), "modern")
        assert t != m
        assert "壬" not in t
        assert "壬" in m

    def test_wu_differs_traditional_vs_ken_lai(self) -> None:
        t = hidden_stems(_b("午"), "traditional")
        k = hidden_stems(_b("午"), "ken_lai")
        assert t != k
        assert "己" in t
        assert "己" not in k

    def test_wu_traditional_vs_modern_same(self) -> None:
        assert hidden_stems(_b("午"), "traditional") == hidden_stems(_b("午"), "modern")


# ── Return types ──────────────────────────────────────────────────────────────


class TestReturnTypes:
    def test_returns_list(self) -> None:
        result = hidden_stems(_b("子"), "traditional")
        assert isinstance(result, list)

    def test_all_branches_return_nonempty(self) -> None:
        for branch in BRANCHES:
            result = hidden_stems(branch, "traditional")  # type: ignore[arg-type]
            assert len(result) >= 1, f"Empty hidden stems for {branch}"


# ── chart_hidden_stems ────────────────────────────────────────────────────────


class TestChartHiddenStems:
    _PILLARS: ClassVar[list[Pillar]] = [
        Pillar(stem="己", branch="卯", name="year"),
        Pillar(stem="癸", branch="酉", name="month"),
        Pillar(stem="丁", branch="卯", name="day"),
        Pillar(stem="辛", branch="亥", name="hour"),
    ]

    def test_keys_match_pillar_names(self) -> None:
        result = chart_hidden_stems(self._PILLARS, "traditional")
        assert set(result.keys()) == {"year", "month", "day", "hour"}

    def test_year_branch_mao(self) -> None:
        result = chart_hidden_stems(self._PILLARS, "traditional")
        assert result["year"] == ["乙"]  # 卯 → 乙

    def test_month_branch_you(self) -> None:
        result = chart_hidden_stems(self._PILLARS, "traditional")
        assert result["month"] == ["辛"]  # 酉 → 辛

    def test_hour_branch_hai(self) -> None:
        result = chart_hidden_stems(self._PILLARS, "traditional")
        assert result["hour"] == ["壬", "甲"]  # 亥 → 壬, 甲

    def test_school_propagates(self) -> None:
        # With modern school, if pillar has 子, it should return 壬, 癸
        pillars_with_zi = [
            Pillar(stem="甲", branch="子", name="year"),
            Pillar(stem="乙", branch="丑", name="month"),
            Pillar(stem="丙", branch="寅", name="day"),
            Pillar(stem="丁", branch="卯", name="hour"),
        ]
        trad = chart_hidden_stems(pillars_with_zi, "traditional")
        modern = chart_hidden_stems(pillars_with_zi, "modern")
        assert trad["year"] == ["癸"]
        assert modern["year"] == ["壬", "癸"]
