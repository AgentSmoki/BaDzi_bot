"""Four Pillars generation tests.

Reference chart (user-verified against professional Ba Zi calculator):
  Birth : 1999-09-12 23:55 Moscow Summer Time (UTC+4)
  City  : Волжский (lon=44.77°E, lat=48.79°N)
  Year  : 己卯
  Month : 癸酉  (after 白露 ≈ Sep 8)
  Day   : 丁卯  (甲子 reference = 2000-01-07)
  Hour  : 辛亥  (亥時 TST≈22:57, Late Rat default)
"""

from datetime import datetime

from calculator.models import ChartInput, Pillar
from calculator.pillars import calculate_pillars

# ── Reference fixture ─────────────────────────────────────────────────────────

_VOLZHSKY = ChartInput(
    birth_datetime=datetime(1999, 9, 12, 23, 55, 0),
    latitude=48.79,
    longitude=44.77,
    tz_offset=4.0,  # Moscow Summer Time (UTC+4), Sep 1999
)


class TestFourPillarsVolzhsky1999:
    def test_returns_four_pillars(self) -> None:
        assert len(calculate_pillars(_VOLZHSKY)) == 4

    def test_pillar_names(self) -> None:
        assert [p.name for p in calculate_pillars(_VOLZHSKY)] == ["year", "month", "day", "hour"]

    def test_year_pillar_ji_mao(self) -> None:
        year = calculate_pillars(_VOLZHSKY)[0]
        assert year.stem == "己"
        assert year.branch == "卯"

    def test_month_pillar_gui_you(self) -> None:
        month = calculate_pillars(_VOLZHSKY)[1]
        assert month.stem == "癸"
        assert month.branch == "酉"

    def test_day_pillar_ding_mao(self) -> None:
        day = calculate_pillars(_VOLZHSKY)[2]
        assert day.stem == "丁"
        assert day.branch == "卯"

    def test_hour_pillar_xin_hai(self) -> None:
        hour = calculate_pillars(_VOLZHSKY)[3]
        assert hour.stem == "辛"
        assert hour.branch == "亥"


class TestYearBoundary:
    def test_before_liqian_uses_previous_year(self) -> None:
        # Jan 20, 1999 is before 立春 1999 → year 戊寅 (1998)
        inp = ChartInput(
            birth_datetime=datetime(1999, 1, 20, 12, 0, 0),
            latitude=48.79,
            longitude=44.77,
            tz_offset=3.0,
        )
        year = calculate_pillars(inp)[0]
        assert year.stem == "戊"
        assert year.branch == "寅"

    def test_after_liqian_uses_current_year(self) -> None:
        # Feb 10, 1999 is after 立春 1999 (≈ Feb 4) → year 己卯
        inp = ChartInput(
            birth_datetime=datetime(1999, 2, 10, 12, 0, 0),
            latitude=48.79,
            longitude=44.77,
            tz_offset=3.0,
        )
        year = calculate_pillars(inp)[0]
        assert year.stem == "己"
        assert year.branch == "卯"


class TestMonthBoundary:
    def test_before_bailu_in_shen_month(self) -> None:
        # Sep 5, 1999 is before 白露 (≈ Sep 8) → 申 month
        inp = ChartInput(
            birth_datetime=datetime(1999, 9, 5, 12, 0, 0),
            latitude=48.79,
            longitude=44.77,
            tz_offset=4.0,
        )
        assert calculate_pillars(inp)[1].branch == "申"

    def test_after_bailu_in_you_month(self) -> None:
        assert calculate_pillars(_VOLZHSKY)[1].branch == "酉"


class TestEarlyLatRat:
    def test_late_rat_advances_day(self) -> None:
        # Local 00:02 Sep 12 → TST 23:04 Sep 11 → late rat → day = Sep 12
        # Local 01:30 Sep 12 → TST 00:32 Sep 12 → normal Sep 12
        # Both should give the same day pillar (Sep 12)
        late = ChartInput(
            birth_datetime=datetime(1999, 9, 12, 0, 2, 0),
            latitude=48.79,
            longitude=44.77,
            tz_offset=4.0,
            early_rat=False,
        )
        normal = ChartInput(
            birth_datetime=datetime(1999, 9, 12, 1, 30, 0),
            latitude=48.79,
            longitude=44.77,
            tz_offset=4.0,
        )
        late_day = calculate_pillars(late)[2]
        normal_day = calculate_pillars(normal)[2]
        assert late_day.stem == normal_day.stem
        assert late_day.branch == normal_day.branch

    def test_early_rat_keeps_same_day(self) -> None:
        # Local 00:02 Sep 12 → TST 23:04 Sep 11 → early rat → day stays Sep 11
        early = ChartInput(
            birth_datetime=datetime(1999, 9, 12, 0, 2, 0),
            latitude=48.79,
            longitude=44.77,
            tz_offset=4.0,
            early_rat=True,
        )
        same = ChartInput(
            birth_datetime=datetime(1999, 9, 11, 22, 0, 0),
            latitude=48.79,
            longitude=44.77,
            tz_offset=4.0,
            early_rat=True,
        )
        assert calculate_pillars(early)[2].branch == calculate_pillars(same)[2].branch

    def test_hour_branch_zi_at_local_0100(self) -> None:
        # Local 01:00 → TST 00:02 → 子時 (23:00-01:00 TST)
        inp = ChartInput(
            birth_datetime=datetime(1999, 9, 12, 1, 0, 0),
            latitude=48.79,
            longitude=44.77,
            tz_offset=4.0,
        )
        assert calculate_pillars(inp)[3].branch == "子"

    def test_hour_branch_hai_at_2355(self) -> None:
        assert calculate_pillars(_VOLZHSKY)[3].branch == "亥"

    def test_all_pillars_are_pillar_instances(self) -> None:
        for p in calculate_pillars(_VOLZHSKY):
            assert isinstance(p, Pillar)
