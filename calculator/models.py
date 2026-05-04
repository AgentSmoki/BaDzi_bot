from datetime import datetime
from typing import Literal, get_args

from pydantic import BaseModel, field_validator

# ── Primitive types ───────────────────────────────────────────────────────────

Stem = Literal["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
Branch = Literal["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

STEMS: tuple[str, ...] = get_args(Stem)
BRANCHES: tuple[str, ...] = get_args(Branch)

HiddenStemsSchool = Literal["traditional", "modern", "ken_lai"]


# ── Composite types ───────────────────────────────────────────────────────────


class Pillar(BaseModel):
    stem: Stem
    branch: Branch
    name: str


# ── Calculator I/O ────────────────────────────────────────────────────────────


class ChartInput(BaseModel):
    birth_datetime: datetime
    latitude: float
    longitude: float
    tz_offset: float
    early_rat: bool = False
    hidden_stems_school: HiddenStemsSchool = "traditional"

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: float) -> float:
        if not -90.0 <= v <= 90.0:
            raise ValueError(f"latitude must be in [-90, 90], got {v}")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: float) -> float:
        if not -180.0 <= v <= 180.0:
            raise ValueError(f"longitude must be in [-180, 180], got {v}")
        return v


class ChartOutput(BaseModel):
    input: ChartInput
    true_solar_time: datetime
    pillars: list[Pillar]
    day_master: Stem
    hidden_stems: dict[str, list[Stem]]
    ten_gods: dict[str, list[str]]
    element_balance: dict[str, float]
