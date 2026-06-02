"""Wave 4e — important dates detector.

Anastasia acts as a personal astrologer who watches for resonances
between a chart's natal Шэнь Ша / pillar branches and the calendar:
each upcoming day, year/month/day pillars trigger or deactivate
specific stars. We surface the «significant» ones (Белый Тигр, Цветок
Персика, Звезда Академии, Семь Убийц, Овечий Нож, etc.) so the bot
can pre-warn the user and prompt a journal reflection.

Rate-limit (Bogdan, 2026-05-20): at most one important-date message
per chart per week. The repository layer keeps ``last_important_date_at``
on ChartJournalSettings; the scheduler job skips when that's < 7 days
ago.

Public API:
- ``find_important_dates_in_range(chart, start, end) -> list[ImportantDate]``
- ``format_important_date_message(chart, important) -> str``
- ``render_demo_for_chart(chart, today) -> str`` — what the user
  would see if a date were active today; used by the /start demo
  card so the user knows what to expect.

This is a pure computation module — no DB, no Telegram. Scheduler
and handlers compose it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Final

from calculator import calculate_chart
from calculator.models import ChartInput, ChartOutput
from calculator.symbolic_stars_tables import META as STAR_META

# Stars worth telling the user about — high-signal natal markers that
# meaningfully shift the day's energy when they line up with the day
# pillar branch. Match by ``name_zh`` (the only stable identifier
# exposed on the ``SymbolicStar`` Pydantic model).
_SIGNIFICANT_STAR_ZH: Final[frozenset[str]] = frozenset(
    {
        "天乙贵人",  # благородный покровитель
        "文昌贵人",  # академия, обучение
        "天德贵人",  # небесная добродетель
        "月德贵人",  # лунная добродетель
        "桃花",  # Цветок Персика
        "驿马",  # Почтовая Лошадь, путешествия
        "华盖",  # Цветущий Балдахин, духовность
        "将星",  # Звезда Генерала
        "羊刃",  # Овечий Нож
        "飞刃",  # Летящий Нож
        "白虎",  # Белый Тигр
    }
)
# Reverse lookup: name_zh → STAR_META key (для severity).
_NAME_ZH_TO_KEY: Final[dict[str, str]] = {meta.name_zh: key for key, meta in STAR_META.items()}


@dataclass(frozen=True)
class ImportantDate:
    """One significant date in the calendar range.

    ``active_stars`` are the star names (``name_zh``) that fire on
    ``date_`` thanks to the day pillar branch matching the user's
    natal anchor. ``severity`` lets the UI sort/colour-code:
    - ``high``: dangerous Шэнь Ша (Белый Тигр, Овечий Нож)
    - ``medium``: mixed/strong (Цветок Персика, Почтовая Лошадь)
    - ``low``: auspicious-only (Благородные, Академия)
    """

    date_: date
    active_stars: tuple[str, ...]  # values are name_zh strings
    severity: str  # "low" | "medium" | "high"


def _star_severity(name_zh: str) -> str:
    key = _NAME_ZH_TO_KEY.get(name_zh)
    if key is None:
        return "low"
    meta = STAR_META[key]
    if meta.nature == "inauspicious":
        return "high"
    if meta.nature == "mixed":
        return "medium"
    return "low"


def _pick_severity(active_stars: tuple[str, ...]) -> str:
    """Highest severity among active stars wins."""
    rank = {"low": 0, "medium": 1, "high": 2}
    best = "low"
    for sid in active_stars:
        candidate = _star_severity(sid)
        if rank[candidate] > rank[best]:
            best = candidate
    return best


def _day_pillars(target: date) -> ChartOutput:
    """Build a chart for ``target`` at noon UTC so we can read its
    year/month/day pillars without invoking the natal calculator
    from scratch every call (calculate_chart is the unified path)."""
    return calculate_chart(
        ChartInput(
            birth_datetime=datetime.combine(target, time(12, 0)),
            latitude=0.0,
            longitude=0.0,
            tz_offset=0.0,
            gender="male",
        )
    )


def find_important_dates_in_range(
    chart: ChartOutput, start: date, end: date
) -> list[ImportantDate]:
    """Walk each day from ``start`` to ``end`` inclusive and pick
    dates where the day pillar's branch activates one of the user's
    natal significant stars.

    Activation rule (simplification of classical 神煞 anchoring): a
    natal star with anchor pillar X is «active» today when today's
    day-pillar branch matches the chart's branch that holds the
    star. This is the same hot-spot the scheduler in W3 uses for the
    daily-forecast headers.
    """
    if start > end:
        raise ValueError("start must be <= end")

    # Resolve natal star positions → branches.
    # ``SymbolicStar.pillars`` is a list of pillar names
    # (``year`` / ``month`` / ``day`` / ``hour``) — translate each to
    # the corresponding natal branch.
    pillar_branch = {
        "year": chart.pillars[0].branch,
        "month": chart.pillars[1].branch,
        "day": chart.pillars[2].branch,
        "hour": chart.pillars[3].branch,
    }
    natal_star_anchors: dict[str, tuple[str, ...]] = {}
    if chart.symbolic_stars is not None:
        for star in chart.symbolic_stars.stars:
            if star.name_zh not in _SIGNIFICANT_STAR_ZH:
                continue
            branches = tuple(pillar_branch[p] for p in star.pillars if p in pillar_branch)
            if branches:
                natal_star_anchors[star.name_zh] = branches

    if not natal_star_anchors:
        return []

    results: list[ImportantDate] = []
    cursor = start
    while cursor <= end:
        day_chart = _day_pillars(cursor)
        day_branch = day_chart.pillars[2].branch  # day pillar branch

        active: list[str] = []
        for name_zh, anchors in natal_star_anchors.items():
            # Star is active today when today's day-branch matches one
            # of the branches the natal star sits on — i.e. the day
            # «touches» the chart at that natal anchor.
            if day_branch in anchors:
                active.append(name_zh)

        if active:
            results.append(
                ImportantDate(
                    date_=cursor,
                    active_stars=tuple(sorted(set(active))),
                    severity=_pick_severity(tuple(active)),
                )
            )
        cursor += timedelta(days=1)

    return results


# Короткие трактовки значимых звёзд для уведомлений (что значит + на что
# обратить внимание). Источник: База/teacher/L5_stars/anastasia_shen_sha_catalog.md.
# Стиль Анастасии: тепло, без восклицаний, без латиницы.
_STAR_MEANING: Final[dict[str, str]] = {
    "天乙贵人": "звезда покровителей — приходят нужные люди и помощь. Хорошо просить поддержку, заводить полезные знакомства, решать вопросы через других.",
    "文昌贵人": "звезда учёбы и ясного ума. Хорошо для договоров, экзаменов, документов, переговоров и любой умственной работы.",
    "天德贵人": "защита и удача свыше — сглаживает конфликты и риски. Благоприятна для важных начинаний и примирений.",
    "月德贵人": "мягкая защита и поддержка дома и семьи. Хорошо для семейных дел, восстановления, спокойных решений.",
    "桃花": "магнетизм и обаяние — вы притягиваете людей и внимание. Хорошо для публичности и знакомств; внимательнее с соблазнами и пустым флиртом.",
    "驿马": "движение и перемены — поездки, переезды, смена обстановки. День дороги и суеты; держите фокус, не распыляйтесь.",
    "华盖": "творчество, уединение, духовность. Хорошо для замысла, учёбы, тишины; тянет побыть одному — это нормально.",
    "将星": "лидерство и управление — легче брать ответственность и вести за собой. Хороший день для руководящих шагов и решительных действий.",
    "羊刃": "резкая сильная энергия — смелость и напор, но и риск перегиба. Внимательнее с острым, техникой, спешкой и резкими словами.",
    "飞刃": "внезапная острая энергия — возможны травмы, конфликты, поспешные решения. День осторожности: не рискуйте телом и не рубите сплеча.",
    "白虎": "напряжение и конфликты, риск ссор и травм. Не вступайте в споры по горячему, будьте аккуратны физически, замедляйтесь.",
}


def _star_label(name_zh: str) -> str:
    key = _NAME_ZH_TO_KEY.get(name_zh)
    if key is None:
        return name_zh
    meta = STAR_META[key]
    return f"{meta.name_zh} {meta.name_ru}"


def _star_lines_with_meaning(active_stars: tuple[str, ...]) -> str:
    """Render each active star as «• 名 Имя — трактовка» (Bug C fix)."""
    lines = []
    for sid in active_stars:
        meaning = _STAR_MEANING.get(sid)
        if meaning:
            lines.append(f"  • {_star_label(sid)} — {meaning}")
        else:
            lines.append(f"  • {_star_label(sid)}")
    return "\n".join(lines)


def _severity_emoji(severity: str) -> str:
    return {"high": "⚠", "medium": "🌟", "low": "✨"}.get(severity, "✨")


_SEVERITY_NOTE: Final[dict[str, str]] = {
    "high": (
        "Это день усиления — будьте внимательнее к решениям, "
        "конфликтам и быстрой реакции. Не вступайте в споры по горячему."
    ),
    "medium": (
        "Это день, когда энергии активируют конкретные сферы "
        "вашей карты. Хороший день для осознанных действий."
    ),
    "low": (
        "Это благоприятный день — Шэнь Ша помощников и развития. "
        "Подходит для важных шагов в выделенных сферах."
    ),
}


def format_important_date_message(
    chart: ChartOutput, important: ImportantDate, *, days_ahead: int
) -> str:
    """Compose a Telegram-ready message for one important date.

    ``days_ahead``:
    - ``2``: «через 2 дня…»
    - ``1``: «завтра…»
    - ``0``: «сегодня…»
    - ``-N``: previous date (used for journal auto-entry)
    """
    if days_ahead == 0:
        when = "Сегодня"
    elif days_ahead == 1:
        when = "Завтра"
    elif days_ahead > 0:
        when = f"Через {days_ahead} дня"
    else:
        when = f"{abs(days_ahead)} дней назад"

    star_lines = _star_lines_with_meaning(important.active_stars)
    emoji = _severity_emoji(important.severity)
    severity_note = _SEVERITY_NOTE[important.severity]

    return (
        f"{emoji} <b>{when} ({important.date_.strftime('%d.%m.%Y')}) — "
        "важная для вашей карты дата</b>\n\n"
        "Активируются звёзды:\n"
        f"{star_lines}\n\n"
        f"{severity_note}\n\n"
        "В день этой даты я напомню записать рефлексию — что прожилось "
        "на этой энергии.\n\n"
        "<i>Это сообщение приходит не чаще одного раза в неделю — "
        "я не хочу заваливать вас уведомлениями.</i>"
    )


def format_important_date_reflection(chart: ChartOutput, important: ImportantDate) -> str:
    """Day-of reflection invite (B2, 2026-06-02): sent ON the important
    date itself (days_ahead==0), separate from the ahead-of-time warning.
    Carries the «📝 Записать рефлексию» button at the handler layer."""
    star_lines = _star_lines_with_meaning(important.active_stars)
    emoji = _severity_emoji(important.severity)
    severity_note = _SEVERITY_NOTE[important.severity]
    return (
        f"{emoji} <b>Сегодня ({important.date_.strftime('%d.%m.%Y')}) — "
        "важная для вашей карты дата</b>\n\n"
        "Активируются звёзды:\n"
        f"{star_lines}\n\n"
        f"{severity_note}\n\n"
        "Как прожили этот день? Запишите рефлексию — что почувствовали "
        "на этой энергии. Можно текстом или голосовым; если пропустите — "
        "я просто отмечу день в дневнике сама."
    )


def render_demo_for_chart(chart: ChartOutput, today: date) -> str:
    """Build a demo message showing what an important-date alert would
    look like for the given chart, picking the next significant date in
    a 30-day window. Used by /start «Демо важных дат» button so the
    user previews the experience before enabling reminders."""
    end = today + timedelta(days=30)
    candidates = find_important_dates_in_range(chart, today, end)
    if not candidates:
        return (
            "За ближайшие 30 дней по этой карте я не нашла «громких» "
            "звёзд для уведомлений. Включите функцию и оставьте — "
            "как только подходящая дата появится, напишу за два дня."
        )
    # Show the highest-severity upcoming.
    candidates.sort(key=lambda d: ({"high": 0, "medium": 1, "low": 2}[d.severity], d.date_))
    chosen = candidates[0]
    days_ahead = (chosen.date_ - today).days
    return format_important_date_message(chart, chosen, days_ahead=days_ahead)
