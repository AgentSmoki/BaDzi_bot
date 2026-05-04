from datetime import datetime
from typing import Any

import pytest
from pydantic import ValidationError

from calculator.models import (
    BRANCHES,
    STEMS,
    Branch,
    ChartInput,
    ChartOutput,
    Pillar,
    Stem,
)

_VALID_DT = datetime(1990, 6, 15, 12, 0, 0)


def _make(**overrides: Any) -> ChartInput:
    """Build a ChartInput from defaults, applying overrides via model_validate."""
    data: dict[str, Any] = {
        "birth_datetime": _VALID_DT,
        "latitude": 55.75,
        "longitude": 37.62,
        "tz_offset": 3.0,
    }
    data.update(overrides)
    return ChartInput.model_validate(data)


class TestChartInput:
    def test_valid_input_creates_instance(self) -> None:
        inp = _make()
        assert inp.birth_datetime == _VALID_DT
        assert inp.latitude == 55.75
        assert inp.longitude == 37.62
        assert inp.tz_offset == 3.0

    def test_defaults(self) -> None:
        inp = _make()
        assert inp.early_rat is False
        assert inp.hidden_stems_school == "traditional"

    def test_latitude_too_low_raises(self) -> None:
        with pytest.raises(ValidationError):
            _make(latitude=-91.0)

    def test_latitude_too_high_raises(self) -> None:
        with pytest.raises(ValidationError):
            _make(latitude=90.1)

    def test_longitude_too_low_raises(self) -> None:
        with pytest.raises(ValidationError):
            _make(longitude=-180.1)

    def test_longitude_too_high_raises(self) -> None:
        with pytest.raises(ValidationError):
            _make(longitude=181.0)

    def test_boundary_values_accepted(self) -> None:
        _make(latitude=-90.0, longitude=-180.0)
        _make(latitude=90.0, longitude=180.0)

    def test_invalid_hidden_stems_school_raises(self) -> None:
        with pytest.raises(ValidationError):
            _make(hidden_stems_school="unknown")

    def test_early_rat_toggle(self) -> None:
        inp = _make(early_rat=True)
        assert inp.early_rat is True


class TestPillar:
    def test_valid_pillar(self) -> None:
        p = Pillar(stem="甲", branch="子", name="year")
        assert p.stem == "甲"
        assert p.branch == "子"
        assert p.name == "year"

    def test_invalid_stem_raises(self) -> None:
        with pytest.raises(ValidationError):
            Pillar(stem="X", branch="子", name="year")  # type: ignore[arg-type]

    def test_invalid_branch_raises(self) -> None:
        with pytest.raises(ValidationError):
            Pillar(stem="甲", branch="Z", name="year")  # type: ignore[arg-type]


class TestStemBranchConstants:
    def test_stems_count(self) -> None:
        assert len(STEMS) == 10

    def test_branches_count(self) -> None:
        assert len(BRANCHES) == 12

    def test_stem_type_annotation(self) -> None:
        stem: Stem = "甲"
        assert stem in STEMS

    def test_branch_type_annotation(self) -> None:
        branch: Branch = "子"
        assert branch in BRANCHES


class TestChartOutput:
    def test_output_stores_input(self) -> None:
        inp = _make()
        pillars = [
            Pillar(stem="丙", branch="午", name="year"),
            Pillar(stem="庚", branch="午", name="month"),
            Pillar(stem="甲", branch="子", name="day"),
            Pillar(stem="壬", branch="申", name="hour"),
        ]
        out = ChartOutput(
            input=inp,
            true_solar_time=_VALID_DT,
            pillars=pillars,
            day_master="甲",
            hidden_stems={
                "year": ["丁"],
                "month": ["己"],
                "day": [],
                "hour": ["戊", "壬", "庚"],
            },
            ten_gods={"year": ["食神"], "month": ["偏财"]},
            element_balance={"木": 20.0, "火": 30.0, "土": 15.0, "金": 25.0, "水": 10.0},
        )
        assert out.input is inp
        assert len(out.pillars) == 4
        assert out.day_master == "甲"
