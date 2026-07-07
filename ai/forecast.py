"""Wave 3b — paid forecast generators (daily + monthly).

Two entry points used by the scheduler (W3c) and by the «buy» handler
(W3d):

- ``generate_daily_forecast(chart, target_date)`` — fires every morning
  at 4 local for a daily-subscriber. ~5 blocks.
- ``generate_monthly_forecast(chart, period_start)`` — either as a bulk
  body or chunked into 4 weekly slices by the scheduler.

Both use the **main LLM** (Qwen3.6 ``interpretation`` intent) — same
budget tier as ``base_interpretation.py``. Forecast is blocky markdown:
each block has a ``## БЛОК N. <title>`` heading so parsing/Telegram-
splitting stays consistent with the rest of the bot.

The generator builds a small ``[FORECAST_CONTEXT]`` payload (карта
рождения + столпы цели + активный такт) inline. It does **not** invoke the
RAG, skill-router, or partner-chart machinery — those are tied to the
interactive consultation flow. Forecast prompts cite chart data
strictly (anti-hallucination) but stay narrative, not factual lookup.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Final

import structlog

from ai.fallback import FallbackResult, chat_with_fallback
from ai.orchestrator import ChatMessage
from ai.prompts import SchoolName, load_base_prompt
from ai.skills import load_skill
from calculator import calculate_chart
from calculator.models import ChartInput, ChartOutput

logger = structlog.get_logger(__name__)

# Block titles in the order the LLM must emit them.
_DAILY_BLOCK_TITLES: Final[dict[int, str]] = {
    1: "Общая энергия дня",
    2: "Что активируется (звёзды и взаимодействия)",
    3: "Благоприятные сферы",
    4: "На что обратить внимание",
    5: "Рекомендации на день",
}

_MONTHLY_BLOCK_TITLES: Final[dict[int, str]] = {
    1: "Общая энергия месяца",
    2: "Главная тема и вызов",
    3: "Возможности (сферы расцвета)",
    4: "Зоны риска",
    5: "По неделям",
    6: "Рекомендации на месяц",
}


@dataclass(frozen=True)
class ForecastResult:
    """Generic forecast envelope — same shape for daily and monthly so
    the scheduler and delivery-recorder don't branch on type."""

    text: str
    """Telegram-ready markdown body. Blocks separated by ``## БЛОК N.``."""
    model: str
    used_fallback: bool
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    latency_ms: int
    trace_id: str


def _chart_at_noon(target: date) -> ChartOutput:
    """Build a synthetic chart for 12:00 UTC on ``target`` so we can
    extract that day's pillars (year/month/day) via the regular
    calculator. Hour pillar is meaningless for forecast purposes and
    we drop it from the rendered context."""
    return calculate_chart(
        ChartInput(
            birth_datetime=datetime.combine(target, time(12, 0)),
            latitude=0.0,
            longitude=0.0,
            tz_offset=0.0,
            gender="male",  # arbitrary — not used in forecast logic
        )
    )


_PILLAR_LABELS: Final[tuple[str, str, str, str]] = ("Год", "Месяц", "День", "Час")
"""Position-to-label map for chart.pillars. ChartOutput.pillars is always
ordered year/month/day/hour — see calculator.pillars.calculate_pillars."""


def _format_chart_for_forecast(chart: ChartOutput) -> str:
    """Compact birth chart block — ~500 chars. Each pillar is labelled
    (Год/Месяц/День/Час) so the LLM knows which one it cites in the
    response and can call it by name — fixes the «丙午 приносит…» dangling
    reference seen in prod 2026-05-22."""
    pillar_lines = [
        f"  {_PILLAR_LABELS[i]}: {p.stem}{p.branch}" for i, p in enumerate(chart.pillars)
    ]
    parts = [
        f"Дневной Мастер: {chart.day_master}",
        "Столпы рождения:",
        *pillar_lines,
    ]
    if chart.element_balance:
        bal = ", ".join(f"{k} {v:.0%}" for k, v in chart.element_balance.items())
        parts.append(f"Баланс стихий: {bal}")
    if chart.luck_pillars and chart.luck_pillars.pillars:
        lp = chart.luck_pillars.pillars[0]
        parts.append(
            f"Текущий такт удачи: {lp.stem}{lp.branch} "
            f"({lp.start_datetime.year}–{lp.end_datetime.year})"
        )
    return "\n".join(parts)


def _format_target_chart(chart: ChartOutput, *, drop_hour: bool = True) -> str:
    """Pillars of the target date/month — drop the hour pillar (it's
    a 12:00 placeholder and would mislead the LLM into spurious
    «час свиньи активирует X» claims).

    Pillars are labelled by position (Год/Месяц/День) so the LLM can
    cite them by name in the response instead of dropping the iero­glyph
    as a dangling subject («丙午 приносит» without saying whose pillar
    that is)."""
    relevant = chart.pillars[:3] if drop_hour else chart.pillars
    pillar_lines = [f"  {_PILLAR_LABELS[i]}: {p.stem}{p.branch}" for i, p in enumerate(relevant)]
    return "Столпы цели:\n" + "\n".join(pillar_lines)


_INLINE_GLOSSARY_RULE = """\
ПРАВИЛО РАСШИФРОВКИ ИЕРОГЛИФОВ (КРИТИЧНО — ЛЮБОЙ ГОЛЫЙ ИЕРОГЛИФ = ОШИБКА):
- При ПЕРВОМ упоминании любого китайского иероглифа или термина в ответе \
обязательно дай русскую расшифровку прямо в скобках формата \
`<b>иероглиф</b> (русский перевод)`.
- Пример: `<b>卯酉冲</b> (столкновение Кролика и Петуха)`, \
`<b>丙午</b> (Бин-У: Огонь Ян над Лошадью)`, `<b>七杀</b> (Семь Убийц — \
энергия давления, как строгий начальник)`, `<b>劫财</b> (Грабитель — \
энергия партнёров-конкурентов)`.
- Если упоминаешь столп цели (`丙午`) — всегда называй ЧТО это за столп \
(год/месяц/день из секции [TARGET_PILLARS]): «Год приносит <b>丙午</b> \
(Бин-У, Огонь Лошади)» вместо «<b>丙午</b> приносит…».
- Не используй угловые скобки 「」 — только HTML-теги."""


_DAILY_INSTRUCTION = f"""\
Дай прогноз на ОДИН день для пользователя в виде пяти блоков, \
в указанном порядке, каждый с заголовком вида `## БЛОК N. Название`.

Структура (используй ровно эти заголовки):
{json.dumps(dict(_DAILY_BLOCK_TITLES.items()), ensure_ascii=False, indent=2)}

Каждый блок: 50-120 слов, связный текст нарративом без буллет-списков. \
Опирайся ТОЛЬКО на данные [BAZI_DATA] (карта рождения) и [TARGET_PILLARS] \
(столпы дня — подписаны по позициям Год/Месяц/День). Сравнивай их через \
10 Божеств, взаимодействия (合沖刑害破), символические звёзды.

ВАЖНО ПО РАЗМЕРУ: суммарно весь прогноз не больше 1800 слов / 3800 \
символов — у Telegram жёсткий лимит 4096 на сообщение. Если выходит \
длиннее, СОКРАЩАЙТЕ блоки до сути, не приписывая «полнее раскрою в \
следующий раз». Цельный короткий ответ лучше обрезанного длинного.

{_INLINE_GLOSSARY_RULE}

Стиль Анастасии: тёплый, проницательный, без `!`, 4-5 эмодзи на ответ \
(🌿🔥⛰⚔️💧 для стихий, ✨ для звёзд, ⏳ для времени, 💡 для рекомендаций, \
☯️ финал). Метафоры из §6 base.md если уместно. Без эзотерической \
вычурности — конкретика по картам."""


_MONTHLY_INSTRUCTION = f"""\
Дай прогноз на ОДИН календарный месяц в виде шести блоков, \
в указанном порядке, каждый с заголовком вида `## БЛОК N. Название`.

Структура (используй ровно эти заголовки):
{json.dumps(dict(_MONTHLY_BLOCK_TITLES.items()), ensure_ascii=False, indent=2)}

Каждый блок: 60-130 слов. БЛОК 5 «По неделям» — 4 короткие абзаца по \
одной на каждую неделю месяца, с конкретной темой недели.

Опирайся ТОЛЬКО на данные [BAZI_DATA] (карта рождения) и [TARGET_PILLARS] \
(столпы — подписаны по позициям). Анализируй через 10 Божеств, \
взаимодействия, активный такт удачи.

ВАЖНО ПО РАЗМЕРУ: суммарно весь прогноз не больше 2200 слов / 7600 \
символов — длинный текст будет разбит на 2 сообщения Telegram, но \
лучше уложиться в одно (3800 символов). Если выходит длиннее, \
СОКРАЩАЙТЕ блоки до сути.

{_INLINE_GLOSSARY_RULE}

Стиль Анастасии: тёплый, без `!`, 4-5 эмодзи на ответ. Метафоры из §6 \
base.md уместно. БЛОК 6 «Рекомендации» — 3-5 конкретных действий, \
не общие фразы."""


def _build_system_prompt(school: SchoolName | None = None) -> str:
    """Forecast персона = base.md (universal Anastasia) + опциональная
    школьная надстройка base_<school>.md + time skill body (forecast-
    specific methodology). Wave 7 Phase 2 ext (2026-05-26) — school
    parameter позволяет подписчику получать дневные/месячные прогнозы
    в стиле выбранной школы (classic / edoha / modern). По умолчанию
    None → grand-fathered подписки получают универсальный base.md.

    Cached because both loaders are LRU-cached themselves; this is
    just a string concat."""
    base = load_base_prompt(school)
    time_skill = load_skill("time").body
    return f"{base}\n\n---\n\n# [SKILL: time]\n\n{time_skill}"


async def generate_daily_forecast(
    *,
    chart: ChartOutput,
    target_date: date,
    trace_id: str | None = None,
    school: SchoolName | None = None,
) -> ForecastResult:
    """One-day forecast for ``target_date``.

    ``school`` (Wave 7 Phase 2 ext) — interpretation school chosen by
    the subscriber. Threaded down from ChartForecastSubscription
    .chosen_school via scheduler/jobs.py. None = legacy неопределённая
    школа → fall back to universal base.md.
    """
    target_chart = _chart_at_noon(target_date)

    user_payload = (
        "[BAZI_DATA] (карта рождения)\n"
        f"{_format_chart_for_forecast(chart)}\n\n"
        f"[TARGET_DATE]\n{target_date.isoformat()}\n\n"
        "[TARGET_PILLARS] (столпы выбранного дня)\n"
        f"{_format_target_chart(target_chart)}\n\n"
        f"[INSTRUCTION]\n{_DAILY_INSTRUCTION}"
    )

    messages = [
        ChatMessage(role="system", content=_build_system_prompt(school)),
        ChatMessage(role="user", content=user_payload),
    ]

    result: FallbackResult = await chat_with_fallback(
        messages=messages,
        temperature=0.55,
        intent="interpretation",
        trace_id=trace_id,
    )
    logger.info(
        "forecast.daily.generated",
        target_date=target_date.isoformat(),
        latency_ms=result.result.latency_ms,
        completion_tokens=result.result.usage.completion_tokens,
        cost_usd=result.result.usage.cost_usd,
        used_fallback=result.used_fallback,
        trace_id=result.result.trace_id,
    )
    return ForecastResult(
        text=result.result.text,
        model=result.result.model,
        used_fallback=result.used_fallback,
        prompt_tokens=result.result.usage.prompt_tokens,
        completion_tokens=result.result.usage.completion_tokens,
        cost_usd=result.result.usage.cost_usd,
        latency_ms=result.result.latency_ms,
        trace_id=result.result.trace_id,
    )


async def generate_monthly_forecast(
    *,
    chart: ChartOutput,
    period_start: date,
    trace_id: str | None = None,
    school: SchoolName | None = None,
) -> ForecastResult:
    """30-day forecast starting at ``period_start``.

    ``school`` (Wave 7 Phase 2 ext) — interpretation school chosen by
    the subscriber. Threaded down from ChartForecastSubscription
    .chosen_school via scheduler/jobs.py.

    The LLM gets pillars for both the first day and the 15th — the
    half-month sample improves the «по неделям» block by anchoring
    energy shifts."""
    target_chart_start = _chart_at_noon(period_start)
    target_chart_mid = _chart_at_noon(period_start + timedelta(days=15))
    period_end = period_start + timedelta(days=29)

    user_payload = (
        "[BAZI_DATA] (карта рождения)\n"
        f"{_format_chart_for_forecast(chart)}\n\n"
        f"[TARGET_MONTH]\n"
        f"С {period_start.isoformat()} по {period_end.isoformat()}\n\n"
        "[TARGET_PILLARS] (1-й день месяца)\n"
        f"{_format_target_chart(target_chart_start)}\n\n"
        "[TARGET_PILLARS_MID] (15-й день месяца)\n"
        f"{_format_target_chart(target_chart_mid)}\n\n"
        f"[INSTRUCTION]\n{_MONTHLY_INSTRUCTION}"
    )

    messages = [
        ChatMessage(role="system", content=_build_system_prompt(school)),
        ChatMessage(role="user", content=user_payload),
    ]

    result: FallbackResult = await chat_with_fallback(
        messages=messages,
        temperature=0.55,
        intent="interpretation",
        trace_id=trace_id,
    )
    logger.info(
        "forecast.monthly.generated",
        period_start=period_start.isoformat(),
        latency_ms=result.result.latency_ms,
        completion_tokens=result.result.usage.completion_tokens,
        cost_usd=result.result.usage.cost_usd,
        used_fallback=result.used_fallback,
        trace_id=result.result.trace_id,
    )
    return ForecastResult(
        text=result.result.text,
        model=result.result.model,
        used_fallback=result.used_fallback,
        prompt_tokens=result.result.usage.prompt_tokens,
        completion_tokens=result.result.usage.completion_tokens,
        cost_usd=result.result.usage.cost_usd,
        latency_ms=result.result.latency_ms,
        trace_id=result.result.trace_id,
    )
