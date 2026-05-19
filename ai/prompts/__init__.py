"""System prompts as code-first loadable resources.

Prompts are .md files alongside this module so version control sees
diffs as readable text, but consumers always load via ``get_prompt``
to keep file paths off call sites.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Final

_PROMPTS_DIR: Final = Path(__file__).resolve().parent

ANASTASIA_SYSTEM: Final = "anastasia_system"


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
    """Shorthand for the only prompt anyone loads in 1.8: Anastasia's
    persona. Kept as a function (not a constant) so the read happens
    on first use, not at import — startup stays fast even if the
    prompt grows."""
    return get_prompt(ANASTASIA_SYSTEM)


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
        "  из блоков [BAZI_DATA] и [CURRENT_MOMENT]. Цитируй их",
        "  дословно в кавычках.",
        "- Если запрашиваемых данных нет — честно скажи «в исходных",
        "  данных это не указано», не оценивай «на глаз».",
        "- Запрещены восклицательные знаки `!` в любом разделе ответа.",
        "- Не путай натальные звёзды (постоянные) с активными звёздами",
        "  сегодня (универсальная погода неба). Блок «Резонансы натала",
        "  с текущим моментом» показывает, КАК сегодня лично трогает",
        "  пользователя.",
        "",
        "Структура ответа (4 раздела):",
        "1. **Кратко** (1-3 предложения) — суть, без чисел.",
        "2. **Анализ карты** — 3-7 пунктов, каждый цитирует данные",
        "   из [BAZI_DATA] дословно.",
        "3. **Ответ на вопрос** — нумерованный список 50-250 слов,",
        "   привязанный к разделу 2.",
        "4. **Рекомендация** — 1-2 абзаца в тоне Анастасии, тёплый,",
        "   без новых чисел / звёзд / дат.",
        "[/INSTRUCTIONS]",
    ]
)


def get_instruction_prefix() -> str:
    """Public accessor — kept as a function so callers don't import
    the constant directly (lets us swap the source later, e.g. read
    from a file or feature-flag two variants)."""
    return INSTRUCTION_PREFIX
