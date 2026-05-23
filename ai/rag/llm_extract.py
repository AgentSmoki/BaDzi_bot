"""LLM-based concept extraction for RAG (Phase 3.5).

Complements :func:`ai.rag.extract.extract_concepts` (vocabulary match +
Russian stem tokens) by adding an LLM pass over the question text. The
LLM hint catches concepts the deterministic extractors miss:

- Synonyms / colloquialisms — «начальник» → ``正官`` (Прямой Чиновник)
- Implied themes — «постоянно ругаюсь с женой» → ``夫妻宫``, ``六冲``
- Time references — «следующая неделя» → ``流月``
- Health symptoms — «голова болит» → ``五行 + Огонь + печень``

Two safety nets so the hot consultation path doesn't break:

1. **Redis-backed cache** — same question → same concepts (TTL 24h).
   Repeated questions inside a session cost zero LLM calls, and
   identical questions across users still share the cache.
2. **Graceful fallback** — any LLM error returns ``[]``, callers
   merge with vocab+stem hits so retrieval keeps working.

Uses the existing fast-tier (``yc_fast_model = qwen3.6-35b-a3b``,
max_tokens=2000) — same model as ``ai.skill_router``. Cost per call:
~0.3 ₽; with Redis cache amortised to ~0.05 ₽ on real load.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Final

import redis.asyncio as redis_async
import structlog

from ai.orchestrator import ChatMessage, OrchestratorError, chat
from bot.config import get_settings

logger = structlog.get_logger(__name__)


_CACHE_KEY_PREFIX: Final = "rag:concepts:"
_CACHE_TTL_SECONDS: Final = 24 * 60 * 60
_JSON_BLOCK_RE: Final = re.compile(r"\[.*?\]", re.DOTALL)
_MAX_CONCEPTS: Final = 15  # cap per call to keep Cypher join cheap


_SYSTEM_PROMPT: Final = (
    "Ты экстрактор концептов Ба Цзы (四柱命理) из вопроса клиента. "
    "Извлеки китайские термины и иероглифы, которые могут быть релевантны "
    "ответу — даже если в вопросе они не упоминаются дословно.\n\n"
    "Категории для извлечения:\n"
    "- 10 Небесных Стволов: 甲乙丙丁戊己庚辛壬癸\n"
    "- 12 Земных Ветвей: 子丑寅卯辰巳午未申酉戌亥\n"
    "- 10 Божеств: 比肩 劫財 食神 傷官 正財 偏財 正官 七殺 正印 偏印\n"
    "- Звёзды Шэнь Ша: 桃花 白虎 文昌 將星 天乙貴人 月德 羊刃 紅鸞\n"
    "- Взаимодействия: 六合 六冲 三合 三刑 自刑 六害\n"
    "- Структуры (格局): 正官格 七殺格 食神格 傷官格 化氣格 從格\n"
    "- Концепции: 用神 (Полезное Божество), 忌神 (Вредное), 日主 (Дневной Мастер), "
    "夫妻宫 (Дворец Супруга), 大運 (Столп Удачи), 流年 (Годовой Столп), "
    "流月 (Месячный Столп)\n\n"
    "Правила:\n"
    "1. Возвращай ТОЛЬКО JSON-массив строк, без объяснений и markdown-обёрток.\n"
    "2. Не больше 15 концептов. Если вопрос узкий — 2-3 концепта достаточно.\n"
    "3. Используй китайские иероглифы где есть. Не русскую транслитерацию.\n"
    "4. Не выдумывай — если ничего конкретного не извлекается, верни [].\n\n"
    "Примеры:\n"
    'Вопрос: «Как у меня с работой?» → ["正官", "七殺", "偏財", "正財", "食傷", "月柱"]\n'
    'Вопрос: «Какой опасный месяц 2026?» → ["六冲", "三刑", "流月", "羊刃", "白虎"]\n'
    'Вопрос: «Подходит ли мой парень?» → ["夫妻宫", "正官", "桃花", "六合"]\n'
    "Вопрос: «Что сегодня на ужин?» → []"
)


class ConceptCache:
    """Tiny Redis wrapper: sha256(question) → list[concept].

    Cache key derived from the **lowercased+trimmed** question so
    «Какой опасный месяц 2026?» and «  какой опасный месяц 2026?  »
    share the entry. Cache value is a JSON list of strings (compact,
    decoded on read).

    Construct once per process; share via lazy singleton from
    :func:`_get_global_cache`.
    """

    def __init__(self, client: redis_async.Redis) -> None:
        self._r = client

    @classmethod
    def from_settings(cls) -> ConceptCache:
        """Connect to ``settings.redis_url`` — same instance as
        ``HistoryStore`` uses; redis-py pools connections under the hood."""
        settings = get_settings()
        client: redis_async.Redis = redis_async.from_url(  # type: ignore[no-untyped-call]
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        return cls(client)

    @staticmethod
    def _key(question: str) -> str:
        digest = hashlib.sha256(question.strip().lower().encode("utf-8")).hexdigest()
        return f"{_CACHE_KEY_PREFIX}{digest}"

    async def get(self, question: str) -> list[str] | None:
        """Return cached concepts or ``None`` on cache miss / parse error."""
        try:
            raw = await self._r.get(self._key(question))
        except Exception as exc:
            logger.warning("concept_cache.get_failed", error=str(exc))
            return None
        if raw is None:
            return None
        try:
            value = json.loads(raw)
        except json.JSONDecodeError:
            return None
        if not isinstance(value, list):
            return None
        return [str(c) for c in value if isinstance(c, str)]

    async def set(self, question: str, concepts: list[str]) -> None:
        """Store concepts under the question hash with 24h TTL.
        Errors are swallowed — cache is a perf optimisation, not a
        correctness requirement."""
        try:
            await self._r.set(
                self._key(question),
                json.dumps(concepts, ensure_ascii=False),
                ex=_CACHE_TTL_SECONDS,
            )
        except Exception as exc:
            logger.warning("concept_cache.set_failed", error=str(exc))

    async def aclose(self) -> None:
        """Idempotent shutdown — release the Redis connection pool."""
        await self._r.aclose()


_global_cache: ConceptCache | None = None


def _get_global_cache() -> ConceptCache:
    """Lazy singleton. First call connects to Redis; subsequent calls
    return the same instance. Process-lifetime — closed on bot shutdown
    via ``close_concept_cache``."""
    global _global_cache
    if _global_cache is None:
        _global_cache = ConceptCache.from_settings()
    return _global_cache


async def close_concept_cache() -> None:
    """Hook for ``bot.main._shutdown`` — release the Redis pool."""
    global _global_cache
    if _global_cache is not None:
        await _global_cache.aclose()
        _global_cache = None


def _parse_concepts(raw: str) -> list[str]:
    """Best-effort JSON-array extraction from the LLM response.

    The fast LLM sometimes wraps JSON in ```json fences``` or adds a
    one-line preamble even when the system prompt forbids it. We
    grep the first bracketed block and parse it; if that fails — empty.
    """
    text = raw.strip()
    # Direct parse first — covers the well-behaved case.
    try:
        value = json.loads(text)
        if isinstance(value, list):
            return [str(c).strip() for c in value if isinstance(c, str) and str(c).strip()]
    except json.JSONDecodeError:
        pass
    # Fallback: extract first [...] block.
    match = _JSON_BLOCK_RE.search(text)
    if not match:
        return []
    try:
        value = json.loads(match.group(0))
    except json.JSONDecodeError:
        return []
    if not isinstance(value, list):
        return []
    return [str(c).strip() for c in value if isinstance(c, str) and str(c).strip()]


async def extract_concepts_llm(
    question: str,
    *,
    cache: ConceptCache | None = None,
) -> list[str]:
    """LLM-augmented concept extraction. Returns up to 15 concepts.

    Strategy:
    1. Cache hit → return immediately.
    2. Call Qwen3.6 fast tier with the catalog-aware system prompt.
    3. Parse JSON array, cap at 15, store in cache.
    4. Any failure → return ``[]`` and let the caller union with
       vocab+stem hits.

    ``cache=None`` uses the process-global singleton; passing an
    explicit instance is useful for tests that want isolation.
    """
    question = question.strip()
    if not question:
        return []

    cache = cache or _get_global_cache()
    cached = await cache.get(question)
    if cached is not None:
        return cached

    settings = get_settings()
    try:
        result = await chat(
            provider="yc",
            model=settings.yc_fast_model,
            messages=[
                ChatMessage(role="system", content=_SYSTEM_PROMPT),
                ChatMessage(role="user", content=question),
            ],
            temperature=0.1,
            max_tokens=settings.yc_fast_max_tokens,
        )
    except OrchestratorError as exc:
        logger.warning("rag.llm_extract.upstream_failed", error=str(exc))
        return []

    concepts = _parse_concepts(result.text)[:_MAX_CONCEPTS]
    await cache.set(question, concepts)
    logger.info(
        "rag.llm_extract.done",
        question_chars=len(question),
        concept_count=len(concepts),
        latency_ms=result.latency_ms,
    )
    return concepts
