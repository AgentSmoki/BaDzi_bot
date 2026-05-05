from datetime import datetime
from typing import Literal, get_args

from pydantic import BaseModel, field_validator

# ── Primitive types ───────────────────────────────────────────────────────────

Stem = Literal["甲", "乙", "丙", "丁", "戊", "己", "庚", "辛", "壬", "癸"]
Branch = Literal["子", "丑", "寅", "卯", "辰", "巳", "午", "未", "申", "酉", "戌", "亥"]

STEMS: tuple[str, ...] = get_args(Stem)
BRANCHES: tuple[str, ...] = get_args(Branch)

HiddenStemsSchool = Literal["traditional", "modern", "ken_lai"]
Gender = Literal["male", "female"]


# ── Composite types ───────────────────────────────────────────────────────────


class Pillar(BaseModel):
    stem: Stem
    branch: Branch
    name: str


class LuckPillar(BaseModel):
    stem: Stem
    branch: Branch
    name: str
    start_age: int
    start_datetime: datetime
    end_datetime: datetime


class LuckPillarsOutput(BaseModel):
    gender: Gender
    direction: Literal["forward", "backward"]
    start_age_years: int
    start_age_months: int
    start_age_days: int
    start_age_hours: int
    start_age_minutes: int
    pillars: list[LuckPillar]


InteractionType = Literal[
    "stem_combination",
    "branch_clash",
    "six_harmony",
    "three_harmony",
    "half_harmony",
    "three_punishment",
    "self_punishment",
    "six_harm",
    "six_break",
]


class Interaction(BaseModel):
    type: InteractionType
    name: str
    members: list[str]
    transforms_to: str | None = None
    pillars: list[str]


class InteractionsOutput(BaseModel):
    stem_combinations: list[Interaction]
    branch_clashes: list[Interaction]
    six_harmonies: list[Interaction]
    three_harmonies: list[Interaction]
    half_harmonies: list[Interaction]
    three_punishments: list[Interaction]
    self_punishments: list[Interaction]
    six_harms: list[Interaction]
    six_breaks: list[Interaction]


SymbolicStarCategory = Literal[
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
]
SymbolicStarNature = Literal["auspicious", "inauspicious", "mixed"]


class SymbolicStar(BaseModel):
    name_zh: str
    name_pinyin: str
    name_ru: str
    category: SymbolicStarCategory
    nature: SymbolicStarNature
    source: str
    pillars: list[str]


class SymbolicStarsOutput(BaseModel):
    stars: list[SymbolicStar]


class AuxiliaryPillars(BaseModel):
    tai_yuan: Pillar
    ming_gong: Pillar


# ── Calculator I/O ────────────────────────────────────────────────────────────


class ChartInput(BaseModel):
    birth_datetime: datetime
    latitude: float
    longitude: float
    tz_offset: float
    early_rat: bool = False
    hidden_stems_school: HiddenStemsSchool = "traditional"
    gender: Gender | None = None

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
    luck_pillars: LuckPillarsOutput | None = None
    interactions: InteractionsOutput | None = None
    symbolic_stars: SymbolicStarsOutput | None = None
    auxiliary: AuxiliaryPillars | None = None
