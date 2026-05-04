"""Four Pillars generation tests.

Reference chart: 1999-09-12 12:00 Beijing time (UTC+8), lon=116.39°E lat=39.91°N
  Year  : 己卯
  Month : 癸酉  (after 白露 ~Sep 8)
  Day   : 丁亥
  Hour  : 丙午  (noon = 午时, TST ≈ 11:49)

Cross-verified with astronomical reference: Swiss Ephemeris sun longitude.
"""

from datetime import datetime

from calculator.models import ChartInput, Pillar
from calculator.pillars import calculate_pillars

# ── Reference fixture ─────────────────────────────────────────────────────────

_BEIJING_INPUT = ChartInput(
    birth_datetime=datetime(1999, 9, 12, 12, 0, 0),
    latitude=39.91,
    longitude=116.39,
    tz_offset=8.0,
)


class TestFourPillarsBeijing1999:
    def test_returns_four_pillars(self) -> None:
        pillars = calculate_pillars(_BEIJING_INPUT)
        assert len(pillars) == 4

    def test_pillar_names(self) -> None:
        pillars = calculate_pillars(_BEIJING_INPUT)
        names = [p.name for p in pillars]
        assert names == ["year", "month", "day", "hour"]

    def test_year_pillar_ji_mao(self) -> None:
        year = calculate_pillars(_BEIJING_INPUT)[0]
        assert year.stem == "己"
        assert year.branch == "卯"

    def test_month_pillar_gui_you(self) -> None:
        month = calculate_pillars(_BEIJING_INPUT)[1]
        assert month.stem == "癸"
        assert month.branch == "酉"

    def test_day_pillar_ding_hai(self) -> None:
        day = calculate_pillars(_BEIJING_INPUT)[2]
        assert day.stem == "丁"
        assert day.branch == "亥"

    def test_hour_pillar_bing_wu(self) -> None:
        hour = calculate_pillars(_BEIJING_INPUT)[3]
        assert hour.stem == "丙"
        assert hour.branch == "午"


class TestYearBoundary:
    def test_before_liqian_uses_previous_year(self) -> None:
        # Jan 20, 1999 is before 立春 1999 → year should be 戊寅 (1998)
        inp = ChartInput(
            birth_datetime=datetime(1999, 1, 20, 12, 0, 0),
            latitude=39.91,
            longitude=116.39,
            tz_offset=8.0,
        )
        year = calculate_pillars(inp)[0]
        assert year.stem == "戊"
        assert year.branch == "寅"

    def test_after_liqian_uses_current_year(self) -> None:
        # Feb 10, 1999 is after 立春 1999 (≈ Feb 4) → year 己卯
        inp = ChartInput(
            birth_datetime=datetime(1999, 2, 10, 12, 0, 0),
            latitude=39.91,
            longitude=116.39,
            tz_offset=8.0,
        )
        year = calculate_pillars(inp)[0]
        assert year.stem == "己"
        assert year.branch == "卯"


class TestMonthBoundary:
    def test_before_bailu_in_shen_month(self) -> None:
        # Sep 5, 1999 is before 白露 (≈ Sep 8) → 申 month
        inp = ChartInput(
            birth_datetime=datetime(1999, 9, 5, 12, 0, 0),
            latitude=39.91,
            longitude=116.39,
            tz_offset=8.0,
        )
        month = calculate_pillars(inp)[1]
        assert month.branch == "申"

    def test_after_bailu_in_you_month(self) -> None:
        month = calculate_pillars(_BEIJING_INPUT)[1]
        assert month.branch == "酉"


class TestEarlyLatRat:
    def test_late_rat_23h_next_day(self) -> None:
        # 23:30 TST with late rat (default) → day pillar of NEXT day
        base = ChartInput(
            birth_datetime=datetime(1999, 9, 12, 23, 30, 0),
            latitude=39.91,
            longitude=116.39,
            tz_offset=8.0,
            early_rat=False,
        )
        base_day = calculate_pillars(base)[2]

        next_day = ChartInput(
            birth_datetime=datetime(1999, 9, 13, 0, 30, 0),
            latitude=39.91,
            longitude=116.39,
            tz_offset=8.0,
        )
        next_d = calculate_pillars(next_day)[2]
        assert base_day.stem == next_d.stem
        assert base_day.branch == next_d.branch

    def test_early_rat_23h_same_day(self) -> None:
        # 23:30 TST with early rat → same day as 22:00
        base = ChartInput(
            birth_datetime=datetime(1999, 9, 12, 23, 30, 0),
            latitude=39.91,
            longitude=116.39,
            tz_offset=8.0,
            early_rat=True,
        )
        same = ChartInput(
            birth_datetime=datetime(1999, 9, 12, 22, 0, 0),
            latitude=39.91,
            longitude=116.39,
            tz_offset=8.0,
            early_rat=True,
        )
        assert calculate_pillars(base)[2].branch == calculate_pillars(same)[2].branch

    def test_hour_branch_midnight_is_zi(self) -> None:
        inp = ChartInput(
            birth_datetime=datetime(1999, 9, 12, 0, 0, 0),
            latitude=39.91,
            longitude=116.39,
            tz_offset=8.0,
        )
        assert calculate_pillars(inp)[3].branch == "子"

    def test_hour_branch_noon_is_wu(self) -> None:
        assert calculate_pillars(_BEIJING_INPUT)[3].branch == "午"

    def test_all_pillars_are_pillar_instances(self) -> None:
        for p in calculate_pillars(_BEIJING_INPUT):
            assert isinstance(p, Pillar)
