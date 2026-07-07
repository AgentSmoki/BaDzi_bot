"""Concept extraction from the user question (Phase 3.1).

MVP strategy — **vocabulary matching**, not LLM. We took the cheap
path here on purpose:
- The graph already exposes every concept that exists as
  :func:`ai.rag.store.get_concept_vocabulary`. Matching against that
  vocabulary catches the high-precision tokens (``taohua``, ``baihu``,
  the chinese stems / branches) without an API call.
- The retrieval call site is on the consultation hot path; adding an
  LLM round-trip would add ~500 ms p50 latency for ~10% recall gain.
- The plan's Qwen-mini upgrade slot stays open: replace this function
  with an async LLM call when retrieval starts feeling thin.

Token normalisation: lowercase, ё→е, strip punctuation. Multi-word
concepts (``белый тигр``) are matched via substring of the full
normalised question, so the vocabulary entry survives word boundaries.
"""

from __future__ import annotations

import re
from typing import Final

from ai.rag.store import get_concept_vocabulary

_PUNCT_SPLIT: Final = re.compile(r"[\s,.;:!?\"'()\[\]{}«»—–\-]+")

# Russian stop-words pruned aggressively — these words appear in almost
# every consultation question and would explode the candidate set with
# noise hits. Anything domain-specific (даже короткое, "ДМ", "час") stays.
_RU_STOPWORDS: Final[frozenset[str]] = frozenset(
    {
        "что",
        "как",
        "это",
        "там",
        "тут",
        "если",
        "когда",
        "потом",
        "будет",
        "может",
        "чтобы",
        "тоже",
        "ещё",
        "еще",
        "уже",
        "только",
        "очень",
        "тогда",
        "значит",
        "значение",
        "значения",
        "почему",
        "зачем",
        "куда",
        "откуда",
        "сейчас",
        "тебе",
        "мне",
        "меня",
        "тебя",
        "себя",
        "себе",
        "наше",
        "наша",
        "ваш",
        "ваша",
        "мой",
        "моя",
        "моего",
        "моей",
        "твой",
        "твоя",
        "расскажи",
        "скажи",
        "объясни",
        "помоги",
        "пожалуйста",
        "можно",
        "нужно",
        "надо",
        "хочу",
        "хотел",
        "буду",
        "карте",
        "карта",
        "карты",
        "карту",
    }
)

# Minimum length for a free-form question token to make it into the
# search bag. Captures "крыса", "удачи", "тигр", "столпы" while keeping
# articles / prepositions out.
_MIN_TOKEN_LEN: Final[int] = 4

# Simple Russian suffix stripper — handles the common declensions so
# "дракона" matches title "Дракон", "змею" matches "Змея", "столпы"
# matches "Столпы". Order matters: longer suffixes first so "ого" wins
# over "о". This is intentionally NOT a full morphological analyser
# (pymorphy3 would add 12 MB to the Docker image for a hot-path that
# only ever sees Bazi terminology). False positives on a 33-node graph
# are tolerable; precision can be raised later via the LLM-based
# extraction slot reserved for Phase 3.5.
_RU_SUFFIXES: Final[tuple[str, ...]] = (
    "ами",
    "ями",
    "ого",
    "его",
    "ему",
    "ому",
    "ыми",
    "ими",
    "ах",
    "ях",
    "ам",
    "ям",
    "ев",
    "ов",
    "ой",
    "ей",
    "ом",
    "ем",
    "ы",
    "и",
    "у",
    "ю",
    "а",
    "я",
    "е",
    "о",
    "ь",
)
_MIN_STEM_LEN: Final[int] = 3


def _normalise(text: str) -> str:
    return text.lower().replace("ё", "е")


def _tokenise(text: str) -> list[str]:
    return [tok for tok in _PUNCT_SPLIT.split(_normalise(text)) if tok]


def _stem(token: str) -> str:
    """Strip one Russian suffix if it leaves a stem of ≥3 chars."""
    for suf in _RU_SUFFIXES:
        if token.endswith(suf) and len(token) - len(suf) >= _MIN_STEM_LEN:
            return token[: -len(suf)]
    return token


def extract_concepts(question: str, *, vocab: frozenset[str] | None = None) -> list[str]:
    """Return concept slugs from the KB vocabulary that match the question.

    These are the high-precision matches used by
    :func:`ai.rag.retrieve.retrieve_nodes` for ``related_concepts``
    overlap. Order is stable (sorted) so retrieval is deterministic.

    Vocabulary is mostly English transliterations + frontmatter slugs
    (``baihu``, ``liuchong``, ``ten_gods``); for natural Russian
    phrasings see :func:`extract_search_tokens`.
    """
    v = vocab if vocab is not None else get_concept_vocabulary()
    if not v:
        return []
    normalised = _normalise(question)
    tokens = set(_tokenise(question))

    hits: set[str] = set()
    for concept in v:
        c = concept.lower()
        if c in tokens or c in normalised:
            hits.add(c)
    return sorted(hits)


def extract_search_tokens(question: str) -> list[str]:
    """Return content-bearing **stems** (len ≥ 3 after suffix strip,
    stop-words removed) from the question. These feed the
    *title-substring* retrieval path:
    ``MATCH (n) WHERE lower(n.title) CONTAINS $stem``.

    Stemming covers the common Russian declensions ("дракона" → "дракон",
    "змею" → "зме", "столпы" → "столп") so the substring CONTAINS query
    catches title words regardless of grammatical case.

    The two extractors are complementary — :func:`extract_concepts` is
    high-precision via the KB vocabulary; this one is high-recall via
    titles and catches Russian phrasings the English-leaning vocabulary
    misses.
    """
    tokens = _tokenise(question)
    return sorted(
        {_stem(tok) for tok in tokens if len(tok) >= _MIN_TOKEN_LEN and tok not in _RU_STOPWORDS}
    )
