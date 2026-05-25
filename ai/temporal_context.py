"""Build the markdown payload that goes to the LLM as the user message.

Three concerns wrapped here:
1. Render a ``ChartOutput`` as a compact markdown block — the same
   layout we hand-tuned in the live demo (12.09.1999 reference). LLM
   reads this in 200-300 tokens and can quote individual rows back
   verbatim.
2. Optionally append a *current* Bazi block (year/month/day/hour
   pillars for "now") when the router (1.8.3) flags the question as
   temporal. Without this the LLM has no reliable anchor for "this
   year", "right now", or "the next decade".
3. Glue user history (1.8.4) and the chart block into the final
   ``messages`` list passed to ``chat`` / ``chat_with_fallback``.

The current-Bazi computation reuses ``calculate_chart`` directly —
no separate astronomical pipeline. Coordinates default to Moscow
(55.75 N, 37.62 E, UTC+3) since "now" is mostly used for Russia-
based clients; callers can override per-user if they want true-solar-
time accuracy on their longitude.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Final

from ai.calendar_context import render_calendar_block
from ai.orchestrator import ChatMessage
from ai.prompts import get_instruction_prefix
from ai.rag import load_knowledge_for_question
from ai.rag.retrieve import SchoolFilter
from ai.skills import SkillSpec
from calculator import calculate_chart
from calculator.calendar_select import ScoredDay
from calculator.models import ChartInput, ChartOutput

# Default location for "current Bazi" computations: Moscow. Bazi day
# pillar is highly sensitive to longitude (TST shifts ~4 min per
# degree), but unless the user has explicitly set a city, Moscow is
# a reasonable mid-Russia default that keeps the "current year" and
# "current month" pillars stable for the whole country.
DEFAULT_NOW_LATITUDE: Final = 55.7558
DEFAULT_NOW_LONGITUDE: Final = 37.6173
DEFAULT_NOW_TZ_OFFSET: Final = 3.0  # MSK, no DST since 2011


def _format_pillar(stem: str, branch: str) -> str:
    return f"{stem}{branch}"


def render_chart_block(chart: ChartOutput) -> str:
    """Render a ChartOutput as the markdown block we feed the LLM.

    Mirrors the format used in the live demo so the LLM sees a stable
    schema across requests. Hidden stems / ten gods print as
    ``year: 乙`` lines — short enough to keep the prompt tight, named
    enough that the model can quote them.

    Includes natal symbolic stars (神煞) since 2.2.3 — the calculator
    detects 60+ classical stars, and Анастасия needs to cite them
    by name (with category + source) so users like Bogdan who feel
    a particular star activating today get a grounded answer.
    """
    pillars_summary = " · ".join(_format_pillar(p.stem, p.branch) for p in chart.pillars)
    hidden = "\n".join(
        f"  - {name}: {' / '.join(stems)}" for name, stems in chart.hidden_stems.items()
    )
    ten_gods = "\n".join(f"  - {name}: {' / '.join(gods)}" for name, gods in chart.ten_gods.items())
    balance = ", ".join(
        f"{element} {pct * 100:.0f}%" for element, pct in chart.element_balance.items()
    )
    luck_lines: list[str] = []
    if chart.luck_pillars and chart.luck_pillars.pillars:
        for lp in chart.luck_pillars.pillars[:6]:
            luck_lines.append(
                f"  - {lp.start_age:.1f} лет "
                f"({lp.start_datetime.year}–{lp.end_datetime.year}): "
                f"{_format_pillar(lp.stem, lp.branch)}"
            )

    parts = [
        "**Бацзы карта**",
        f"- Дневной Хозяин (日主): {chart.day_master}",
        "",
        f"**Четыре столпа (Y·M·D·H):** {pillars_summary}",
        "",
        "**Скрытые стволы:**",
        hidden,
        "",
        "**10 Богов:**",
        ten_gods,
        "",
        f"**Баланс пяти стихий:** {balance}",
    ]
    if luck_lines:
        parts.append("")
        parts.append("**Ближайшие столпы удачи:**")
        parts.extend(luck_lines)
    stars_block = _render_natal_stars_block(chart)
    if stars_block:
        parts.append("")
        parts.append(stars_block)
    return "\n".join(parts)


def _render_natal_stars_block(chart: ChartOutput) -> str:
    """Format detected natal Шэнь Ша as a sorted, grouped markdown list.

    Ordering: auspicious first → mixed → inauspicious, then by category
    inside each nature group. Within a category, stars are sorted by
    canonical Chinese name so the same chart always serializes to the
    same string (important for prompt caching and snapshot tests).

    Empty output (no stars detected) returns an empty string — caller
    skips the section so the prompt doesn't carry a stub heading.
    """
    if chart.symbolic_stars is None or not chart.symbolic_stars.stars:
        return ""
    nature_order = {"auspicious": 0, "mixed": 1, "inauspicious": 2}
    sorted_stars = sorted(
        chart.symbolic_stars.stars,
        key=lambda s: (nature_order.get(s.nature, 9), s.category, s.name_zh),
    )
    lines = ["**Врождённые звёзды (神煞):**"]
    for s in sorted_stars:
        pillars_str = "/".join(s.pillars)
        lines.append(
            f"  - {s.name_zh} {s.name_ru} "
            f"({s.category}, {s.nature}, столбы: {pillars_str}, источник: {s.source})"
        )
    return "\n".join(lines)


def render_temporal_block(
    now_chart: ChartOutput,
    *,
    when: datetime | None = None,
    natal_chart: ChartOutput | None = None,
) -> str:
    """Render the *current moment* as a Bazi snapshot the LLM can
    diff against the user's natal chart. Includes the calendar
    timestamp explicitly so the model doesn't have to guess what
    "now" means.

    When ``natal_chart`` is supplied, also computes:
    - Active stars on the "now" pillars (separate from natal stars).
    - Resonances: natal branches that 合 (combine) or 冲 (clash) with
      a current pillar branch — these are the days Bogdan literally
      *feels* (e.g. 白虎 in his hour pillar 亥 activates on day 寅 via
      寅亥合 from today, 2026-05-16).
    """
    label_dt = (when or datetime.now(UTC)).strftime("%Y-%m-%d %H:%M UTC")
    pillars_summary = " · ".join(_format_pillar(p.stem, p.branch) for p in now_chart.pillars)
    parts = [
        f"**Текущий момент ({label_dt})**",
        f"- Дневной Хозяин дня: {now_chart.day_master}",
        f"- Столпы (Y·M·D·H): {pillars_summary}",
    ]
    now_stars_block = _render_now_stars_block(now_chart)
    if now_stars_block:
        parts.append("")
        parts.append(now_stars_block)
    if natal_chart is not None:
        resonance_block = _render_resonance_block(natal_chart, now_chart)
        if resonance_block:
            parts.append("")
            parts.append(resonance_block)
    return "\n".join(parts)


# ── Resonance tables (六合 / 六冲) ────────────────────────────────────────
#
# Embedded here as small constants rather than imported from
# calculator.interactions because we only need the *direct* branch-pair
# tests, not the full 9-interaction matrix. Keeps temporal_context
# self-contained and trivially testable.
_SIX_HARMONIES: dict[str, str] = {
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
_SIX_CLASHES: dict[str, str] = {
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


def _render_now_stars_block(now_chart: ChartOutput) -> str:
    """Stars active on the current moment's pillars. Same format as
    natal but headlined separately so Анастасия doesn't conflate
    transient activations with the user's permanent natal stars."""
    if now_chart.symbolic_stars is None or not now_chart.symbolic_stars.stars:
        return ""
    nature_order = {"auspicious": 0, "mixed": 1, "inauspicious": 2}
    sorted_stars = sorted(
        now_chart.symbolic_stars.stars,
        key=lambda s: (nature_order.get(s.nature, 9), s.category, s.name_zh),
    )
    lines = ["**Активные звёзды сегодня (на столпах текущего момента):**"]
    for s in sorted_stars:
        lines.append(f"  - {s.name_zh} {s.name_ru} ({s.category}, {s.nature})")
    return "\n".join(lines)


def _render_resonance_block(natal: ChartOutput, now: ChartOutput) -> str:
    """Detect 六合 / 六冲 between natal pillar branches and current
    moment pillar branches. These are the activations that make a
    user *feel* a natal star — e.g. 白虎 in natal hour pillar 亥 lights
    up on a day where 寅 appears (寅亥合)."""
    natal_branches = [(p.branch, p.name) for p in natal.pillars]
    now_branches = [(p.branch, p.name) for p in now.pillars]
    hits: list[str] = []
    for nb, n_name in natal_branches:
        for cb, c_name in now_branches:
            if _SIX_HARMONIES.get(nb) == cb:
                hits.append(
                    f"  - 六合 (гармония): ветвь рождения {nb} ({n_name}) ↔ "
                    f"текущая {cb} ({c_name}) → активирует столп {n_name}"
                )
            elif _SIX_CLASHES.get(nb) == cb:
                hits.append(
                    f"  - 六冲 (столкновение): ветвь рождения {nb} ({n_name}) ↔ "
                    f"текущая {cb} ({c_name}) → возмущает столп {n_name}"
                )
    if not hits:
        return ""
    return "\n".join(["**Резонансы карты рождения с текущим моментом:**", *hits])


def get_current_bazi(
    *,
    when: datetime | None = None,
    latitude: float = DEFAULT_NOW_LATITUDE,
    longitude: float = DEFAULT_NOW_LONGITUDE,
    tz_offset: float = DEFAULT_NOW_TZ_OFFSET,
) -> ChartOutput:
    """Calculate the Bazi pillars for ``when`` (default: now) at the
    given location. Default is Moscow.

    The calculator's ``ChartInput`` expects local civil time — we
    convert the (typically UTC-aware) ``when`` to local time at
    ``tz_offset`` before passing it in. ``early_rat=False`` matches
    the bot's default school.
    """
    moment_utc = (when or datetime.now(UTC)).astimezone(UTC)
    moment_local_naive = (moment_utc + timedelta(hours=tz_offset)).replace(tzinfo=None)
    inp = ChartInput(
        birth_datetime=moment_local_naive,
        latitude=latitude,
        longitude=longitude,
        tz_offset=tz_offset,
        early_rat=False,
    )
    return calculate_chart(inp)


def compose_messages(
    *,
    system_prompt: str,
    chart: ChartOutput,
    question: str,
    history: list[ChatMessage] | None = None,
    include_temporal: bool = False,
    now_chart: ChartOutput | None = None,
    calendar_top: list[ScoredDay] | None = None,
    calendar_bottom: list[ScoredDay] | None = None,
    calendar_event_type: str | None = None,
    calendar_start_iso: str | None = None,
    calendar_end_iso: str | None = None,
    # Wave 6 / ADR-010 — skill-router additions. All optional so legacy
    # callers (base_interpretation) keep working unchanged.
    skill_spec: SkillSpec | None = None,
    partner_chart: ChartOutput | None = None,
    clarifications: list[tuple[str, str]] | None = None,
    concept_hints: list[str] | None = None,
    # W5e-MVP (2026-05-21) — summaries of the client's personal
    # master-meeting transcripts, injected as a high-authority block
    # for Anastasia to weave in.
    master_meeting_summaries: list[str] | None = None,
    # Wave 7 Phase 5 — restrict KuzuDB retrieval to nodes belonging to
    # the user's chosen interpretation school (+ universal). ``None``
    # falls through with no filter, preserving the legacy behaviour
    # for callers that don't yet thread school (forecast.py).
    school: str | None = None,
) -> list[ChatMessage]:
    """Build the final ``messages`` list for the orchestrator.

    Section order in the user-message body:

    1. ``[BAZI_DATA]``         — natal chart, stars, luck pillars
    2. ``[PARTNER_CHART]``     — Wave 6, when relationships skill linked
       a partner chart via ``charts.partner_chart_id``
    3. ``[CURRENT_MOMENT]``    — today's pillars + resonances (temporal Qs)
    4. ``[CALENDAR_SELECTION]``— pre-scored top/bottom dates (date Qs)
    5. ``[SKILL]``             — Wave 6, body of selected skill's .md file
    6. ``[CLARIFICATIONS]``    — Wave 6, accumulated Q→A from clarifying loop
    7. ``[KNOWLEDGE]``         — RAG hits, augmented by ``concept_hints``
    8. ``[INSTRUCTIONS]``      — strict-cite + 4-section output rules
    9. ``[QUESTION]``          — the user's text

    Structured tags let the LLM reason about scope — «эти проценты —
    только то что внутри [BAZI_DATA]» — which measurably reduces
    fabrication per research 2026-05-16. History is preserved verbatim
    so the LLM can refer back to earlier answers.
    """
    # [TODAY] — текущая дата всегда инжектится в первой секции, ВНЕ
    # зависимости от того определил ли router temporal-intent. Без
    # этого LLM (training cutoff Jan 2026) при вопросах про «ближайшие
    # благоприятные дни» / «когда мне можно» может выдать прошедшие
    # даты «из обучения». См. инцидент с @S_Kate2011 2026-05-25.
    today = datetime.now(UTC).date()
    weekday_ru = [
        "понедельник",
        "вторник",
        "среда",
        "четверг",
        "пятница",
        "суббота",
        "воскресенье",
    ][today.weekday()]
    today_block = (
        f"[TODAY]\n"
        f"Сегодня: {today.isoformat()} ({weekday_ru}).\n"
        f"Никогда не предлагай прошедшие даты (раньше сегодня) — только\n"
        f"сегодня и будущие. Если клиент спросил «когда лучше», диапазон\n"
        f"всегда начинается с сегодня или позже.\n"
        f"[/TODAY]"
    )
    chart_block = render_chart_block(chart)
    sections = [today_block, f"[BAZI_DATA]\n{chart_block}\n[/BAZI_DATA]"]
    if partner_chart is not None:
        partner_block = render_chart_block(partner_chart)
        sections.append(f"[PARTNER_CHART]\n{partner_block}\n[/PARTNER_CHART]")
    if include_temporal:
        snapshot = now_chart or get_current_bazi()
        temporal_block = render_temporal_block(snapshot, natal_chart=chart)
        sections.append(f"[CURRENT_MOMENT]\n{temporal_block}\n[/CURRENT_MOMENT]")
    if calendar_top is not None and calendar_bottom is not None:
        # event_type is Literal in calendar_select; we accept str here
        # and let the renderer tolerate any string.
        cal_block = render_calendar_block(
            top=calendar_top,
            bottom=calendar_bottom,
            event_type=calendar_event_type,  # type: ignore[arg-type]
            start_iso=calendar_start_iso or "",
            end_iso=calendar_end_iso or "",
        )
        sections.append(f"[CALENDAR_SELECTION]\n{cal_block}\n[/CALENDAR_SELECTION]")
    if skill_spec is not None:
        sections.append(f"[SKILL: {skill_spec.name}]\n{skill_spec.body}\n[/SKILL]")
    if clarifications:
        clar_lines = []
        for q, a in clarifications:
            clar_lines.append(f"- Q: {q}")
            clar_lines.append(f"  A: {a}")
        sections.append("[CLARIFICATIONS]\n" + "\n".join(clar_lines) + "\n[/CLARIFICATIONS]")
    if master_meeting_summaries:
        notes_body = "\n\n---\n\n".join(s.strip() for s in master_meeting_summaries if s.strip())
        if notes_body:
            sections.append(
                "[PERSONAL_MASTER_NOTES]\n"
                "Личные записи клиента с мастером (учитывайте как высший "
                "приоритет глубинного знания о карте, особенно когда мастер "
                "проговорил конкретные акценты и рекомендации):\n\n"
                f"{notes_body}\n"
                "[/PERSONAL_MASTER_NOTES]"
            )
    # Wave 7 Phase 5 — narrow ``school`` into the typed Literal accepted
    # by the RAG layer. Unknown values silently fall through (the RAG
    # function tolerates ``None`` = no filter).
    school_filter: SchoolFilter | None = (
        school  # type: ignore[assignment]
        if school in {"classic", "edoha", "modern"}
        else None
    )
    knowledge_block = load_knowledge_for_question(
        question, concept_hints=concept_hints, school=school_filter
    )
    if knowledge_block:
        sections.append(f"[KNOWLEDGE]\n{knowledge_block}\n[/KNOWLEDGE]")
    sections.append(get_instruction_prefix())
    sections.append(f"[QUESTION]\n{question}\n[/QUESTION]")
    body = "\n\n".join(sections)

    out: list[ChatMessage] = [ChatMessage(role="system", content=system_prompt)]
    if history:
        out.extend(history)
    out.append(ChatMessage(role="user", content=body))
    return out
