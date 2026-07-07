"""Calendar selection (择日 Ze Ri) — score days in a range against a natal chart.

When the user asks "what are the best dates for X in the next 3 months?",
the LLM alone cannot reason over 90 day pillars. The calculator pre-scores
every day in the range against the user's natal chart and surfaces a
ranked table the LLM cites verbatim.

Scoring axes (additive, all per-day):
- 六合 with any natal branch  → +2.0 (harmony — supports the event)
- 六冲 with natal Day branch  → -3.0 (clash with most-personal pillar)
- 六冲 with other natal branch → -1.5
- Required event star active   → +1.5 per match
- Forbidden event star active  → -2.5 per match
- Day element preference match → +1.0
- Day element preference clash → -1.0

This is a deliberately small MVP. The classical 择日 system has 50+ rules
(building, opening, burial, marriage…) catalogued in 协纪辨方书 —
adding them is an incremental upgrade. For now we cover 6 event types
that account for ~80% of real user questions.

The full Шэнь Ша detection (60 stars) is re-used here: we compute
each day's symbolic_stars by constructing a synthetic ``ChartInput``
with hour=noon Moscow — hour doesn't affect day/month/year stars,
only hour stars (which we ignore for date selection since events
aren't tied to a specific hour at this stage).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Final, Literal

from calculator.models import ChartInput, ChartOutput, Pillar
from calculator.pillars import calculate_pillars
from calculator.symbolic_stars import calculate_symbolic_stars

EventType = Literal[
    "wedding",
    "negotiation",
    "contract",
    "surgery",
    "move",
    "launch",
    "spiritual",
]

EVENT_TYPE_RU: Final[dict[EventType, str]] = {
    "wedding": "Свадьба",
    "negotiation": "Переговоры",
    "contract": "Подписание контракта",
    "surgery": "Операция / медицинская процедура",
    "move": "Переезд",
    "launch": "Запуск проекта",
    "spiritual": "Медитация / чайная церемония / ритуал",
}


# ── Branch interaction tables (shared with ai.temporal_context) ───────────


_SIX_HARMONIES: Final[dict[str, str]] = {
    "子": "丑",
    "丑": "子",
    "寅": "亥",
    "亥": "寅",
    "卯": "戌",
    "戌": "卯",
    "辰": "酉",
    "酉": "辰",
    "巳": "申",
    "申": "巳",
    "午": "未",
    "未": "午",
}

_SIX_CLASHES: Final[dict[str, str]] = {
    "子": "午",
    "午": "子",
    "丑": "未",
    "未": "丑",
    "寅": "申",
    "申": "寅",
    "卯": "酉",
    "酉": "卯",
    "辰": "戌",
    "戌": "辰",
    "巳": "亥",
    "亥": "巳",
}


# ── Event rules table ─────────────────────────────────────────────────────
#
# Source: classical 协纪辨方书 (Sezhi Bianfang Shu) where rules exist;
# pragmatic modern interpretation where the classics are silent (e.g.
# project-launches don't appear in the Qing-era manuals). Provenance
# noted per-event for future audit by Bogdan's teacher.


@dataclass(frozen=True)
class EventRules:
    """Static per-event-type scoring policy. ``required_stars`` add
    a positive score when active on the day; ``forbidden_stars`` add
    a negative penalty. Element preferences modulate the day-stem
    score (e.g. weddings favour days with growing/passionate energy
    — wood or fire stems)."""

    required_stars: tuple[str, ...]
    forbidden_stars: tuple[str, ...]
    preferred_day_elements: tuple[str, ...]
    avoided_day_elements: tuple[str, ...]
    source: str


# Stem → element mapping (also exists in calculator/models but we
# inline-duplicate to keep this module dependency-light).
_STEM_ELEMENT: Final[dict[str, str]] = {
    "甲": "wood",
    "乙": "wood",
    "丙": "fire",
    "丁": "fire",
    "戊": "earth",
    "己": "earth",
    "庚": "metal",
    "辛": "metal",
    "壬": "water",
    "癸": "water",
}


EVENT_RULES: Final[dict[EventType, EventRules]] = {
    "wedding": EventRules(
        required_stars=("天乙贵人", "月德贵人", "天德贵人", "桃花", "红艳"),
        forbidden_stars=("白虎", "飞刃", "孤辰", "寡宿", "灾煞", "亡神"),
        preferred_day_elements=("wood", "fire"),
        avoided_day_elements=("metal",),
        source="协纪辨方书 + classical 桃花-marriage rules",
    ),
    "negotiation": EventRules(
        required_stars=("将星", "天乙贵人", "文昌贵人"),
        forbidden_stars=("截路空亡", "空亡", "白虎"),
        preferred_day_elements=("metal", "wood"),
        avoided_day_elements=(),
        source="modern interpretation — career advancement",
    ),
    "contract": EventRules(
        required_stars=("天乙贵人", "月德贵人", "天德贵人", "学堂"),
        forbidden_stars=("截路空亡", "空亡", "破日"),
        preferred_day_elements=("metal", "earth"),
        avoided_day_elements=(),
        source="协纪辨方书 — 立券交易 (signing contracts)",
    ),
    "surgery": EventRules(
        required_stars=("天医", "天乙贵人"),
        forbidden_stars=("白虎", "飞刃", "灾煞", "亡神", "血刃"),
        preferred_day_elements=("water",),
        avoided_day_elements=("fire",),
        source="协纪辨方书 — 求医疗病 (seeking medical treatment)",
    ),
    "move": EventRules(
        required_stars=("天乙贵人", "月德贵人", "驿马"),
        forbidden_stars=("白虎", "灾煞", "破日"),
        preferred_day_elements=("water", "wood"),
        avoided_day_elements=(),
        source="协纪辨方书 — 入宅 (moving into a new home)",
    ),
    "launch": EventRules(
        required_stars=("将星", "天乙贵人", "驿马"),
        forbidden_stars=("截路空亡", "空亡", "破日"),
        preferred_day_elements=("wood", "fire"),
        avoided_day_elements=(),
        source="modern interpretation — entrepreneurial launches",
    ),
    "spiritual": EventRules(
        required_stars=("天乙贵人", "月德贵人", "天德贵人", "文昌贵人", "学堂"),
        forbidden_stars=("白虎", "飞刃", "灾煞", "亡神"),
        preferred_day_elements=("water", "wood"),
        avoided_day_elements=("fire",),
        source="modern interpretation — meditative / spiritual practices",
    ),
}


# ── Data structures ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class DayPillar:
    """The four pillars at noon Moscow for a given calendar date.

    Hour pillar is computed against a fixed 12:00 anchor — we only
    use day/month/year for date selection. Including hour would
    multiply candidate count by 12 (one per двухчасовка) and we don't
    have user intent for hour-precision yet."""

    date: date
    year_stem: str
    year_branch: str
    month_stem: str
    month_branch: str
    day_stem: str
    day_branch: str
    hour_stem: str
    hour_branch: str


@dataclass(frozen=True)
class ScoredDay:
    """A single day's score against a natal chart for a given event."""

    pillar: DayPillar
    score: float
    factors: list[str] = field(default_factory=list)
    activated_required_stars: list[str] = field(default_factory=list)
    activated_forbidden_stars: list[str] = field(default_factory=list)

    @property
    def day_pillar_str(self) -> str:
        return f"{self.pillar.day_stem}{self.pillar.day_branch}"


# ── Public API ────────────────────────────────────────────────────────────


_NOON_LATITUDE: Final = 55.7558  # Moscow — neutral mid-Russia default
_NOON_LONGITUDE: Final = 37.6173
_NOON_TZ_OFFSET: Final = 3.0


def generate_day_pillars(start: date, end: date) -> list[DayPillar]:
    """Compute the four pillars at noon Moscow for every day in
    ``[start, end]`` (inclusive). Returns chronologically ordered.

    Hour pillar is fixed to noon. The day pillar itself is hour-
    independent (changes only at midnight true solar time), and we
    aggregate scores over day-level features only.
    """
    if end < start:
        raise ValueError(f"end {end} is before start {start}")
    days: list[DayPillar] = []
    current = start
    while current <= end:
        noon = datetime.combine(current, datetime.min.time()).replace(hour=12)
        inp = ChartInput(
            birth_datetime=noon,
            latitude=_NOON_LATITUDE,
            longitude=_NOON_LONGITUDE,
            tz_offset=_NOON_TZ_OFFSET,
            early_rat=False,
        )
        pillars = calculate_pillars(inp)
        days.append(
            DayPillar(
                date=current,
                year_stem=pillars[0].stem,
                year_branch=pillars[0].branch,
                month_stem=pillars[1].stem,
                month_branch=pillars[1].branch,
                day_stem=pillars[2].stem,
                day_branch=pillars[2].branch,
                hour_stem=pillars[3].stem,
                hour_branch=pillars[3].branch,
            )
        )
        current += timedelta(days=1)
    return days


def _day_to_pillars(day: DayPillar) -> list[Pillar]:
    """Convert ``DayPillar`` to the ``list[Pillar]`` expected by
    ``calculate_symbolic_stars``."""
    return [
        Pillar(stem=day.year_stem, branch=day.year_branch, name="year"),  # type: ignore[arg-type]
        Pillar(stem=day.month_stem, branch=day.month_branch, name="month"),  # type: ignore[arg-type]
        Pillar(stem=day.day_stem, branch=day.day_branch, name="day"),  # type: ignore[arg-type]
        Pillar(stem=day.hour_stem, branch=day.hour_branch, name="hour"),  # type: ignore[arg-type]
    ]


def score_day_for_event(
    natal_chart: ChartOutput,
    day: DayPillar,
    event_type: EventType,
) -> ScoredDay:
    """Score a single day against the natal chart for a given event.

    See module docstring for the scoring axes.
    """
    rules = EVENT_RULES[event_type]
    score = 0.0
    factors: list[str] = []
    activated_required: list[str] = []
    activated_forbidden: list[str] = []

    # ── Branch interactions (六合 / 六冲) ──
    natal_day_branch = next(p.branch for p in natal_chart.pillars if p.name == "day")
    natal_branches = [(p.name, p.branch) for p in natal_chart.pillars]
    day_branches_in_day = [
        ("year", day.year_branch),
        ("month", day.month_branch),
        ("day", day.day_branch),
    ]

    for natal_pillar_name, nb in natal_branches:
        for day_pillar_name, db in day_branches_in_day:
            if _SIX_HARMONIES.get(nb) == db:
                score += 2.0
                factors.append(
                    f"六合 (гармония): {nb} рождения ({natal_pillar_name}) ↔ "
                    f"{db} в {day_pillar_name}"
                )
            elif _SIX_CLASHES.get(nb) == db:
                if nb == natal_day_branch:
                    score -= 3.0
                    factors.append(
                        f"六冲 (столкновение со столпом дня): {nb} рождения (day) ↔ "
                        f"{db} в {day_pillar_name}"
                    )
                else:
                    score -= 1.5
                    factors.append(
                        f"六冲 (столкновение): {nb} рождения "
                        f"({natal_pillar_name}) ↔ {db} в {day_pillar_name}"
                    )

    # ── Stars active on this day ──
    day_stars = calculate_symbolic_stars(_day_to_pillars(day))
    day_star_names = {s.name_zh for s in day_stars.stars}
    for star_name in rules.required_stars:
        if star_name in day_star_names:
            score += 1.5
            activated_required.append(star_name)
    for star_name in rules.forbidden_stars:
        if star_name in day_star_names:
            score -= 2.5
            activated_forbidden.append(star_name)
    if activated_required:
        factors.append(f"активны желательные звёзды: {', '.join(activated_required)}")
    if activated_forbidden:
        factors.append(f"активны нежелательные звёзды: {', '.join(activated_forbidden)}")

    # ── Day stem element preference ──
    day_element = _STEM_ELEMENT[day.day_stem]
    if day_element in rules.preferred_day_elements:
        score += 1.0
        factors.append(f"стихия дня {day_element} — благоприятна для события")
    elif day_element in rules.avoided_day_elements:
        score -= 1.0
        factors.append(f"стихия дня {day_element} — нежелательна для события")

    return ScoredDay(
        pillar=day,
        score=round(score, 2),
        factors=factors,
        activated_required_stars=activated_required,
        activated_forbidden_stars=activated_forbidden,
    )


def pick_best_dates(
    natal_chart: ChartOutput,
    start: date,
    end: date,
    event_type: EventType,
    *,
    top_n: int = 10,
    bottom_n: int = 5,
) -> tuple[list[ScoredDay], list[ScoredDay]]:
    """End-to-end: score every day in ``[start, end]`` and return
    (top_n favourable, bottom_n unfavourable) lists.

    The bottom list is included so Анастасия can warn the user about
    specific days to avoid — surfacing only the favourites would let
    the user accidentally pick a bad day not in the top-N."""
    days = generate_day_pillars(start, end)
    scored = [score_day_for_event(natal_chart, d, event_type) for d in days]
    top = sorted(scored, key=lambda s: (-s.score, s.pillar.date))[:top_n]
    bottom = sorted(scored, key=lambda s: (s.score, s.pillar.date))[:bottom_n]
    return top, bottom
