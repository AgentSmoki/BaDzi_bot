# План реализации: bge-m3 embeddings для RAG (1.9.16)

> Статус: одобрен Богданом 2026-06-10 («я не против, давай»).
> База: [bge_m3_embeddings.md](bge_m3_embeddings.md) (proposal 2026-06-02).
> Оценка: ~2 дня. Отдельная сессия, начинать с Phase 0.

## Решённые вопросы

| Вопрос | Решение | Основание |
|---|---|---|
| Инфраструктура | KuzuDB 0.10 остаётся, AGE отменён | решение Богдана 2026-06-02 |
| Хостинг модели | **ONNX int8 квантованный bge-m3** в bot-контейнере для query-инференса | замер VM 2026-06-10: 3.9 GB RAM, 2.3 GB available, swap 0. fp32 (~2.3 GB) — OOM-риск; int8 ≈ 600-700 MB — влезает (bot сейчас 234 MB) |
| Индексация корпуса | Один прогон **локально на Mac** (полная модель или int8), на VM едет готовый kuzu_db | На VM не хватит RAM для батч-индексации; паттерн `docker compose cp` отработан в 1.9.11 |
| Деградация | Пустой `embedding` → текущий sparse retrieval без изменений | требование proposal |

## Phase 0 — подготовка (0.5 ч)

1. Проверить, что колонка `embedding FLOAT[]` реально есть в Node DDL ([knowledge/schema.py](../../knowledge/schema.py)) и читается из kuzu 0.10.
2. Выбрать ONNX-вариант: официальный экспорт BAAI/bge-m3 + onnxruntime int8 (динамическое квантование) ИЛИ готовый `bge-m3-onnx` с HuggingFace. Зафиксировать ревизию модели в коде (без `latest`).
3. deps: `onnxruntime`, `tokenizers` — без torch в проде. Для локальной индексации torch допустим как dev-extra.

## Phase 1 — индексация (0.5 дня)

`knowledge/ingest/embed.py`:
- CLI: `python -m knowledge.ingest.embed [--db-path] [--batch 64] [--only-empty]`
- Текст узла: `title + "\n" + (summary or body[:2000])`.
- Батчи + `CHECKPOINT` каждые 500 (урок OOM из EdoHa-импорта 2026-05-24), `buffer_pool_size=1GB`.
- Идемпотентно: `--only-empty` пропускает узлы с заполненным embedding; полный re-embed по флагу.
- 7788 узлов на Mac CPU ≈ 30-60 мин.

## Phase 2 — retrieval-гибрид (1 день)

`ai/rag/retrieve.py`:
- Кандидаты: текущая школо-выборка (`_school_clause` сохраняется) → узлы с непустым embedding → косинус в Python (numpy предпочтителен: 7788×1024 float ≈ 32 МБ; проверить наличие в deps).
- Гибрид: `final = 0.6 * dense_norm + 0.4 * sparse_norm` (min-max нормировка по выдаче; коэффициенты — константы в Settings).
- Query-эмбеддинг: lazy-singleton ONNX-сессия в bot-процессе; первый вызов ~1-2 с (загрузка), дальше ~50-200 мс.
- Кэш query-векторов: переиспользовать паттерн `ConceptCache` (Redis, sha256(question), TTL 24h).
- Fallback: модель отсутствует в образе / ошибка инференса → sparse-only + warning-лог. Бот обязан бутиться без модели — тот же принцип, что «бот бутится без kuzu_db».

## Phase 3 — Docker + деплой (0.5 дня)

1. Dockerfile: скачивание ONNX-модели на build-стадии (curl с зафиксированным sha256) ИЛИ volume. Образ +~700 MB — проверить свободный диск на VM перед build.
2. Локально: полный re-ingest с embeddings → smoke на 7 эталонных вопросах (recall must-not-regress) + новый кейс «как перестать выгорать на работе» (lexical-miss из proposal — должен начать находить «истощение Огня»).
3. rsync → build bot+worker → `docker compose cp knowledge/kuzu_db/. bot:/app/knowledge/kuzu_db/` → restart.
4. Замер RAM на VM после деплоя (`docker stats`): bot < 1.2 GB.

## Phase 4 — тесты (0.5 дня)

- unit: cosine ranking детерминирован; гибрид-merge (dense-hit без sparse-hit попадает в top-k); пустые embedding → sparse-only; ONNX-сессия не грузится, когда модель отсутствует.
- e2e (локальный kuzu fixture): вопрос без лексического пересечения находит узел по смыслу.
- mypy strict + ruff; coverage ai/rag не ниже 80%.

## Риски

- **RAM на VM** — главный. Митигация: int8 + замер после деплоя; если bot >1.2 GB — план Б: эмбеддер отдельным лёгким HTTP-сервисом (FastAPI + onnxruntime, один контейнер) или YC embeddings API.
- Качество int8 vs fp32 — на retrieval-задачах деградация обычно <1-2% recall; проверяем на эталонных вопросах.
- Холодный старт bot-контейнера +1-2 с (загрузка ONNX) — допустимо.
