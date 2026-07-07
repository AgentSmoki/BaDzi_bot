"""System prompts as code-first loadable resources.

Prompts are .md files alongside this module so version control sees
diffs as readable text, but consumers always load via ``get_prompt``
to keep file paths off call sites.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Final, Literal

_PROMPTS_DIR: Final = Path(__file__).resolve().parent

ANASTASIA_SYSTEM: Final = "anastasia_system"
ANASTASIA_BASE: Final = "base"
SKILL_ROUTER_SYSTEM: Final = "skill_router_system"
BIRTH_EXTRACT_SYSTEM: Final = "birth_extract_system"

# Wave 7 Phase 2 — three parallel schools layered over `base.md`.
# Each file is methodology-only (no identity/glossary duplication); `base.md`
# stays the universal core. `compose_messages(school=...)` concatenates
# base + school layer + skill body so the LLM gets one coherent system
# prompt per consultation turn.
SchoolName = Literal["classic", "edoha", "modern"]
"""Three coexisting interpretation traditions. Adding a fourth = new
``Literal`` value + ``ai/prompts/base_<name>.md`` + UI button."""

_SCHOOL_FILE_MAP: Final[dict[SchoolName, str]] = {
    "classic": "base_classic",
    "edoha": "base_edoha",
    "modern": "base_modern",
}


@lru_cache(maxsize=8)
def get_prompt(name: str) -> str:
    """Return the contents of ``ai/prompts/<name>.md``.

    Cached: prompts are static at runtime, the 68 KB Anastasia file
    being the dominant case. Pass a stable identifier (``ANASTASIA_SYSTEM``
    constant) instead of a hand-typed string at call sites.
    """
    path = _PROMPTS_DIR / f"{name}.md"
    if not path.is_file():
        raise FileNotFoundError(f"prompt not found: {path}")
    return path.read_text(encoding="utf-8")


def load_system_prompt() -> str:
    """Legacy: full 39 KB Anastasia persona (anastasia_system.md).
    Used in pre-skill-router flow. After feature flag
    ``skill_router_enabled`` flips on (Phase 6), callers switch to
    ``load_base_prompt`` + injected [SKILL] section."""
    return get_prompt(ANASTASIA_SYSTEM)


def load_base_prompt(school: SchoolName | None = None) -> str:
    """Slimmed-down base prompt (~12 KB) used by the skill-router flow.
    Contains persona + style + glossary + ethics + metaphor bank, but
    defers domain-specific methodology to per-skill prompts injected
    via the [SKILL] section by ``ai.temporal_context.compose_messages``.

    Wave 7 Phase 2: optional ``school`` argument concatenates the
    methodology overlay (``base_classic.md`` / ``base_edoha.md`` /
    ``base_modern.md``) after the universal core. Returns the same
    string identity across calls for cache friendliness — cache keyed
    on ``school`` so each variant is loaded once per process.

    ``school=None`` returns just ``base.md`` — backward-compat for
    ``ai/forecast.py`` and ``ai/base_interpretation.py`` which run
    outside the interactive consultation flow and don't know which
    school the user picked."""
    return _load_base_prompt_cached(school)


@lru_cache(maxsize=4)
def _load_base_prompt_cached(school: SchoolName | None) -> str:
    """Implementation backing ``load_base_prompt``. Separate function
    so the public API stays kwargless-friendly while still benefiting
    from positional ``lru_cache`` keying."""
    base = get_prompt(ANASTASIA_BASE)
    if school is None:
        return base
    school_body = get_prompt(_SCHOOL_FILE_MAP[school])
    return f"{base}\n\n---\n\n{school_body}"


def load_skill_router_prompt() -> str:
    """Template prompt for the fast skill-router LLM (Phase 2).

    The prompt contains a single ``{catalog}`` placeholder; the
    caller (``ai.skill_router.select_skill``) substitutes the rendered
    skill catalog before sending. All JSON braces in the prompt use
    ``{{`` / ``}}`` to survive ``str.format()``."""
    return get_prompt(SKILL_ROUTER_SYSTEM)


def load_birth_extract_prompt() -> str:
    """Prompt for the smart birth-data extractor (Wave 2, ai.text_extract).
    No placeholders — caller passes the user text as the user message."""
    return get_prompt(BIRTH_EXTRACT_SYSTEM)


# ── Anti-hallucination instruction prefix (task 2.2.5) ────────────────────
#
# Short, dense instruction prepended to every user-message right before
# the [QUESTION] tag. Sourced from research findings 2026-05-16
# (doc/research/anastasia_prompt_optimization_2026-05-16.md): structured
# tags + strict-cite + 4-section output without rewriting the 39 KB
# persona prompt. The persona file is unchanged — this layer encodes
# *behaviour-shaping rules* the persona prompt doesn't enforce.
#
# Why a prefix and not part of the system prompt: prefixes ride on the
# user-message which is dynamic anyway, so they don't break prompt
# caching of the stable 39 KB persona on caching-aware providers
# (Anthropic). They also let us A/B these rules without rebuilding
# the persona prompt or shipping a new image.
INSTRUCTION_PREFIX: Final = "\n".join(
    [
        "[INSTRUCTIONS]",
        "Перед ответом сделай два внутренних шага:",
        "1. Извлеки данные из блоков [BAZI_DATA] и [CURRENT_MOMENT]",
        "   и проверь, что цитаты дословны.",
        "2. Применяй правила Бацзы к этим данным, не выдумывая",
        "   новых чисел / звёзд / дат.",
        "",
        "Строгие правила:",
        "- Все проценты стихий, имена звёзд, даты и столпы бери ТОЛЬКО",
        "  из блоков [BAZI_DATA] и [CURRENT_MOMENT]. Не выдумывай числа.",
        "- Если запрашиваемых данных нет — честно скажи «в исходных",
        "  данных это не указано», не оценивай «на глаз».",
        "- Запрещены восклицательные знаки `!` в любом разделе ответа.",
        "- Не путай врождённые звёзды (постоянные) с активными звёздами",
        "  сегодня (универсальная погода неба). Блок «Резонансы карты",
        "  рождения с текущим моментом» показывает, КАК сегодня лично",
        "  трогает пользователя.",
        "- ⛔ АБСОЛЮТНЫЙ ЗАПРЕТ на слова «натал», «натале», «натальный»,",
        "  «натальная», «натальные». Это медицинский термин, клиенту",
        "  непонятен. Всегда заменяй на «в карте Ба Цзы», «в карте",
        "  рождения», «врождённый», «в столпах», «в столпе года/месяца/",
        "  дня/часа». Примеры замен: «натальная карта»→«карта рождения»,",
        "  «в натале»→«в карте Ба Цзы», «натальный ДМ»→«врождённый ДМ»,",
        "  «натальные звёзды»→«врождённые звёзды». Любое использование",
        "  слова с корнем «натал» в ответе клиенту — критическая ошибка.",
        "- [BAZI_DATA] — это внутренние данные для твоего рассуждения.",
        "  НЕ ЦИТИРУЙ дословно блоки про «10 Богов», «Скрытые стволы»,",
        "  «Врождённые звёзды» как bullet-список. Это техническая",
        "  раскладка для рассуждения, не текст для клиента. Синтезируй 2-3 главных",
        "  фактора в нарратив, остальное используй для своего вывода.",
        "- Каждый китайский термин или иероглиф ОБЯЗАТЕЛЬНО даёшь с",
        "  inline-расшифровкой при первом упоминании в формате",
        "  «<b>七杀</b> (Семь Убийств) — энергия давления, словно",
        "  строгий начальник». Голый иероглиф без расшифровки —",
        "  критическая ошибка.",
        "- Используй HTML-теги <b>...</b> для жирного, НЕ Markdown",
        "  **звёздочки** — бот шлёт с parse_mode=HTML, звёздочки",
        "  отображаются как текст.",
        "- 4-5 эмодзи в ответе для разделения смысловых блоков",
        "  (🌿🔥⛰⚔️💧 для стихий, ✨ для звёзд, ⏳ для времени,",
        "  💡 для рекомендаций, ☯️ в финале).",
        "",
        "Формат ответа — РАССКАЗ-ИСТОРИЯ от Мастера Шифу, не сухой разбор.",
        "Обращайся на «ты» — тепло, как старый наставник к ученику.",
        "Веди ответ как историю с аркой (без заголовков-разделов):",
        "1. ОБРАЗ-ЗАВЯЗКА — открой живой сценой через главный символ",
        "   карты (Дневной Мастер как стихия-персонаж: свеча, река, гора).",
        "   Разверни образ в маленькую сцену на 2-4 фразы, НЕ в одну",
        "   строку-сравнение.",
        "2. РАЗВИТИЕ — введи 1-2 ключевых фактора карты (10 богов,",
        "   столкновение, звезда) КАК ПЕРСОНАЖЕЙ той же истории",
        "   (七杀 — строгий Кузнец; 偏财 — ветер с чужих полей).",
        "   Один новый китайский концепт на абзац, каждый иероглиф —",
        "   с inline-расшифровкой. Без дампа всех богов/звёзд/стволов.",
        "3. ПОВОРОТ — назови нюанс или трещину (приходящий столп, риск)",
        "   тоже образом, а не сухим термином.",
        "4. ПРИЗЕМЛЕНИЕ — прямой ответ на вопрос простыми словами плюс",
        "   ОДИН конкретный шаг на эту неделю. Без новых чисел/звёзд/дат.",
        "5. Финал — приглашение строго в формате (HTML обязателен):",
        "   <b><u>Чтобы узнать больше, задай вопрос по этой карте:</u></b>",
        "   с новой строки <code>один вопрос, 10-20 слов, без кавычек</code>.",
        "",
        "Правила истории: образ можно вести сквозным «персонажем» через",
        "весь ответ; образ должен удивлять и запоминаться; длину НЕ",
        "ограничивай — пусть будет наглядно и подробно. Числа, проценты,",
        "звёзды и даты — ТОЛЬКО из [BAZI_DATA] и [CURRENT_MOMENT].",
        "[/INSTRUCTIONS]",
    ]
)


def get_instruction_prefix() -> str:
    """Public accessor — kept as a function so callers don't import
    the constant directly (lets us swap the source later, e.g. read
    from a file or feature-flag two variants)."""
    return INSTRUCTION_PREFIX
