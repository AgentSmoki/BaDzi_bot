# План реализации: semantic embeddings для RAG (1.9.16)

> Статус: одобрен Богданом 2026-06-10 («я не против, давай»).
> База: [bge_m3_embeddings.md](bge_m3_embeddings.md) (proposal 2026-06-02).
> Оценка: ~1.5 дня (Вариант 1) / ~2 дня (Вариант 2). Отдельная сессия, начинать с Phase 0.
> **Дополнено 2026-06-10:** live-probe эмбеддинг-моделей Yandex Cloud — индексацию и query-инференс можно гнать через YC API, без макбука и без модели в Docker.

## Выбор движка эмбеддингов — два варианта

### ✅ Вариант 1 (рекомендуемый старт): Yandex Cloud Embeddings API

**Live-probe 2026-06-10 ключом проекта (`YC_AI_API_KEY` / SA `badzi-ai-sa`) — работает:**

| Модель | URI | Размерность | Версия | Назначение |
|---|---|---|---|---|
| `text-search-doc` | `emb://<folder>/text-search-doc/latest` | **256** | 06.12.2023 | индексация узлов KB |
| `text-search-query` | `emb://<folder>/text-search-query/latest` | **256** | 06.12.2023 | эмбеддинг вопроса клиента |

Endpoint: `https://llm.api.cloud.yandex.net/foundationModels/v1/textEmbedding`, auth — те же headers что у chat (`Api-Key` + `x-folder-id`). Пара асимметричная (doc/query) — это плюс для retrieval. Других эмбеддеров в каталоге YC нет (probe: qwen3-embedding-*, bge-m3, *-v2 → `unknown model`).

**Почему стартуем с него:**
- **Ноль инфраструктуры:** ни модели в Docker (+0 MB к образу), ни RAM на VM (+0 MB), ни прогона на макбуке. Индексация 7788 узлов — обычные HTTP-вызовы, можно запускать откуда угодно (хоть с VM).
- Тот же провайдер и биллинг (RUB), что и main LLM (ADR-009). Стоимость индексации корпуса — копейки (one-off ~1.5-2M токенов), query-вызов дешевле LLM-вызова на порядки.
- Сетевая зависимость в query-path уже есть (main LLM тоже YC); fallback на sparse сохраняется.

**Риски Варианта 1 (проверяются quality-gate'ом в Phase 3):**
- 256-dim против 1024 у bge-m3 — меньшая выразительность.
- Модель 2023 года, заточена на русский веб-поиск; качество на китайской терминологии (七殺, 桃花) неизвестно — но точные термины страхует sparse-составляющая гибрида.
- Rate limit (~10 RPS sync) → индексация 7788 узлов с троттлингом ≈ 15-30 мин.

### Вариант 2 (fallback по качеству): bge-m3 ONNX int8 локально

Прежний план — включается, если quality-gate Варианта 1 провален (recall на эталонных вопросах хуже текущего sparse или критично проседают китайские термины):
- **ONNX int8 квантованный bge-m3** (~700 MB RAM) в bot-контейнере для query-инференса. Замер VM 2026-06-10: 3.9 GB RAM, 2.3 GB available, swap 0 → fp32 (~2.3 GB) = OOM-риск, int8 влезает (bot сейчас 234 MB).
- Индексация — один прогон локально на Mac, на VM едет готовый kuzu_db (`docker compose cp`, паттерн 1.9.11).
- 1024-dim, нативная мультиязычность RU+ZH.

**Код пишем движко-агностично:** интерфейс `embed_doc(texts) / embed_query(text)` с двумя реализациями (`YCEmbedder` / `OnnxEmbedder`), выбор через Settings (`embedding_backend: yc | onnx | off`). Переключение варианта = смена конфига + re-embed, без переписывания retrieve.py.

## Решённые вопросы

| Вопрос | Решение | Основание |
|---|---|---|
| Инфраструктура | KuzuDB 0.10 остаётся, AGE отменён | решение Богдана 2026-06-02 |
| Движок | **Вариант 1 — YC Embeddings API** (text-search-doc/query, 256-dim); Вариант 2 (bge-m3 ONNX int8) — fallback по качеству | live-probe 2026-06-10 + запрос Богдана «прогнать через Яндекс, а не через макбук» |
| Индексация корпуса | HTTP-вызовы YC API (~15-30 мин на 7788 узлов с троттлингом ≤10 RPS) | без модели локально; Вариант 2 — прогон на Mac |
| Деградация | Пустой `embedding` / ошибка API → текущий sparse retrieval без изменений | требование proposal |

## Phase 0 — подготовка (0.5 ч)

1. Проверить, что колонка `embedding FLOAT[]` реально есть в Node DDL ([knowledge/schema.py](../../knowledge/schema.py)) и читается из kuzu 0.10 (узлы пишутся/читаются с массивом 256 float).
2. `ai/embeddings.py` — интерфейс `embed_doc/embed_query` + реализация `YCEmbedder` (httpx, reuse паттерна `ai/orchestrator.py`: singleton client, retry на 429/5xx, троттлинг). Settings: `embedding_backend`, `yc_embedding_doc_model="text-search-doc"`, `yc_embedding_query_model="text-search-query"`.
3. (Вариант 2, отложено) ONNX-вариант: официальный экспорт BAAI/bge-m3 + onnxruntime int8; deps `onnxruntime`, `tokenizers` — без torch в проде.

## Phase 1 — индексация (0.5 дня)

`knowledge/ingest/embed.py`:
- CLI: `python -m knowledge.ingest.embed [--db-path] [--batch 16] [--only-empty]`
- Текст узла: `title + "\n" + (summary or body[:2000])`. Эмбеддер — `embed_doc` (для YC — модель text-search-doc).
- Батчи + `CHECKPOINT` каждые 500 записей в kuzu (урок OOM из EdoHa-импорта 2026-05-24), `buffer_pool_size=1GB`; троттлинг API ≤10 RPS, retry на 429.
- Идемпотентно: `--only-empty` пропускает узлы с заполненным embedding; полный re-embed по флагу (обязателен при смене движка/модели — размерности несовместимы).
- 7788 узлов через YC API ≈ 15-30 мин (сетевой бюджет, не CPU).

## Phase 2 — retrieval-гибрид (1 день)

`ai/rag/retrieve.py`:
- Кандидаты: текущая школо-выборка (`_school_clause` сохраняется) → узлы с непустым embedding → косинус в Python (numpy предпочтителен: 7788×256 float ≈ 8 МБ — кэшировать матрицу в памяти процесса, инвалидация по mtime kuzu_db).
- Гибрид: `final = 0.6 * dense_norm + 0.4 * sparse_norm` (min-max нормировка по выдаче; коэффициенты — константы в Settings).
- Query-эмбеддинг: `embed_query(question)` → для YC это один HTTP-вызов (~100-300 мс). ⚠️ Вызов **async** → `compose_messages` остаётся sync, поэтому query-эмбеддинг получаем НА УРОВНЕ caller'а (consultation.py, рядом с `extract_concepts_llm`) и передаём вектор в `load_knowledge_for_question(query_vector=...)` опциональным параметром — тот же паттерн, что `concept_hints`.
- Кэш query-векторов: переиспользовать паттерн `ConceptCache` (Redis, sha256(question), TTL 24h) — повторный вопрос не дёргает API.
- Fallback: ошибка API / `embedding_backend=off` / пустой вектор → sparse-only + warning-лог. Бот обязан бутиться и отвечать без эмбеддера — тот же принцип, что «бот бутится без kuzu_db».

## Phase 3 — quality-gate + деплой (0.5 дня)

1. Локально: индексация через YC API → smoke на 7 эталонных вопросах (recall must-not-regress vs sparse) + 3 lexical-miss кейса («как перестать выгорать на работе» → «истощение Огня»; «муж охладел» → 夫妻宫/六冲-ноды; «когда меня повысят» → career-ноды). **Gate: гибрид ≥ sparse на эталоне И ≥2/3 lexical-miss кейсов находят релевантное.**
2. Gate провален → переключение на Вариант 2 (ONNX int8, см. выше): добавляются шаги Dockerfile (+700 MB, проверить диск), индексация на Mac, замер RAM bot < 1.2 GB.
3. Gate пройден: rsync → build bot+worker (образ НЕ растёт) → `docker compose cp knowledge/kuzu_db/. bot:/app/knowledge/kuzu_db/` → restart → прод-smoke 2 вопросов через MCP.

## Phase 4 — тесты (0.5 дня)

- unit: cosine ranking детерминирован; гибрид-merge (dense-hit без sparse-hit попадает в top-k); пустые embedding → sparse-only; `YCEmbedder` мокается (HTTP не дёргается в тестах — деньги); retry на 429.
- e2e (локальный kuzu fixture с предзаписанными векторами): вопрос без лексического пересечения находит узел по смыслу.
- mypy strict + ruff; coverage ai/rag не ниже 80%.

## Риски

- **Качество 256-dim модели 2023 г. на китайской терминологии** — главный риск Варианта 1. Митигация: sparse-составляющая гибрида держит точные термины (七殺, 桃花); quality-gate в Phase 3 с автоматическим переключением на Вариант 2.
- Латентность +100-300 мс на query-эмбеддинг (HTTP) — на фоне 12-17 с main LLM незаметно; Redis-кэш убирает повторы.
- Rate limit YC на индексации — троттлинг + retry; one-off процесс, не критично.
- (Вариант 2) RAM на VM: int8 + замер после деплоя; план Б — эмбеддер отдельным HTTP-сервисом.
