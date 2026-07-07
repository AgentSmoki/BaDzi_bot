"""Render the calendar-selection block for the LLM payload.

After the calculator scores days in a date range against the user's
natal chart, this module formats top/bottom candidates as a markdown
table the LLM can cite verbatim. Lives in ``ai/`` (not ``calculator/``)
because formatting is a presentation concern — the calculator returns
neutral ``ScoredDay`` objects, this module decides what the LLM sees.

The block is wrapped in ``[CALENDAR_SELECTION]...[/CALENDAR_SELECTION]``
tags so the LLM treats it as data-to-cite (same protocol as
``[BAZI_DATA]`` from task 2.2.5). The instruction prefix in
``ai/prompts/__init__.py`` already tells the model to quote tagged
data dossiers verbatim — calendar inherits that contract.
"""

from __future__ import annotations

from calculator.calendar_select import (
    EVENT_TYPE_RU,
    EventType,
    ScoredDay,
)


def render_calendar_block(
    *,
    top: list[ScoredDay],
    bottom: list[ScoredDay],
    event_type: EventType | None,
    start_iso: str,
    end_iso: str,
) -> str:
    """Format ranked dates as a structured markdown block.

    Top section lists the best days with rationale; bottom lists days
    to avoid. The LLM is expected to cite specific dates with their
    pillar (e.g. "24 июня (день 戊午)") rather than make up timing.
    """
    event_label = EVENT_TYPE_RU.get(event_type) if event_type else "Общий благоприятный день"
    lines = [
        f"**Выбор даты (择日) для события: {event_label}**",
        f"Диапазон поиска: {start_iso} — {end_iso} "
        f"({len(top) + len(bottom)} оценок ниже, "
        f"топ {len(top)} благоприятных + {len(bottom)} нежелательных).",
        "",
        f"**ТОП-{len(top)} благоприятных дней:**",
    ]
    if top:
        lines.append("| Дата | Столп дня | Score | Ключевые факторы |")
        lines.append("|---|---|---|---|")
        for sd in top:
            factors_short = "; ".join(sd.factors[:3]) if sd.factors else "—"
            if len(sd.factors) > 3:
                factors_short += f" (+{len(sd.factors) - 3} ещё)"
            lines.append(
                f"| {sd.pillar.date.isoformat()} | "
                f"{sd.day_pillar_str} | "
                f"{sd.score:+.1f} | "
                f"{factors_short} |"
            )
    else:
        lines.append("_(нет ни одного благоприятного дня в диапазоне)_")
    lines.append("")
    lines.append(f"**ТОП-{len(bottom)} нежелательных дней (избегать):**")
    if bottom:
        lines.append("| Дата | Столп дня | Score | Почему избегать |")
        lines.append("|---|---|---|---|")
        for sd in bottom:
            factors_short = "; ".join(sd.factors[:3]) if sd.factors else "—"
            if len(sd.factors) > 3:
                factors_short += f" (+{len(sd.factors) - 3} ещё)"
            lines.append(
                f"| {sd.pillar.date.isoformat()} | "
                f"{sd.day_pillar_str} | "
                f"{sd.score:+.1f} | "
                f"{factors_short} |"
            )
    else:
        lines.append("_(в диапазоне нет дней с явно негативной оценкой)_")
    return "\n".join(lines)
