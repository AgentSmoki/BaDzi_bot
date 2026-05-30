"""Per-user dialogue history backed by Redis.

Layout: each user gets a Redis list at key ``chat:{user_id}:history``
with one JSON-encoded message per element (LPUSH front, LTRIM tail).
TTL is reset on every write so an active conversation never expires
mid-session, while idle ones drop out after 24h.

The store is pure infrastructure — it doesn't know about Anastasia,
the calculator, or routing. The orchestrator/composer (1.8.6) decides
which messages get persisted and in what order. Typically: every
user turn AND every assistant reply.
"""

from __future__ import annotations

import json
import time
from typing import Final

import redis.asyncio as redis_async
import structlog

from ai.orchestrator import ChatMessage
from bot.config import get_settings

logger = structlog.get_logger(__name__)

HISTORY_TTL_SECONDS: Final = 24 * 60 * 60
HISTORY_MAX_MESSAGES: Final = 20
HISTORY_KEY_PREFIX: Final = "chat:"
HISTORY_KEY_SUFFIX: Final = ":history"

PENDING_QUESTION_TTL_SECONDS: Final = 60 * 60  # 1 hour
"""TTL для pending-question stash. После часа клиент скорее всего
уже забыл что хотел спросить — лучше очистить и не replay'ить."""


def _key(user_id: int) -> str:
    return f"{HISTORY_KEY_PREFIX}{user_id}{HISTORY_KEY_SUFFIX}"


def _pending_key(user_id: int) -> str:
    """Отдельный Redis ключ для stash'а вопроса, заблокированного
    free-question guard. Надёжнее FSM data — переживает любой
    callback который мог бы сбросить state.
    """
    return f"{HISTORY_KEY_PREFIX}{user_id}:pending_question"


def _suggested_followup_key(user_id: int) -> str:
    """Redis ключ для последнего follow-up вопроса который Анастасия
    предложила клиенту. Кнопка «⬆️ Задать предложенный вопрос» под
    ответом достаёт его и отправляет в pipeline без повторного ввода.
    """
    return f"{HISTORY_KEY_PREFIX}{user_id}:suggested_followup"


def _last_skill_key(user_id: int) -> str:
    """Redis ключ для skill последнего успешного assistant-ответа.

    Используется для smart-reset истории при смене темы — если новый
    skill отличается от last_skill, очищаем chat-историю чтобы LLM
    не утягивала контекст и имена из чужой темы (Wave 7 2026-05-26).
    """
    return f"{HISTORY_KEY_PREFIX}{user_id}:last_skill"


class HistoryStore:
    """Async Redis-backed history. Construct once per process; share
    across handlers via dependency injection (db_session-style middleware
    in the bot)."""

    def __init__(self, client: redis_async.Redis) -> None:
        self._r = client

    @classmethod
    def from_settings(cls) -> HistoryStore:
        """Convenience factory — connects to ``settings.redis_url``."""
        settings = get_settings()
        client: redis_async.Redis = redis_async.from_url(  # type: ignore[no-untyped-call]
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        return cls(client)

    async def append(self, user_id: int, message: ChatMessage) -> None:
        """Append one message to the user's history. Trims to the
        last ``HISTORY_MAX_MESSAGES`` so memory pressure stays bounded
        even on long conversations. TTL is refreshed on every write."""
        payload = json.dumps(
            {"role": message.role, "content": message.content, "ts": time.time()},
            ensure_ascii=False,
        )
        key = _key(user_id)
        # LPUSH so newest-first; LTRIM keeps the freshest N entries.
        # EXPIRE inside the same pipeline = atomic refresh.
        async with self._r.pipeline(transaction=True) as pipe:
            pipe.lpush(key, payload)
            pipe.ltrim(key, 0, HISTORY_MAX_MESSAGES - 1)
            pipe.expire(key, HISTORY_TTL_SECONDS)
            await pipe.execute()

    async def get(self, user_id: int, *, limit: int = HISTORY_MAX_MESSAGES) -> list[ChatMessage]:
        """Return the user's history oldest→newest, ready to splice
        into a new request. Returns an empty list if there's nothing
        cached or if the entry has expired."""
        key = _key(user_id)
        # LRANGE 0..N-1 is newest-first because we LPUSH; reverse for
        # chronological order so the LLM reads like a transcript.
        raw_items: list[str] = await self._r.lrange(key, 0, limit - 1)  # type: ignore[misc]
        if not raw_items:
            return []
        messages: list[ChatMessage] = []
        for raw in reversed(raw_items):
            try:
                data = json.loads(raw)
                messages.append(ChatMessage(role=data["role"], content=data["content"]))
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                # Tolerate one bad entry without breaking the whole
                # conversation — just log and skip.
                logger.warning("history.skip_corrupt_entry", user_id=user_id, error=str(exc))
                continue
        return messages

    async def clear(self, user_id: int) -> None:
        """Drop the conversation. Used by /reset and admin commands."""
        await self._r.delete(_key(user_id))

    async def stash_pending_question(self, user_id: int, question: str) -> None:
        """Сохранить вопрос клиента, заблокированный free-question guard,
        в отдельный Redis-ключ с TTL 1 час. Используется как
        надёжный fallback на случай если FSM-data будет затёрта между
        guard и нажатием «продолжить бесплатно»."""
        if not question:
            return
        await self._r.set(
            _pending_key(user_id),
            question,
            ex=PENDING_QUESTION_TTL_SECONDS,
        )

    async def pop_pending_question(self, user_id: int) -> str | None:
        """Прочитать и удалить stash'нутый вопрос. None если ничего
        не было либо TTL истёк. Удаление в одной операции = идемпотентно
        при повторном нажатии «продолжить бесплатно»."""
        key = _pending_key(user_id)
        # GETDEL: атомарно прочитать и удалить. redis-py >= 4.5 поддерживает.
        value = await self._r.getdel(key)
        if value is None or not isinstance(value, str):
            return None
        return value.strip() or None

    async def stash_suggested_followup(self, user_id: int, question: str) -> None:
        """Сохранить последний follow-up вопрос («Чтобы узнать больше,
        задайте вопрос по этой карте: …»), извлечённый из ответа
        Анастасии. Используется кнопкой «⬆️ Задать предложенный
        вопрос» под ответом — она достанет вопрос и отправит в
        consultation pipeline без повторного ввода клиентом.

        TTL 1 час: после этого клиент уже потерял контекст ответа.
        """
        if not question:
            return
        await self._r.set(
            _suggested_followup_key(user_id),
            question,
            ex=PENDING_QUESTION_TTL_SECONDS,
        )

    async def pop_suggested_followup(self, user_id: int) -> str | None:
        """Прочитать и удалить последний suggested follow-up вопрос.
        Атомарно (GETDEL) чтобы случайный повторный клик не
        дублировал запрос."""
        key = _suggested_followup_key(user_id)
        value = await self._r.getdel(key)
        if value is None or not isinstance(value, str):
            return None
        return value.strip() or None

    async def get_last_skill(self, user_id: int) -> str | None:
        """Достать skill последнего успешного ответа Анастасии.

        Используется в consultation-pipeline для smart-reset истории
        при смене темы (Wave 7 2026-05-26). Если возвращает None —
        либо это первый ответ, либо TTL истёк (= history тоже истёк).
        """
        value = await self._r.get(_last_skill_key(user_id))
        if value is None or not isinstance(value, str):
            return None
        return value.strip() or None

    async def set_last_skill(self, user_id: int, skill: str) -> None:
        """Запомнить skill только что закрывшегося турна.

        TTL = HISTORY_TTL_SECONDS чтобы ключ автоматически экспайрился
        синхронно с историей и не оставался «висеть» во время
        следующего диалога через сутки.
        """
        if not skill:
            return
        await self._r.set(
            _last_skill_key(user_id),
            skill,
            ex=HISTORY_TTL_SECONDS,
        )

    async def clear_last_skill(self, user_id: int) -> None:
        """Удалить last_skill ключ — обычно вместе с `clear`."""
        await self._r.delete(_last_skill_key(user_id))

    async def aclose(self) -> None:
        """Idempotent shutdown — release the Redis connection pool."""
        await self._r.aclose()
