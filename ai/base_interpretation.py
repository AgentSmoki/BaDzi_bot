"""Free-tier 9-block base interpretation of a Bazi chart.

This is the *single* AI artefact every user gets without paying:
nine structured blocks describing the chart's element balance, day
master, life-flow through the generation cycle, ideal partner
profile, strengths, the influence of the current year, plus three
pillar-projection blocks added per Bogdan's spec 2026-05-19 (work
through month pillar, society through year pillar, secret desires
through hour pillar). Per [ADR-006 / monetization plan][monetization]
in vision.mdc, this is always free and is the hook that brings users
back for paid Q&A.

[monetization]: ../.cursor/rules/vision.mdc#L171-L185

Each block ends with a single
``**Чтобы узнать больше, задайте вопрос по этой карте:** «...»``
line — a concrete follow-up question that suggests the natural next
paid Q&A turn. The line stays inside the block body (no separate
Pydantic field) so callers / formatters render it as-is.

Implementation:
1. One ``chat_with_fallback`` call (nine round-trips would cost ~9x
   and run for ~9 minutes on Qwen3.6 thinking).
2. Output is a single markdown document with `## БЛОК N. <title>`
   headings; ``parse_blocks`` splits it back into a structured
   ``BaseInterpretation`` so the bot can render whichever block is
   needed.
3. ``format_for_telegram`` joins the blocks for chat delivery and
   strips the exclamation marks Anastasia must never use.

Tested against mocked LLM output; live validation goes through
[scripts/bench_render.py]-style smoke tests on a known reference
chart.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final

import structlog
from pydantic import BaseModel

from ai.fallback import FallbackResult, chat_with_fallback
from ai.prompts import load_system_prompt
from ai.temporal_context import compose_messages, get_current_bazi
from calculator.models import ChartOutput

logger = structlog.get_logger(__name__)


# ── Block schema ─────────────────────────────────────────────────────────
#
# Six fixed blocks, in this exact order. We surface them as Pydantic
# fields rather than a dict because callers (1.13 chat router, future
# Mini App) read them by name and we want type-checker support.

BLOCK_TITLES: Final[dict[int, str]] = {
    1: "Баланс пяти стихий",
    2: "Господин Дня — личность",
    3: "Реализация по кругу порождения",
    4: "Идеальный партнёр",
    5: "Сильные стороны карты",
    6: "Влияние текущего года",
    7: "Как проявляюсь в работе (столп месяца)",
    8: "Как проявляюсь в обществе (столп года)",
    9: "Тайные желания и предназначение (столп часа)",
}

# Heading regex — tolerant of `## БЛОК 1.`, `## Блок 1:`, `## БЛОК 1 —`,
# `## Block 1.`, etc. Matches the whole heading line so the body
# starts on the next line, not in the middle of the title.
_HEADING_RE: Final = re.compile(
    r"^\s*##\s*(?:БЛОК|Блок|BLOCK|Block)\s*(\d)[^\n]*\n",
    re.MULTILINE,
)


class BaseInterpretation(BaseModel):
    """Nine markdown blocks. Order is fixed; missing blocks come back
    as empty strings so downstream code can rely on every key being
    present. Blocks 7-9 cover the year/month/hour pillar projections
    (work, society, secret desires) per Bogdan's spec 2026-05-19."""

    block_1_balance: str = ""
    block_2_day_master: str = ""
    block_3_realization: str = ""
    block_4_partner: str = ""
    block_5_strengths: str = ""
    block_6_current_year: str = ""
    block_7_in_work: str = ""
    block_8_in_society: str = ""
    block_9_secret_desires: str = ""

    def as_ordered(self) -> list[tuple[int, str, str]]:
        """``[(idx, title, body), ...]`` for templates / tests."""
        return [
            (1, BLOCK_TITLES[1], self.block_1_balance),
            (2, BLOCK_TITLES[2], self.block_2_day_master),
            (3, BLOCK_TITLES[3], self.block_3_realization),
            (4, BLOCK_TITLES[4], self.block_4_partner),
            (5, BLOCK_TITLES[5], self.block_5_strengths),
            (6, BLOCK_TITLES[6], self.block_6_current_year),
            (7, BLOCK_TITLES[7], self.block_7_in_work),
            (8, BLOCK_TITLES[8], self.block_8_in_society),
            (9, BLOCK_TITLES[9], self.block_9_secret_desires),
        ]


@dataclass(frozen=True)
class InterpretationResult:
    """Wraps the parsed interpretation with the raw response and
    telemetry — handy for the /admin debug screen and Consultation
    persistence in 1.13."""

    interpretation: BaseInterpretation
    raw_text: str
    model: str
    used_fallback: bool
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float
    latency_ms: int
    trace_id: str


# ── Generation ───────────────────────────────────────────────────────────


_INSTRUCTION = """\
Дай базовую интерпретацию карты пользователя в виде ровно девяти блоков, \
в указанном порядке, каждый с заголовком вида `## БЛОК N. Название`.

Структура блоков (используй ровно эти заголовки):
## БЛОК 1. Баланс пяти стихий
## БЛОК 2. Господин Дня — личность
## БЛОК 3. Реализация по кругу порождения
## БЛОК 4. Идеальный партнёр
## БЛОК 5. Сильные стороны карты
## БЛОК 6. Влияние текущего года
## БЛОК 7. Как проявляюсь в работе (столп месяца)
## БЛОК 8. Как проявляюсь в обществе (столп года)
## БЛОК 9. Тайные желания и предназначение (столп часа)

Содержание блоков 7-9:
- **БЛОК 7 (столп месяца):** рабочий стиль, амбиции, как клиент проявляется \
в деле и карьере. Опирайся на ствол и ветвь МЕСЯЧНОГО столпа, на 10 Божеств \
к ДМ из этого столпа, на структуру карты (格局), которая обычно определяется \
именно по месячному столпу.
- **БЛОК 8 (столп года):** социальный образ, общественная роль, как клиент \
проявляется во внешнем мире, для окружения, в социуме. Опирайся на ствол \
и ветвь ГОДОВОГО столпа и его 10 Божеств к ДМ.
- **БЛОК 9 (столп часа):** тайные желания, истинное предназначение, чего \
хочется когда никто не видит, наследие. Опирайся на ствол и ветвь \
ЧАСОВОГО столпа и его 10 Божеств к ДМ. Если в [BAZI_DATA] часовой столп \
выглядит как полдень-fallback (час 午 при отсутствии явного указания на \
точное время), мягко обозначь это — «время рождения не уточнено, поэтому \
этот блок ориентировочный».

Каждый блок: 100-180 слов, связный текст без буллет-списков. \
Опирайся ТОЛЬКО на данные карты, без выдумок. \
Не ссылайся на типовые примеры из обучения, только на эту конкретную карту. \
Сохраняй стиль Анастасии: тёплый, проницательный, без восклицательных знаков, \
без эзотерической вычурности.

ВАЖНО: в КОНЦЕ каждого из девяти блоков добавь отдельной строкой \
follow-up вопрос. Формат строго такой (HTML-теги <b>, <u>, <code> \
обязательны — клиент в Telegram нажмёт на блок <code> чтобы \
скопировать вопрос):

<b><u>Чтобы узнать больше, задайте вопрос по этой карте:</u></b>
<code>один конкретный вопрос, раскрывающий тему блока глубже</code>

Пример строки для блока 4 (Идеальный партнёр):
<b><u>Чтобы узнать больше, задайте вопрос по этой карте:</u></b>
<code>Какой типаж партнёра мне максимально подходит и где его искать?</code>

Follow-up должен быть КОНКРЕТНЫМ (не «расскажи больше»), коротким (10-20 слов), \
и явно вытекать из содержания блока. Внутри <code>…</code> вопрос пишется \
БЕЗ кавычек и без ёлочек — это plain текст для копирования."""


async def generate_base_interpretation(
    *,
    chart: ChartOutput,
    now_chart: ChartOutput | None = None,
    trace_id: str | None = None,
) -> InterpretationResult:
    """Run the 6-block interpretation against the configured primary
    model with Claude fallback. Always includes the current Bazi
    block so block 6 ("influence of the current year") is grounded."""
    snapshot = now_chart or get_current_bazi()
    system = load_system_prompt()

    messages = compose_messages(
        system_prompt=system,
        chart=chart,
        question=_INSTRUCTION,
        include_temporal=True,
        now_chart=snapshot,
    )

    out: FallbackResult = await chat_with_fallback(
        messages=messages,
        # Lower temperature than chat — interpretation must be stable
        # across re-rolls; we don't want the same chart described in
        # contradictory ways on retry.
        temperature=0.5,
        # 6 blocks × 100-180 words ≈ 3-5k output tokens. ``interpretation``
        # intent gives ratio 0.4 — plenty of headroom on Qwen3.6 (262k)
        # and Claude (200k).
        intent="interpretation",
        trace_id=trace_id,
    )
    parsed = parse_blocks(out.result.text)
    logger.info(
        "base_interpretation.generated",
        used_fallback=out.used_fallback,
        latency_ms=out.result.latency_ms,
        completion_tokens=out.result.usage.completion_tokens,
        cost_usd=out.result.usage.cost_usd,
        blocks_present=sum(1 for _, _, body in parsed.as_ordered() if body.strip()),
        trace_id=out.result.trace_id,
    )
    return InterpretationResult(
        interpretation=parsed,
        raw_text=out.result.text,
        model=out.result.model,
        used_fallback=out.used_fallback,
        prompt_tokens=out.result.usage.prompt_tokens,
        completion_tokens=out.result.usage.completion_tokens,
        cost_usd=out.result.usage.cost_usd,
        latency_ms=out.result.latency_ms,
        trace_id=out.result.trace_id,
    )


# ── Parsing ──────────────────────────────────────────────────────────────


def parse_blocks(text: str) -> BaseInterpretation:
    """Split the LLM markdown into six blocks by ``## БЛОК N`` heading.

    Tolerant: blocks can arrive out of order, with extra whitespace,
    or with mild punctuation variation in the heading. Anything before
    the first heading is dropped. Missing blocks come back as empty
    strings so the downstream renderer can either skip them or show
    a placeholder.
    """
    matches = list(_HEADING_RE.finditer(text))
    if not matches:
        # Fallback: no headings at all — stuff the whole text into
        # block 1 so it isn't lost. Caller can decide whether to
        # treat that as an error.
        logger.warning("base_interpretation.no_headings", text_len=len(text))
        return BaseInterpretation(block_1_balance=text.strip())

    bodies: dict[int, str] = {}
    for i, m in enumerate(matches):
        idx = int(m.group(1))
        body_start = m.end()
        body_end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[body_start:body_end].strip()
        bodies[idx] = body

    return BaseInterpretation(
        block_1_balance=bodies.get(1, ""),
        block_2_day_master=bodies.get(2, ""),
        block_3_realization=bodies.get(3, ""),
        block_4_partner=bodies.get(4, ""),
        block_5_strengths=bodies.get(5, ""),
        block_6_current_year=bodies.get(6, ""),
        block_7_in_work=bodies.get(7, ""),
        block_8_in_society=bodies.get(8, ""),
        block_9_secret_desires=bodies.get(9, ""),
    )


# ── Telegram formatting (task 1.10.8) ───────────────────────────────────


def format_for_telegram(
    interp: BaseInterpretation,
    *,
    chart_label: str | None = None,
) -> str:
    """Compose the six blocks into a single Telegram message.

    - Drops empty blocks (so a partial generation still renders cleanly)
    - Strips ``!`` per Anastasia's stylebook (an upstream guardrail —
      the prompt forbids it, but we don't trust the LLM blindly)
    - Adds the chart label to the header so the user knows which
      chart the interpretation belongs to
    """
    lines: list[str] = []
    if chart_label:
        lines.append(f"<b>Базовая интерпретация · {chart_label}</b>")
    else:
        lines.append("<b>Базовая интерпретация</b>")
    lines.append("")
    for idx, title, body in interp.as_ordered():
        if not body.strip():
            continue
        lines.append(f"<b>{idx}. {title}</b>")
        lines.append(_strip_exclaim(body))
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _strip_exclaim(text: str) -> str:
    """Replace ``!`` with ``.`` — Anastasia's character forbids
    exclamation marks, but the LLM occasionally slips them in despite
    the system-prompt instruction."""
    return text.replace("!", ".")
