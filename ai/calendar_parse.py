"""Detect calendar-selection (择日) intent and parse date range + event type.

Triggered before the regular router: if a user-message looks like
"когда лучше провести свадьбу в июне" we want to attach the
calendar block to the prompt. Two extractions happen:

1. **Event type** — one of 6 supported categories (wedding, negotiation,
   contract, surgery, move, launch). Heuristic keyword match in Russian.
   Returns ``None`` if no event type is unambiguously detected — the
   caller can either default to a generic auspicious-day search or
   prompt the user for clarification.

2. **Date range** — natural-language phrases like "в июне", "следующие
   3 месяца", "ближайшие 2 недели", "до конца лета". Uses ``dateparser``
   relative-time parsing plus a few hand-tuned patterns Russians use
   that the library misses.

Always returns a ``CalendarRequest`` or ``None``. The wrapper that
detects intent is ``detect_calendar_request(text, now)`` —
``now`` is injected for testability (so we don't depend on system
clock in unit tests).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Final

import dateparser

from calculator.calendar_select import EventType

_DEFAULT_HORIZON_DAYS: Final = 30
_MAX_HORIZON_DAYS: Final = 365


_CALENDAR_KEYWORDS: Final[tuple[str, ...]] = (
    "лучшая дата",
    "лучшие даты",
    "лучший день",
    "лучшие дни",
    "благоприятн",
    "когда лучше",
    "когда лучший",
    "выбрать день",
    "выбрать дату",
    "подобрать день",
    "подобрать дату",
    "запланировать",
    "назначить день",
    "удачный день",
    "удачные дни",
    "удачная дата",
    "удачные даты",
    "хорошая дата",
    "хорошие даты",
    "на какой день",
    "на какую дату",
    "в какой день",
    "в какую дату",
)


_EVENT_KEYWORDS: Final[dict[EventType, tuple[str, ...]]] = {
    "wedding": (
        "свадьб",
        "жениться",
        "выйти замуж",
        "брак",
        "регистрация",
        "роспис",
        "венчан",
    ),
    "negotiation": (
        "переговор",
        "встреч",
        "презентац",
        "интервью",
        "собеседован",
        "беседа",
        "разговор",
    ),
    "contract": (
        "контракт",
        "договор",
        "сделк",
        "подпис",
        "оформл",
        "покупка квартиры",
        "ипотек",
    ),
    "surgery": (
        "операц",
        "хирург",
        "процедур",
        "лечение",
        "анализ",
        "обследован",
    ),
    "move": (
        "переезд",
        "переезж",
        "заселен",
        "новоселье",
        "снять квартиру",
        "купить квартиру",
        "новый дом",
    ),
    "launch": (
        "запуск",
        "запуст",
        "старт бизнес",
        "открытие",
        "открыт",
        "релиз",
        "начать дело",
        "открыть бизнес",
    ),
}


_MONTH_NAMES_RU: Final[dict[str, int]] = {
    "январ": 1,
    "феврал": 2,
    "март": 3,
    "апрел": 4,
    "ма": 5,
    "июн": 6,
    "июл": 7,
    "август": 8,
    "сентябр": 9,
    "октябр": 10,
    "ноябр": 11,
    "декабр": 12,
}


@dataclass(frozen=True)
class CalendarRequest:
    """A parsed calendar-selection request.

    ``event_type`` may be ``None`` when the user asks "когда лучшие
    даты в июне" without specifying what for. The handler can either
    fall back to a generic auspicious search or ask the user via an
    inline keyboard."""

    event_type: EventType | None
    start: date
    end: date

    @property
    def horizon_days(self) -> int:
        return (self.end - self.start).days + 1


def _normalise(text: str) -> str:
    return text.lower().replace("ё", "е").strip()


def _has_calendar_intent(norm: str) -> bool:
    return any(kw in norm for kw in _CALENDAR_KEYWORDS)


def _extract_event_type(norm: str) -> EventType | None:
    matches: dict[EventType, int] = {}
    for event_type, keywords in _EVENT_KEYWORDS.items():
        hit_count = sum(1 for kw in keywords if kw in norm)
        if hit_count > 0:
            matches[event_type] = hit_count
    if not matches:
        return None
    # Highest hit count wins. Ties broken by event-type-list ordering
    # (which intentionally puts more common events first).
    return max(matches.items(), key=lambda kv: kv[1])[0]


_NEXT_N_MONTHS_RE = re.compile(
    r"(?:следующ\w*|ближайш\w*|предстоящ\w*)\s+(\d+|два|три|четыре|пять|шесть|семь|восемь|девять|двенадцать)?\s*месяц",
    re.IGNORECASE,
)

_NEXT_N_WEEKS_RE = re.compile(
    r"(?:следующ\w*|ближайш\w*|предстоящ\w*)\s+(\d+|две|три|четыре|пять|шесть)?\s*недел",
    re.IGNORECASE,
)

_WORD_TO_NUM: Final[dict[str, int]] = {
    "один": 1,
    "два": 2,
    "две": 2,
    "три": 3,
    "четыре": 4,
    "пять": 5,
    "шесть": 6,
    "семь": 7,
    "восемь": 8,
    "девять": 9,
    "десять": 10,
    "двенадцать": 12,
}


def _extract_date_range(norm: str, now: date) -> tuple[date, date]:
    """Try several patterns; fall back to a 30-day window from now."""
    # Pattern 1: «следующие N месяцев» / «ближайшие N месяцев»
    m = _NEXT_N_MONTHS_RE.search(norm)
    if m:
        n_raw = m.group(1) or "1"
        n = int(n_raw) if n_raw.isdigit() else _WORD_TO_NUM.get(n_raw, 1)
        return now, now + timedelta(days=min(30 * n, _MAX_HORIZON_DAYS))

    # Pattern 2: «следующие N недель»
    m = _NEXT_N_WEEKS_RE.search(norm)
    if m:
        n_raw = m.group(1) or "1"
        n = int(n_raw) if n_raw.isdigit() else _WORD_TO_NUM.get(n_raw, 1)
        return now, now + timedelta(days=min(7 * n, _MAX_HORIZON_DAYS))

    # Pattern 3: «в июне», «в июле и августе»
    months_hit: list[int] = []
    for prefix, m_num in _MONTH_NAMES_RU.items():
        # Match "в <month>" with the prefix
        if re.search(rf"\bв\s+{re.escape(prefix)}\w*", norm):
            months_hit.append(m_num)
    if months_hit:
        months_hit.sort()
        first, last = months_hit[0], months_hit[-1]
        # Choose year: if the month is in the past for this year, roll to next year
        year_for_first = now.year if first >= now.month else now.year + 1
        year_for_last = now.year if last >= now.month else now.year + 1
        start = date(year_for_first, first, 1)
        # Last day of last month — naive: use day 28 + walk forward
        if last == 12:
            end_next = date(year_for_last + 1, 1, 1)
        else:
            end_next = date(year_for_last, last + 1, 1)
        end = end_next - timedelta(days=1)
        # If user is asking about June while we're already in June, start = today
        if start < now:
            start = now
        return start, end

    # Pattern 4: «до конца лета / года / месяца»
    if "до конца лета" in norm:
        # Summer ends Aug 31
        year = now.year if now.month <= 8 else now.year + 1
        return now, date(year, 8, 31)
    if "до конца года" in norm:
        return now, date(now.year, 12, 31)
    if "до конца месяца" in norm:
        nm = date(
            now.year + (1 if now.month == 12 else 0), 1 if now.month == 12 else now.month + 1, 1
        )
        return now, nm - timedelta(days=1)

    # Pattern 5: dateparser fallback for explicit dates
    parsed = dateparser.parse(norm, languages=["ru"], settings={"PREFER_DATES_FROM": "future"})
    if parsed is not None:
        target = parsed.date()
        if target > now:
            return now, min(target, now + timedelta(days=_MAX_HORIZON_DAYS))

    # Default: 30-day window
    return now, now + timedelta(days=_DEFAULT_HORIZON_DAYS)


def detect_calendar_request(text: str, now: date) -> CalendarRequest | None:
    """Parse a user message into a ``CalendarRequest`` or return None.

    ``now`` is injected for testability — tests pin a known date so
    relative-time parsing is deterministic.
    """
    norm = _normalise(text)
    if not _has_calendar_intent(norm):
        return None
    event_type = _extract_event_type(norm)
    start, end = _extract_date_range(norm, now)
    return CalendarRequest(event_type=event_type, start=start, end=end)
