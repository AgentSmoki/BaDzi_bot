"""Tests for calculator/interactions.py — branch/stem interactions (合沖刑害破)."""

from __future__ import annotations

from calculator.interactions import calculate_interactions
from calculator.models import Pillar


def _mk(stem_branch_pairs: list[tuple[str, str]]) -> list[Pillar]:
    """Build 4 pillars from a list of (stem, branch) tuples in order Y/M/D/H."""
    names = ["year", "month", "day", "hour"]
    return [
        Pillar(stem=s, branch=b, name=n)  # type: ignore[arg-type]
        for (s, b), n in zip(stem_branch_pairs, names, strict=True)
    ]


# ── Empty / negative cases ────────────────────────────────────────────────────


class TestNoInteractions:
    def test_completely_inert_chart(self) -> None:
        # Pick stems and branches with no mutual interactions.
        out = calculate_interactions(_mk([("甲", "子"), ("甲", "子"), ("甲", "子"), ("甲", "子")]))
        # 甲甲 not in STEM_COMBINATIONS; 子子 not in any pair table; 子 self-punishment? no.
        assert out.stem_combinations == []
        assert out.branch_clashes == []
        assert out.six_harmonies == []
        assert out.three_harmonies == []
        assert out.half_harmonies == []
        assert out.three_punishments == []
        assert out.self_punishments == []
        assert out.six_harms == []
        assert out.six_breaks == []


# ── Stem combinations (五合) ──────────────────────────────────────────────────


class TestStemCombinations:
    def test_jia_ji_to_earth(self) -> None:
        out = calculate_interactions(_mk([("甲", "子"), ("己", "丑"), ("丙", "寅"), ("丁", "卯")]))
        assert len(out.stem_combinations) == 1
        c = out.stem_combinations[0]
        assert c.name == "甲己合土"
        assert c.transforms_to == "土"
        assert set(c.members) == {"甲", "己"}
        assert c.pillars == ["year", "month"]

    def test_bing_xin_to_water(self) -> None:
        out = calculate_interactions(_mk([("丙", "子"), ("壬", "丑"), ("辛", "寅"), ("丁", "卯")]))
        names = {c.name for c in out.stem_combinations}
        assert "丙辛合水" in names
        assert "丁壬合木" in names

    def test_no_combination_with_doubled_stem(self) -> None:
        # Two 甲 stems alone do not produce 甲己合
        out = calculate_interactions(_mk([("甲", "子"), ("甲", "丑"), ("乙", "寅"), ("丙", "卯")]))
        assert out.stem_combinations == []


# ── Branch clashes (六沖) ─────────────────────────────────────────────────────


class TestBranchClashes:
    def test_zi_wu_clash(self) -> None:
        out = calculate_interactions(_mk([("甲", "子"), ("乙", "午"), ("丙", "寅"), ("丁", "卯")]))
        assert len(out.branch_clashes) == 1
        clash = out.branch_clashes[0]
        assert clash.name == "子午相沖"
        assert clash.transforms_to is None
        assert set(clash.members) == {"子", "午"}

    def test_chen_xu_clash(self) -> None:
        out = calculate_interactions(_mk([("甲", "辰"), ("乙", "戌"), ("丙", "寅"), ("丁", "卯")]))
        assert any(c.name == "辰戌相沖" for c in out.branch_clashes)


# ── Six harmonies (六合) ──────────────────────────────────────────────────────


class TestSixHarmonies:
    def test_zi_chou_to_earth(self) -> None:
        out = calculate_interactions(_mk([("甲", "子"), ("乙", "丑"), ("丙", "寅"), ("丁", "卯")]))
        assert len(out.six_harmonies) == 1
        h = out.six_harmonies[0]
        assert h.name == "子丑合土"
        assert h.transforms_to == "土"

    def test_yin_hai_appears_with_six_break_simultaneously(self) -> None:
        # 寅亥 is BOTH 六合木 and 六破 — both should appear.
        out = calculate_interactions(_mk([("甲", "寅"), ("乙", "亥"), ("丙", "卯"), ("丁", "辰")]))
        assert any(h.name == "寅亥合木" for h in out.six_harmonies)
        assert any(b.name == "寅亥相破" for b in out.six_breaks)


# ── Three harmonies (三合) ────────────────────────────────────────────────────


class TestThreeHarmonies:
    def test_shen_zi_chen_to_water(self) -> None:
        out = calculate_interactions(_mk([("甲", "申"), ("乙", "子"), ("丙", "辰"), ("丁", "卯")]))
        assert len(out.three_harmonies) == 1
        t = out.three_harmonies[0]
        assert t.name == "申子辰三合水"
        assert t.transforms_to == "水"
        assert set(t.members) == {"申", "子", "辰"}
        assert t.pillars == ["year", "month", "day"]

    def test_yin_wu_xu_to_fire(self) -> None:
        out = calculate_interactions(_mk([("甲", "寅"), ("乙", "午"), ("丙", "戌"), ("丁", "卯")]))
        assert any(t.name == "寅午戌三合火" for t in out.three_harmonies)


# ── Half harmonies (半合) ─────────────────────────────────────────────────────


class TestHalfHarmonies:
    def test_shen_zi_half_water(self) -> None:
        out = calculate_interactions(_mk([("甲", "申"), ("乙", "子"), ("丙", "卯"), ("丁", "巳")]))
        assert len(out.half_harmonies) == 1
        h = out.half_harmonies[0]
        assert h.name == "申子半合水"
        assert h.transforms_to == "水"

    def test_full_triad_suppresses_half_harmonies(self) -> None:
        # 申子辰 full triad — no 申子 / 子辰 half-harmonies should leak through.
        out = calculate_interactions(_mk([("甲", "申"), ("乙", "子"), ("丙", "辰"), ("丁", "卯")]))
        assert out.half_harmonies == []
        assert len(out.three_harmonies) == 1


# ── Punishments (三刑 / 自刑) ─────────────────────────────────────────────────


class TestPunishments:
    def test_yin_si_shen_three_punishment(self) -> None:
        out = calculate_interactions(_mk([("甲", "寅"), ("乙", "巳"), ("丙", "申"), ("丁", "卯")]))
        names = {p.name for p in out.three_punishments}
        assert "寅巳申无恩之刑" in names

    def test_zi_mao_pair_punishment(self) -> None:
        out = calculate_interactions(_mk([("甲", "子"), ("乙", "卯"), ("丙", "寅"), ("丁", "辰")]))
        names = {p.name for p in out.three_punishments}
        assert "子卯无礼之刑" in names

    def test_self_punishment_chen_chen(self) -> None:
        out = calculate_interactions(_mk([("甲", "辰"), ("乙", "辰"), ("丙", "寅"), ("丁", "卯")]))
        assert len(out.self_punishments) == 1
        assert out.self_punishments[0].name == "辰辰自刑"
        assert out.self_punishments[0].pillars == ["year", "month"]

    def test_single_chen_no_self_punishment(self) -> None:
        out = calculate_interactions(_mk([("甲", "辰"), ("乙", "丑"), ("丙", "寅"), ("丁", "卯")]))
        assert out.self_punishments == []


# ── Harms and breaks (六害 / 六破) ────────────────────────────────────────────


class TestHarmsAndBreaks:
    def test_zi_wei_harm(self) -> None:
        out = calculate_interactions(_mk([("甲", "子"), ("乙", "未"), ("丙", "寅"), ("丁", "卯")]))
        assert any(h.name == "子未相害" for h in out.six_harms)

    def test_chou_wu_harm(self) -> None:
        out = calculate_interactions(_mk([("甲", "丑"), ("乙", "午"), ("丙", "寅"), ("丁", "卯")]))
        assert any(h.name == "丑午相害" for h in out.six_harms)

    def test_zi_you_break(self) -> None:
        out = calculate_interactions(_mk([("甲", "子"), ("乙", "酉"), ("丙", "寅"), ("丁", "卯")]))
        assert any(b.name == "子酉相破" for b in out.six_breaks)


# ── Pillar tracking ───────────────────────────────────────────────────────────


class TestPillarTracking:
    def test_pillars_in_natural_order(self) -> None:
        # 甲 in hour, 己 in year — pillars list should be ["year", "hour"]
        out = calculate_interactions(_mk([("己", "丑"), ("乙", "未"), ("丙", "寅"), ("甲", "卯")]))
        assert out.stem_combinations[0].pillars == ["year", "hour"]

    def test_repeated_branch_aggregates_pillars(self) -> None:
        # 子 in year and day; 丑 in month → 子丑合 reported once with all 3 pillars.
        out = calculate_interactions(_mk([("甲", "子"), ("乙", "丑"), ("丙", "子"), ("丁", "卯")]))
        harmonies = [h for h in out.six_harmonies if h.name == "子丑合土"]
        assert len(harmonies) == 1
        assert harmonies[0].pillars == ["year", "month", "day"]


# ── Smoke test: realistic chart (Волжский 1999) ──────────────────────────────


class TestRealChart:
    def test_volzhsky_chart_returns_structured_output(self) -> None:
        # 己卯 / 癸酉 / 丁亥 / 庚子 — actual reference chart (rough).
        out = calculate_interactions(_mk([("己", "卯"), ("癸", "酉"), ("丁", "亥"), ("庚", "子")]))
        # 卯酉相沖 expected
        assert any(c.name == "卯酉相沖" for c in out.branch_clashes)
        # 戊癸合火 NO (no 戊). 甲己 NO (no 甲). So no stem combos.
        # Output structure intact for all 9 fields.
        assert isinstance(out.stem_combinations, list)
        assert isinstance(out.branch_clashes, list)
        assert isinstance(out.six_harmonies, list)
        assert isinstance(out.three_harmonies, list)
        assert isinstance(out.half_harmonies, list)
        assert isinstance(out.three_punishments, list)
        assert isinstance(out.self_punishments, list)
        assert isinstance(out.six_harms, list)
        assert isinstance(out.six_breaks, list)
