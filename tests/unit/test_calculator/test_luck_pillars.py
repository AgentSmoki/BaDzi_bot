"""Luck Pillars (大運) tests.

Direction rules:
  Yang year + male   = forward (顺运)
  Yang year + female = backward (逆运)
  Yin year  + male   = backward (逆运)
  Yin year  + female = forward (顺运)

Reference pillars (60-cycle forward/backward):
  Chart 1 — Волжский 1999 (month 癸酉, 60-idx=9):
    forward  → 甲戌(10), 乙亥(11), 丙子(12) ...
    backward → 壬申(8),  辛未(7),  庚午(6)  ...

  Chart 2 — Новокузнецк 1997 (month 癸卯, 60-idx=39):
    forward  → 甲辰(40), 乙巳(41) ...
    backward → 壬寅(38), 辛丑(37) ...
"""

from datetime import UTC, datetime
from itertools import pairwise

from calculator.luck_pillars import calculate_luck_pillars
from calculator.models import ChartInput, LuckPillar, LuckPillarsOutput

# ── Fixtures ──────────────────────────────────────────────────────────────────

# Волжский 1999-09-12 23:55 UTC+4 — year 己卯 (Yin)
_VOLZHSKY_BIRTH = datetime(1999, 9, 12, 23, 55, 0)
_VOLZHSKY_LAT = 48.79
_VOLZHSKY_LON = 44.77
_VOLZHSKY_TZ = 4.0

_VOLZHSKY_F = ChartInput(
    birth_datetime=_VOLZHSKY_BIRTH,
    latitude=_VOLZHSKY_LAT,
    longitude=_VOLZHSKY_LON,
    tz_offset=_VOLZHSKY_TZ,
    gender="female",
)
_VOLZHSKY_M = ChartInput(
    birth_datetime=_VOLZHSKY_BIRTH,
    latitude=_VOLZHSKY_LAT,
    longitude=_VOLZHSKY_LON,
    tz_offset=_VOLZHSKY_TZ,
    gender="male",
)
_VOLZHSKY_NONE = ChartInput(
    birth_datetime=_VOLZHSKY_BIRTH,
    latitude=_VOLZHSKY_LAT,
    longitude=_VOLZHSKY_LON,
    tz_offset=_VOLZHSKY_TZ,
)

# Новокузнецк 1997-03-09 19:55 UTC+7 — year 丁丑 (Yin)
_NOVO_BIRTH = datetime(1997, 3, 9, 19, 55, 0)
_NOVO_LAT = 53.76
_NOVO_LON = 87.10
_NOVO_TZ = 7.0

_NOVO_F = ChartInput(
    birth_datetime=_NOVO_BIRTH,
    latitude=_NOVO_LAT,
    longitude=_NOVO_LON,
    tz_offset=_NOVO_TZ,
    gender="female",
)
_NOVO_M = ChartInput(
    birth_datetime=_NOVO_BIRTH,
    latitude=_NOVO_LAT,
    longitude=_NOVO_LON,
    tz_offset=_NOVO_TZ,
    gender="male",
)

# Yang year chart: 1998 (戊寅, 戊=index 4, Yang)
_YANG_M = ChartInput(
    birth_datetime=datetime(1998, 5, 15, 12, 0, 0),
    latitude=55.75,
    longitude=37.62,
    tz_offset=3.0,
    gender="male",
)
_YANG_F = ChartInput(
    birth_datetime=datetime(1998, 5, 15, 12, 0, 0),
    latitude=55.75,
    longitude=37.62,
    tz_offset=3.0,
    gender="female",
)


# ── No gender → None ──────────────────────────────────────────────────────────


class TestNoGender:
    def test_returns_none_when_gender_not_set(self) -> None:
        assert calculate_luck_pillars(_VOLZHSKY_NONE) is None

    def test_chart_input_defaults_gender_to_none(self) -> None:
        inp = ChartInput(
            birth_datetime=datetime(1999, 9, 12, 23, 55),
            latitude=48.79,
            longitude=44.77,
            tz_offset=4.0,
        )
        assert inp.gender is None


# ── Output type and structure ──────────────────────────────────────────────────


class TestOutputStructure:
    def test_returns_luck_pillars_output(self) -> None:
        out = calculate_luck_pillars(_VOLZHSKY_F)
        assert isinstance(out, LuckPillarsOutput)

    def test_eight_pillars(self) -> None:
        out = calculate_luck_pillars(_VOLZHSKY_F)
        assert out is not None
        assert len(out.pillars) == 8

    def test_all_luck_pillar_instances(self) -> None:
        out = calculate_luck_pillars(_VOLZHSKY_F)
        assert out is not None
        for p in out.pillars:
            assert isinstance(p, LuckPillar)

    def test_gender_stored_in_output(self) -> None:
        out = calculate_luck_pillars(_VOLZHSKY_F)
        assert out is not None
        assert out.gender == "female"

    def test_direction_is_forward_or_backward(self) -> None:
        out = calculate_luck_pillars(_VOLZHSKY_F)
        assert out is not None
        assert out.direction in ("forward", "backward")


# ── Direction logic ────────────────────────────────────────────────────────────


class TestDirection:
    def test_yin_year_female_is_forward(self) -> None:
        # 己卯年 (己=5, Yin) + female → forward
        out = calculate_luck_pillars(_VOLZHSKY_F)
        assert out is not None
        assert out.direction == "forward"

    def test_yin_year_male_is_backward(self) -> None:
        out = calculate_luck_pillars(_VOLZHSKY_M)
        assert out is not None
        assert out.direction == "backward"

    def test_yang_year_male_is_forward(self) -> None:
        # 戊寅年 (戊=4, Yang) + male → forward
        out = calculate_luck_pillars(_YANG_M)
        assert out is not None
        assert out.direction == "forward"

    def test_yang_year_female_is_backward(self) -> None:
        out = calculate_luck_pillars(_YANG_F)
        assert out is not None
        assert out.direction == "backward"

    def test_ding_chou_male_is_backward(self) -> None:
        # 丁丑年 (丁=3, Yin) + male → backward
        out = calculate_luck_pillars(_NOVO_M)
        assert out is not None
        assert out.direction == "backward"

    def test_ding_chou_female_is_forward(self) -> None:
        out = calculate_luck_pillars(_NOVO_F)
        assert out is not None
        assert out.direction == "forward"


# ── Pillar sequence — Волжский (month 癸酉) ───────────────────────────────────


class TestVolzhskyForward:
    def test_first_pillar_jia_xu(self) -> None:
        # forward from 癸酉(9) → 甲戌(10)
        out = calculate_luck_pillars(_VOLZHSKY_F)
        assert out is not None
        assert out.pillars[0].stem == "甲"
        assert out.pillars[0].branch == "戌"

    def test_second_pillar_yi_hai(self) -> None:
        # 甲戌(10) → 乙亥(11)
        out = calculate_luck_pillars(_VOLZHSKY_F)
        assert out is not None
        assert out.pillars[1].stem == "乙"
        assert out.pillars[1].branch == "亥"

    def test_third_pillar_bing_zi(self) -> None:
        out = calculate_luck_pillars(_VOLZHSKY_F)
        assert out is not None
        assert out.pillars[2].stem == "丙"
        assert out.pillars[2].branch == "子"

    def test_pillar_ages_increment_by_ten(self) -> None:
        out = calculate_luck_pillars(_VOLZHSKY_F)
        assert out is not None
        base = out.start_age_years
        for i, p in enumerate(out.pillars):
            assert p.start_age == base + i * 10

    def test_start_age_years_reasonable(self) -> None:
        out = calculate_luck_pillars(_VOLZHSKY_F)
        assert out is not None
        assert 0 <= out.start_age_years <= 15

    def test_start_age_months_in_range(self) -> None:
        out = calculate_luck_pillars(_VOLZHSKY_F)
        assert out is not None
        assert 0 <= out.start_age_months <= 11

    def test_start_age_days_in_range(self) -> None:
        out = calculate_luck_pillars(_VOLZHSKY_F)
        assert out is not None
        assert 0 <= out.start_age_days <= 29


class TestVolzhskyBackward:
    def test_first_pillar_ren_shen(self) -> None:
        # backward from 癸酉(9) → 壬申(8)
        out = calculate_luck_pillars(_VOLZHSKY_M)
        assert out is not None
        assert out.pillars[0].stem == "壬"
        assert out.pillars[0].branch == "申"

    def test_second_pillar_xin_wei(self) -> None:
        # 壬申(8) → 辛未(7)
        out = calculate_luck_pillars(_VOLZHSKY_M)
        assert out is not None
        assert out.pillars[1].stem == "辛"
        assert out.pillars[1].branch == "未"

    def test_pillar_ages_increment_by_ten(self) -> None:
        out = calculate_luck_pillars(_VOLZHSKY_M)
        assert out is not None
        base = out.start_age_years
        for i, p in enumerate(out.pillars):
            assert p.start_age == base + i * 10


# ── Pillar sequence — Новокузнецк (month 癸卯) ───────────────────────────────


class TestNovokuznetskForward:
    def test_first_pillar_jia_chen(self) -> None:
        # forward from 癸卯(39) → 甲辰(40)
        out = calculate_luck_pillars(_NOVO_F)
        assert out is not None
        assert out.pillars[0].stem == "甲"
        assert out.pillars[0].branch == "辰"

    def test_second_pillar_yi_si(self) -> None:
        # 甲辰(40) → 乙巳(41)
        out = calculate_luck_pillars(_NOVO_F)
        assert out is not None
        assert out.pillars[1].stem == "乙"
        assert out.pillars[1].branch == "巳"

    def test_pillar_ages_increment_by_ten(self) -> None:
        out = calculate_luck_pillars(_NOVO_F)
        assert out is not None
        base = out.start_age_years
        for i, p in enumerate(out.pillars):
            assert p.start_age == base + i * 10


class TestNovokuznetskBackward:
    def test_first_pillar_ren_yin(self) -> None:
        # backward from 癸卯(39) → 壬寅(38)
        out = calculate_luck_pillars(_NOVO_M)
        assert out is not None
        assert out.pillars[0].stem == "壬"
        assert out.pillars[0].branch == "寅"

    def test_second_pillar_xin_chou(self) -> None:
        # 壬寅(38) → 辛丑(37)
        out = calculate_luck_pillars(_NOVO_M)
        assert out is not None
        assert out.pillars[1].stem == "辛"
        assert out.pillars[1].branch == "丑"


# ── 60-cycle wrap-around ──────────────────────────────────────────────────────


class TestCycleWrap:
    def test_forward_wraps_at_60(self) -> None:
        # 癸亥 is 60-idx 59; forward next = 甲子 (0)
        inp = ChartInput(
            birth_datetime=datetime(1983, 12, 15, 12, 0, 0),
            latitude=55.75,
            longitude=37.62,
            tz_offset=3.0,
            gender="female",
        )
        out = calculate_luck_pillars(inp)
        assert out is not None
        # First pillar should be a valid Stem/Branch combination
        assert out.pillars[0].stem in ("甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸")

    def test_eight_pillars_always_unique_within_cycle(self) -> None:
        out = calculate_luck_pillars(_VOLZHSKY_F)
        assert out is not None
        pairs = [(p.stem, p.branch) for p in out.pillars]
        assert len(pairs) == len(set(pairs))


# ── Minute-level precision (start age + absolute pillar boundaries) ──────────


class TestMinutePrecision:
    def test_start_age_hours_in_range(self) -> None:
        out = calculate_luck_pillars(_VOLZHSKY_F)
        assert out is not None
        assert 0 <= out.start_age_hours <= 23

    def test_start_age_minutes_in_range(self) -> None:
        out = calculate_luck_pillars(_VOLZHSKY_F)
        assert out is not None
        assert 0 <= out.start_age_minutes <= 59

    def test_pillar_start_datetime_is_utc_aware(self) -> None:
        out = calculate_luck_pillars(_VOLZHSKY_F)
        assert out is not None
        first = out.pillars[0]
        assert first.start_datetime.tzinfo is not None
        offset = first.start_datetime.utcoffset()
        assert offset is not None
        assert offset.total_seconds() == 0

    def test_pillar_starts_strictly_increase(self) -> None:
        out = calculate_luck_pillars(_VOLZHSKY_F)
        assert out is not None
        for prev, curr in pairwise(p.start_datetime for p in out.pillars):
            assert prev < curr

    def test_pillar_span_is_ten_real_years(self) -> None:
        out = calculate_luck_pillars(_VOLZHSKY_F)
        assert out is not None
        ten_years_seconds = 10 * 365.2425 * 86400
        for prev, curr in pairwise(out.pillars):
            delta = (curr.start_datetime - prev.start_datetime).total_seconds()
            assert abs(delta - ten_years_seconds) < 1.0

    def test_pillar_end_equals_next_start(self) -> None:
        out = calculate_luck_pillars(_VOLZHSKY_F)
        assert out is not None
        for prev, curr in pairwise(out.pillars):
            assert prev.end_datetime == curr.start_datetime

    def test_one_minute_birth_shift_moves_pillar_by_two_hours(self) -> None:
        base = ChartInput(
            birth_datetime=datetime(1999, 9, 12, 23, 55, 0),
            latitude=48.79,
            longitude=44.77,
            tz_offset=4.0,
            gender="female",
        )
        shifted = ChartInput(
            birth_datetime=datetime(1999, 9, 12, 23, 56, 0),
            latitude=48.79,
            longitude=44.77,
            tz_offset=4.0,
            gender="female",
        )
        out_a = calculate_luck_pillars(base)
        out_b = calculate_luck_pillars(shifted)
        assert out_a is not None
        assert out_b is not None
        delta_seconds = abs(
            (out_a.pillars[0].start_datetime - out_b.pillars[0].start_datetime).total_seconds()
        )
        assert 7100 <= delta_seconds <= 7400

    def test_first_pillar_boundary_after_birth(self) -> None:
        out = calculate_luck_pillars(_VOLZHSKY_F)
        assert out is not None
        birth_utc = datetime(1999, 9, 12, 19, 55, 0, tzinfo=UTC)
        assert out.pillars[0].start_datetime > birth_utc
