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

from ai.orchestrator import ChatMessage
from calculator import calculate_chart
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
    return "\n".join(parts)


def render_temporal_block(now_chart: ChartOutput, *, when: datetime | None = None) -> str:
    """Render the *current moment* as a Bazi snapshot the LLM can
    diff against the user's natal chart. Includes the calendar
    timestamp explicitly so the model doesn't have to guess what
    "now" means."""
    label_dt = (when or datetime.now(UTC)).strftime("%Y-%m-%d %H:%M UTC")
    pillars_summary = " · ".join(_format_pillar(p.stem, p.branch) for p in now_chart.pillars)
    return "\n".join(
        [
            f"**Текущий момент ({label_dt})**",
            f"- Дневной Хозяин дня: {now_chart.day_master}",
            f"- Столпы (Y·M·D·H): {pillars_summary}",
        ]
    )


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
) -> list[ChatMessage]:
    """Build the final ``messages`` list for the orchestrator.

    Order:
    1. system (Anastasia persona)
    2. cached history (oldest → newest, from 1.8.4)
    3. one fresh user message containing the chart, optionally the
       "now" block, and the question

    Putting the chart inside the *current* user turn (instead of as a
    separate system message) keeps the LLM aware that the chart is
    what the user is asking *about*, not background trivia. History
    is preserved verbatim so the LLM can refer back to earlier
    answers.
    """
    chart_block = render_chart_block(chart)
    if include_temporal:
        snapshot = now_chart or get_current_bazi()
        temporal_block = render_temporal_block(snapshot)
        body = f"{chart_block}\n\n{temporal_block}\n\nВопрос: {question}"
    else:
        body = f"{chart_block}\n\nВопрос: {question}"

    out: list[ChatMessage] = [ChatMessage(role="system", content=system_prompt)]
    if history:
        out.extend(history)
    out.append(ChatMessage(role="user", content=body))
    return out
