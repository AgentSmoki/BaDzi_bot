---
date: 2026-05-17
source_request: Bogdan
plan: badzi-fractal-rag-graph.md
tasks: 1.9.1
authors: research-agent (Claude Opus 4.7)
status: discovery
---

# Research: Fractal RAG-Graph для домена БаЦзы (2026-05-17)

## TL;DR — Выводы и рекомендации

1. **«Fractal/hierarchical RAG-Graph»** — не отдельная новая методика, а зонтичный термин для семейства подходов 2024-2026, в которых корпус организуется в **дерево/многоуровневый граф с явно выраженными уровнями абстракции**, а retrieval идёт **top-down или bottom-up по уровням** с агрегацией. Канонические реализации: RAPTOR (ICLR 2024, рекурсивная кластеризация + summarization → дерево), MedGraphRAG (ACL 2025, 3 уровня + U-Retrieval), MedRAG (WWW 2025, 4-tier diagnostic KG), HCAG (arXiv 2603.20299, multi-resolution code KB), A-RAG (arXiv 2602.03442, hierarchical retrieval interfaces). Это **прямо подтверждает архитектуру L1-L7 из плана** — нужно лишь правильно выбрать pattern retrieval'а (см. §5).

2. **Стек:** в свете архивации KuzuDB (Apple, октябрь 2025) embedded-вариант остаётся достижимым, но требует пересмотра ADR-004. Рабочие альтернативы: **FalkorDB / FalkorDBLite** (GraphRAG-first, 90%+ accuracy, Cypher, Python-native) — рекомендованный вариант; **ArcadeDB** (быстрее Kuzu на LDBC); **Apache AGE + pgvector** на Yandex Managed PostgreSQL (single-engine graph + vector, ACID, вписывается в текущий стек); **community fork Kuzu / LadybugDB** — рискованно для прод. **LightRAG** (HKUDS, EMNLP 2025) — отдельный кандидат как fullstack RAG-framework, который сам управляет графом + dual-level retrieval'ом.

3. **Embeddings:** для BaCzy (RU вопросы + ZH терминология 甲乙丙丁/十神/格局) лидер 2025-2026 — **Qwen3-Embedding-0.6B** (MTEB multilingual 70.58 у 8B-версии, 0.6B — наилучший trade-off для embedded-сценария, нативный ZH, 32K context, MIT-like license). Запасной вариант: **BAAI/bge-m3** (1024-dim, dense+sparse+ColBERT в одной модели, 100+ языков, проверенный production-default). **Linq-Embed-Mistral** даёт топовое качество на legal/RAG-задачах, но 7B параметров — overkill для embedded.

4. **Retrieval pattern:** комбинируем **U-Retrieval от MedGraphRAG** (top-down: L7 → L6 → ... для точности + bottom-up refinement для глобального контекста) с **dual-level keywords от LightRAG** (high-level «отношения», low-level «桃花 в столпе дня»). Multi-hop ограничить 1-2 переходами; rerank — Qwen3-Reranker-0.6B или cross-encoder bge-reranker-v2-m3. Re-rank критичен: без него score-noise от dense-retrieval'а растворяет L7-эвристики мастера среди L1-определений.

5. **Domain best practices:** RareBench, MedGraphRAG, MedRAG, OpenTCM (Chinese medicine!) и LegalBench-RAG сходятся на трёх правилах: **(a)** иерархия должна совпадать со структурой эксперт-знаний, а не быть искусственной; **(b)** **source authority** (вес источника) — обязательное поле в схеме; **(c)** evidence-based генерация — ответ LLM должен **цитировать узлы**, иначе галлюцинации остаются. OpenTCM напрямую релевантен — Chinese ancient texts, GraphRAG, Deepseek/Kimi для извлечения сущностей — почти один-в-один со сценарием BaCzy.

**Конкретная рекомендация для BaCzy_bot** (детали в финале документа): **FalkorDBLite + Qwen3-Embedding-0.6B + U-Retrieval с dual-level keywords + Qwen3-Reranker-0.6B**. Если Богдан хочет минимум миграционного риска от плана — оставить KuzuDB-fork (LadybugDB или fork Vela Partners) на Phase 1-2, заложить адаптер `knowledge/store/` чтобы Phase 4 (production) переехать на FalkorDB без переписывания retrieval-кода.

---

## 1. Methodology Comparison — что значит «fractal RAG-Graph» в 2026

### 1.1 Flat Graph RAG vs hierarchical/fractal

**Flat Graph RAG** (классический baseline, Microsoft GraphRAG v1, LangChain GraphCypherQAChain, LlamaIndex KnowledgeGraphIndex до v0.10): LLM извлекает `(subject, predicate, object)` triplets из текста → пишет в один граф, все узлы на одном уровне. Retrieval = семантический поиск ближайших узлов + 1-2 hop expansion. Хорошо для FAQ-баз, провалов на «глобальных» вопросах вида «summarize the document», так как не видит структуру.

**Hierarchical / fractal Graph RAG** добавляет **уровни абстракции** как first-class свойство узла. Подходов несколько:

| Pattern | Источник | Как строится | Как retrieve'ится |
|---|---|---|---|
| **RAPTOR tree** | Sarthi et al., ICLR 2024 ([arXiv 2401.18059](https://arxiv.org/abs/2401.18059)) | Рекурсивная кластеризация чанков + LLM-summarization снизу вверх. На каждом уровне меньше узлов, но более абстрактных. | Tree traversal: collapsed (все уровни сразу в один pool) или tree (DFS от корня к листьям). +20% на QuALITY benchmark с GPT-4. |
| **Microsoft GraphRAG (community-based)** | Edge et al., 2024 | Entities → relationships → community detection (Leiden) → LLM генерирует summary каждой community → иерархия communities. | Global search по community summaries для broad-topic; local search по entity neighbourhood для специфичных вопросов. |
| **MedGraphRAG (3-tier)** | Wu et al., ACL 2025 ([arXiv 2408.04187](https://arxiv.org/abs/2408.04187)) | 3 фиксированных уровня: user docs → medical credible texts → foundational concepts. Связи между уровнями явные. | **U-Retrieval:** Top-down Precise Retrieval (от user-docs к фундаменту) + Bottom-up Response Refinement (для global context). Каждый ответ цитирует source. |
| **MedRAG (4-tier diagnostic KG)** | Zhao et al., WWW 2025 ([arXiv 2502.04413](https://arxiv.org/abs/2502.04413)) | 4 уровня: симптомы → синдромы → дифференциальные диагнозы → решения. Уровни — диагностический workflow клинициста. | KG-elicited reasoning: LLM на каждом уровне делает «диагностическое уточнение», proactively просит у retrieval'а уровень выше/ниже. Снижение misdiagnosis vs flat. |
| **HCAG (multi-resolution code KB)** | arXiv 2603.20299 | Offline hierarchical abstraction: recursive parsing кодовой базы → multi-resolution semantic KB с adaptive node compression. | Online top-down level-wise retrieval. Cost-optimal vs flat / iterative RAG. |
| **A-RAG (agentic hierarchy)** | arXiv 2602.03442 | Корпус индексируется на трёх granularities: keyword, sentence, chunk. | Агент сам решает на каком уровне искать, может комбинировать. State-of-the-art на multi-hop QA. |
| **LightRAG dual-level** | Guo et al., EMNLP 2025 ([arXiv 2410.05779](https://arxiv.org/html/2410.05779v1)) | Один граф entities+relations + dual keyword indexing. | Low-level keys (specific entities) + high-level keys (themes) → объединяются, retrieval за один проход. ~30% latency reduction vs GraphRAG. |

**Что общего у всех «fractal»-подходов:**

- **Уровни ≠ просто chunks разной длины.** Уровень имеет **семантический смысл**: «foundational concept», «applied pattern», «case study», «expert heuristic». Без этой семантики иерархия — обман.
- **Retrieval асимметричный.** Top-down (RAPTOR tree, MedGraphRAG) хорош для специфичных вопросов; bottom-up / global — для «расскажи про X в целом». Лучшие системы делают **оба прохода** и сливают.
- **Edges между уровнями** обязательны. Иначе это не граф, а просто несколько индексов рядом.

### 1.2 Откуда термин «fractal»

Слово «fractal» в этом контексте не строго научное (в отличие от RAPTOR / hierarchical / multi-resolution в paper'ах). Употребляется в community-blogs (Towards AI, Neo4j Engineering, LlamaIndex docs 2025) как метафора: **на каждом уровне видна одна и та же структура (entity-relation), но в разном масштабе абстракции** — как в фрактале. План `badzi-fractal-rag-graph.md` использует термин в этом смысле, и это совпадает с canonical RAPTOR/MedGraphRAG-подходом.

Для статьи L1-L7 BaCzy подходит **гибрид MedGraphRAG (явные уровни + U-Retrieval) + RAPTOR (рекурсивная агрегация для случаев, когда уровень переполнен) + LightRAG dual-level keys (для эффективного запроса)**. Это не один paper, а композиция — обоснованная и встречающаяся в production-blogs Neo4j и FalkorDB.

### 1.3 Сравнительная таблица «глобальные vs локальные» вопросы

| Тип вопроса | Flat RAG | Microsoft GraphRAG | MedGraphRAG (U-Retrieval) | RAPTOR | LightRAG |
|---|---|---|---|---|---|
| «Что значит 七杀 в столбе дня?» | ✅ хорошо | ✅ хорошо (local) | ✅ хорошо (top-down уточнение) | ⚠️ листья дают факт | ✅ low-level keys |
| «Я хочу поменять работу — что говорит карта?» (нужна агрегация по 5-10 правилам мастера) | ❌ хаос | ✅ community summary | ✅✅ bottom-up refinement | ✅ внутренние узлы tree | ✅ high-level keys + multi-entity |
| «Расскажи в целом про моё здоровье в этом 10-летии» (broad) | ❌ | ✅✅ global community | ✅ если есть topic=health subgraph | ✅✅ collapsed tree | ✅ |
| «Сравни 2024 и 2025 для меня» (temporal, multi-hop) | ❌ | ⚠️ | ✅ через explicit edges | ⚠️ слабо | ✅ multi-hop traversal |

Для BaCzy преобладают вопросы 2 и 4 — именно поэтому plan'у нужен **именно граф с уровнями, а не tree-only RAPTOR**.

---

## 2. Stack Recommendations

### 2.1 Контекст: что изменилось с момента ADR-004

**Главное событие:** 9 октября 2025 Apple купил Kuzu Inc.; репозиторий `kuzudb/kuzu` на GitHub архивирован 10 октября 2025 ([The Register, 2025-10-14](https://www.theregister.com/2025/10/14/kuzudb_abandoned/)). Это значит:

- **Никаких новых релизов.** Последний — Kuzu 0.10.x.
- **Никаких security-патчей.** Для prod — это growing tail-risk.
- **Wheels на PyPI остаются** (как с любой архивированной библиотекой), но без поддержки.
- Появились community-форки: **LadybugDB** (без корпоративного бэка), fork от **Vela Partners** с concurrent writes для multi-agent AI (заявленные 374× быстрее Neo4j на 2-hop запросах).

Это **не обязательно «срочно мигрировать»**, но требует пересмотра ADR-004 минимум на уровне «выбираем embedded graph DB заново».

### 2.2 Сравнение кандидатов

| Стек | Тип | Schema / язык | GraphRAG-features | Risk | Подходит BaCzy? |
|---|---|---|---|---|---|
| **KuzuDB (archived)** | Embedded columnar | Cypher | Vector index + full-text built-in | 🔴 архивировано | Возможно для Phase 1-2 (быстрый старт), но запланировать миграцию |
| **LadybugDB / Kuzu fork (Vela)** | Embedded columnar | Cypher | те же что у Kuzu + concurrent writes (Vela) | 🟡 нет корпоративной поддержки | Среднесрочно — да, если работает на 0.10 ветке |
| **FalkorDB** | Server (Redis-based) + Lite | Cypher | GraphRAG-first SDK, GraphBLAS sparse matrix, HNSW vector | 🟢 активная разработка, GraphRAG-focused | ✅ топ-кандидат для prod |
| **FalkorDBLite** | Embedded Python sub-process | Cypher | те же, zero-config | 🟢 новая (2025), но от той же команды | ✅ идеален для dev + low-load prod |
| **ArcadeDB** | Embedded / server, multi-model | Cypher / Gremlin / SQL | Faster than Kuzu на LDBC; vector support | 🟢 активна, Apache 2.0 | ✅ если нужен multi-model (doc+graph+vector) |
| **Neo4j Community / Aura Free** | Server (JVM) | Cypher | Зрелая GraphRAG (через LangChain) | 🟢 enterprise-grade, но JVM | ❌ overkill для embedded-сценария |
| **Apache AGE + pgvector** | Postgres extension | OpenCypher + SQL | Граф + vector в одной БД, ACID | 🟢 встаёт на Yandex Managed PG | ✅ если хочется убрать ещё один движок из стека |
| **LightRAG (HKUDS)** | RAG framework (не БД) — хранит в NetworkX / Neo4j / PG | свой API | Dual-level retrieval, KG construction из LLM, hybrid mode | 🟢 EMNLP 2025, active | ⚠️ это framework, не БД — можно положить поверх любой из вышеперечисленных |
| **Microsoft GraphRAG** | Framework + Parquet файлы | свой | Community detection, global/local search, цена ингеста высокая | 🟢 от MS Research | ❌ медленный и дорогой ингест (~$4 за документ), для 50-500 файлов чрезмерно |
| **LlamaIndex Property Graph Index** | Framework | свой | Гибкие extractors, adapter под Neo4j/Kuzu | 🟢 активна | ⚠️ много абстракций; для контролируемого пайплайна избыточно |

### 2.3 Embedded-варианты для 50-500 файлов (целевой корпус BaCzy)

При корпусе 50-500 файлов с гипотетическим взрывом до 5k узлов / 50k рёбер после ingest'а LLM-экстрактором:

- **Любая из embedded-БД справится без проблем.** В этом диапазоне разница в скорости не критична. Главное — **operational simplicity** и **отсутствие сервера**.
- **FalkorDBLite** выигрывает по developer experience: zero-config, GraphRAG-SDK из коробки делает 90%+ accuracy на benchmark'ах без рерэнкеров.
- **Apache AGE + pgvector** выигрывает архитектурно для проекта, у которого **уже есть Managed PostgreSQL** (BaCzy именно такой — `db/` использует SQLAlchemy + Managed PG). Один движок, ACID, одни бэкапы, никакого SQLite-файла в Docker-volume. Минус: нужно проверить, что Yandex Managed PG позволяет ставить extension AGE (Aurora и DigitalOcean — да; YC — надо проверить отдельно).
- **Kuzu-fork** — самый простой путь сохранить существующий план без переписывания, но с tail-risk.

### 2.4 Не embedded, но рассмотреть

**LightRAG** как application-framework поверх простого storage (даже NetworkX-pickle). Его dual-level retrieval — лучший out-of-the-box hierarchical retriever на сегодня для маленьких корпусов. Можно запустить **LightRAG over FalkorDBLite** и получить готовый stack за день.

---

## 3. Embedding Models

### 3.1 Требования BaCzy

- **RU** — вопросы пользователей, ответы Анастасии, бизнес-логика.
- **ZH (упрощённый и традиционный)** — терминология: 甲乙丙丁戊己庚辛壬癸 (10 стволов), 子丑寅卯辰巳午未申酉戌亥 (12 ветвей), 正官七杀正财偏财 (10 богов), 桃花驿马天乙 (звёзды), 比劫格從格 (структуры). Без хорошего ZH-понимания граф мёртв.
- **EN** — частично академическая литература по Бацзы (Joey Yap книги).
- **Compact:** embedded в Docker-образ, без GPU на проде. Целевой размер ≤ 1.5 GB модель + ≤ 2 GB RAM при инференсе.
- **Длина контекста:** один L7-узел может быть 2-3k токенов (полная эвристика мастера + примеры карт).

### 3.2 Кандидаты

| Модель | Params | Dim | Max ctx | RU | ZH | MTEB multi | Лицензия | Размер на диск |
|---|---|---|---|---|---|---|---|---|
| **Qwen3-Embedding-0.6B** | 0.6B | 1024 | 32K | ✅ (через 100+ langs) | ✅✅ (CMTEB top) | ~64-66 (0.6B), 70.58 (8B) | Apache 2.0 | ~1.2 GB |
| **Qwen3-Embedding-4B** | 4B | 2560 | 32K | ✅ | ✅✅ | ~68 | Apache 2.0 | ~8 GB |
| **Qwen3-Embedding-8B** | 8B | 4096 | 32K | ✅ | ✅✅ | 70.58 (No.1 MTEB multi, июнь 2025) | Apache 2.0 | ~16 GB |
| **BAAI/bge-m3** | 0.56B | 1024 | 8192 | ✅ | ✅ | 63.0 | MIT | ~2.3 GB |
| **bge-large-zh-v1.5** | 0.3B | 1024 | 512 | ❌ | ✅✅ | n/a | MIT | ~1.3 GB |
| **Linq-Embed-Mistral** | 7B | 4096 | 32K | ✅ | ⚠️ | top-tier на MTEB-EN, не лидер в multi | CC-BY-NC | ~14 GB |
| **multilingual-e5-large-instruct** | 0.56B | 1024 | 512 | ✅ | ✅ | 64-65 | MIT | ~2.2 GB |
| **OpenAI text-embedding-3-large** | API | 3072 | 8192 | ✅ | ✅ | ~64 | proprietary | — |

### 3.3 Анализ

- **Qwen3-Embedding-0.6B** — рекомендованный default. Он:
  - **Тренировался на CMTEB** (Chinese MTEB) — топовое качество на китайском.
  - **0.6B** идеален для embedded: ~1.2 GB на диск, ~1.5 GB RAM, ~5-15 ms на запрос на CPU.
  - **32K context** позволяет эмбедить целые L7-эвристики.
  - **Apache 2.0** — без ограничений.
  - Доступен на HF, ollama, GGUF, ONNX.
  - Минус: 0.6B-версия не лидер MTEB (~64-66), 8B (70.58) лидер, но для small corpus с keyword-фильтром перед dense — ок.

- **BGE-M3** — лучший fallback. Преимущество: **одна модель = 3 retrieval-режима** (dense, sparse, multi-vector). Это даёт hybrid retrieval из коробки без дополнительной BM25-инфраструктуры. Размер 2.3 GB (немного больше Qwen3-0.6B), но 8192-context (меньше Qwen3 32K). Для BaCzy hybrid (dense+sparse) **критичен**, потому что Cypher-запросы по `applicable_when` — это фактически sparse keyword match, и bge-m3 даст оба в одном проходе.

- **Linq-Embed-Mistral** — отбрасываем: 7B параметров, CC-BY-NC лицензия (коммерческие ограничения), и при том не лидер на multi. Для legal-доменов был топ-1, но для нас слишком тяжёл.

- **bge-large-zh-v1.5** — отбрасываем: только ZH, провал на RU вопросах пользователей.

- **API-only (OpenAI/Cohere)** — отбрасываем по архитектурному принципу: embeddings — это hot-path retrieval'а, latency должна быть < 50 ms, тратить external HTTP-вызов и токены каждый раз бессмысленно для KB на 5k узлов.

### 3.4 Рекомендация по embeddings

**Production default:** `Qwen3-Embedding-0.6B` (через `sentence-transformers` или прямой transformers).

**Если нужен hybrid (dense + sparse) в один присест:** `BAAI/bge-m3` с `FlagEmbedding` SDK.

**Reranker (отдельная стадия — критична для precision):** `Qwen3-Reranker-0.6B` или `BAAI/bge-reranker-v2-m3`. Реранкинг top-50 → top-5 даёт 5-15% precision uplift и почти бесплатен на CPU (~100 ms на 50 пар).

---

## 4. Retrieval Patterns

### 4.1 Канонические подходы 2024-2026

| Pattern | Откуда | Суть | Когда применять для BaCzy |
|---|---|---|---|
| **Tree traversal (collapsed)** | RAPTOR | Все уровни tree'а в один pool, vector search. | Простой baseline, хорош для general «расскажи про X». |
| **Tree traversal (level-wise DFS)** | RAPTOR | От корня вниз, на каждом уровне выбор top-K детей. | Когда вопрос имеет clear hierarchy — например, «marriage» → подкатегории. |
| **U-Retrieval** | MedGraphRAG | Top-down precise (от user-docs/L7 к L1) + bottom-up refinement (агрегация от L1 наверх). | **Default для BaCzy.** Top-down находит мастеровские эвристики L7, bottom-up подтягивает определения L1-L3 для контекста. |
| **Dual-level keyword retrieval** | LightRAG | LLM извлекает low-level keys (specific entities) + high-level keys (themes) → независимые поиски → merge. | Pre-step перед U-Retrieval: low-level = «桃花», «day master», high-level = «marriage signal». |
| **Multi-hop expansion (BFS/DFS)** | SG-RAG MOT, HopRAG (ACL 2025) | После top-K, expand на 1-2 hop по edges. | Для L7→L5 (от паттерна к звёздам) и L7→L4 (от паттерна к взаимодействиям). Ограничить depth=2. |
| **Hybrid retrieval с RRF** | Towards Practical GraphRAG (arXiv 2507.03226), KG-Retriever | Vector + BM25 + graph traversal → Reciprocal Rank Fusion. | Critical, если используется bge-m3 (dense+sparse). |
| **Cascaded retrieval с rerank** | SG-RAG, Hierarchical Lexical Graph (arXiv 2506.08074) | Шаг 1: high-recall graph traversal. Шаг 2: dense rerank. Шаг 3: cross-encoder rerank top-50→top-5. | **Обязательно** для BaCzy: без rerank L7-эвристики тонут. |
| **Agentic retrieval** | A-RAG (arXiv 2602.03442) | LLM-агент сам решает какой инструмент (keyword/semantic/chunk) и какой уровень дёргать. | V2 фича. На v1 — детерминистский pipeline проще отладить. |

### 4.2 Рекомендованный retrieval flow для BaCzy

```
User question
    ↓
[Step 1] LLM concept extractor (mini-call, Qwen3.6 / Kimi)
    Output: {
      low_keys: ["桃花", "day master strength"],
      high_keys: ["marriage", "current dayun"],
      target_topics: ["relationships"],
      target_levels: [L7, L6, L5]   # эвристика: чем applied вопрос — тем выше L
    }
    ↓
[Step 2] Two parallel queries в KuzuDB / FalkorDB:
    (a) Low-level: MATCH (n:Node) WHERE n.related_concepts INTERSECT $low_keys
                    AND n.level IN $target_levels
                    RETURN n ORDER BY n.source_authority DESC LIMIT 20
    (b) High-level: vector_search(embedding(question), top_k=20)
    ↓
[Step 3] RRF merge (a) ∪ (b) → top-30 candidate nodes
    ↓
[Step 4] Bottom-up refinement: для top-10 nodes уровня L≥5,
    pull supporting context из L≤3 (1-hop):
    MATCH (n)-[:REFERENCES|EXAMPLE_OF]->(m)
    WHERE n.id IN $top_ids AND m.level < n.level
    RETURN m LIMIT 20
    ↓
[Step 5] Cross-encoder rerank (Qwen3-Reranker-0.6B):
    score(question, node.summary) → top-7 nodes
    ↓
[Step 6] Format → [KNOWLEDGE] block, token budget 4-5K
    ↓
[Step 7] Inject в compose_messages между [BAZI_DATA] и [QUESTION]
```

Это **U-Retrieval (MedGraphRAG)** + **dual-level keys (LightRAG)** + **RRF hybrid (Towards Practical GraphRAG)** + **cross-encoder rerank**. Прямой композит из best-of-2025 практик.

### 4.3 Конкретные репозитории-примеры

- [parthsarthi03/raptor](https://github.com/parthsarthi03/raptor) — официальный RAPTOR. Эталон tree-based hierarchical retrieval.
- [HKUDS/LightRAG](https://github.com/hkuds/lightrag) — dual-level retrieval, KG construction + retrieval в одной системе.
- [SuperMedIntel/Medical-Graph-RAG](https://github.com/SuperMedIntel/Medical-Graph-RAG) — production-grade U-Retrieval, ACL 2025.
- [FalkorDB/GraphRAG-SDK](https://github.com/FalkorDB/GraphRAG-SDK) — swappable strategies (chunking, extraction, retrieval, reranking) поверх FalkorDB.
- [Ayanami0730/arag](https://github.com/Ayanami0730/arag) — A-RAG agentic hierarchical retrieval interfaces, SOTA на multi-hop QA.
- [zeroentropy-ai/legalbenchrag](https://github.com/zeroentropy-ai/legalbenchrag) — eval harness, можно адаптировать структуру тест-сетов для BaCzy.

---

## 5. Domain-specific Cases — что взять из медицины, права и TCM

### 5.1 OpenTCM (arXiv 2504.20118) — самый релевантный кейс

**Почему критичен для BaCzy:** OpenTCM — это **GraphRAG над древнекитайскими медицинскими текстами**. Стек, объёмы и проблемы практически идентичны:

- Источник: 68 гинекологических книг, 3.73 млн древнекитайских иероглифов → 48k entities, 152k relationships.
- LLM-извлечение через **Deepseek и Kimi** (custom prompts для ZH ancient texts).
- Категории сущностей: herbs / diseases / symptoms / treatments / herb references — в BaCzy будут stems / branches / ten gods / interactions / structures / patterns.
- **Точность: 94.6% → 98.55%** после GraphRAG vs flat prompts.
- Mean Expert Score (валидация людьми): 4.378/5 для retrieval, 4.045/5 для diagnostic Q&A.

**Что взять напрямую:**
- **Custom Chinese prompt** для LLM-extractor'а с **explicit glossary** of Bazi terms (стволы/ветви/боги — список, пиньинь, перевод).
- **Использовать Kimi** (он уже primary LLM в BaCzy) для extraction — он отлично понимает классический китайский.
- **Multi-relational schema** (не одна relation `REFERENCES`, а 5-7 семантических: GENERATES, CONTROLS, COMBINES_WITH, CLASHES_WITH, EXAMPLE_OF — что и заложено в плане).
- **Expert evaluation loop:** Богдан/учитель валидируют ответы по 5-балльной шкале — это metric для итерации.

### 5.2 MedGraphRAG (ACL 2025) — иерархия и U-Retrieval

3 уровня (user docs → credible texts → foundational) — для BaCzy мы расширили до 7, но **принцип U-Retrieval напрямую применим**. Ключевые элементы:

- **Provenance каждого узла** — `source` поле обязательно. В BaCzy → `source_authority` (1-10), где 10 = прямая цитата Богданова учителя.
- **Evidence-based генерация:** в финальный ответ Анастасии включать ссылку на узел (cite) — снижает галлюцинации, даёт Богдану аудит-trail.

### 5.3 MedRAG (WWW 2025) — diagnostic 4-tier KG

4-уровневая diagnostic KG = workflow клинициста (симптом → синдром → диф.диагноз → решение). Для BaCzy аналог: **вопрос → тема (отношения/карьера/здоровье) → правило мастера (L7) → подтверждение из звёзд/структур (L5-L6)**. Это и есть L7→L5 traversal из плана.

### 5.4 RareBench (KDD 2024) — random walk на иерархической онтологии

Использует **Information Content** значения phenotype graph для dynamic few-shot prompting. Для BaCzy менее применимо (у нас нет HPO-аналога), но идея **IC-weighted random walk вместо одинакового сэмплинга при retrieve'е** — интересна для V2.

### 5.5 LegalBench-RAG (arXiv 2408.10343)

Главный урок: **precision важнее recall**. 6858 query-answer пар с **human-annotated minimal text spans** — не «нужный документ», а «нужное конкретное предложение». Контекст-окно LLM ограничено, и retrieving раздутых чанков всё ломает.

**Применение к BaCzy:** Богдану нужно создать аналог LegalBench-RAG — 50-100 query-answer пар, где answer — **точная фраза/абзац** из L7 материалов учителя. Это становится eval-harness'ом для retrieval'а. Без этого «настройка ретривера» = тыкание пальцем.

### 5.6 Что НЕ работает (anti-patterns из всех кейсов)

1. **Auto-generated synthetic иерархия (RAPTOR-style без domain expert)** — для эзотерики/медицины проваливается, потому что LLM-кластеризация не знает доменной структуры. Для BaCzy с 5 стихиями / 10 стволами / 12 ветвями — иерархия **должна** быть expert-defined (что и сделано в плане).
2. **Flat embedding search без graph traversal** — теряет relational reasoning. Все 4 medical/legal benchmarks показывают +10-30% accuracy с графом.
3. **Один универсальный embedding для всего** — для CJK-доменов **обязательно** ZH-tuned модель. Generic multilingual без CMTEB-fine-tuning теряет 15-20% точности на терминах.
4. **Игнорировать source authority** — у мастера и Joey Yap могут быть **противоположные** трактовки 子辰合. Без authority-поля retrieval отдаёт случайную.
5. **Чрезмерный multi-hop** — beyond 2 hops accuracy падает (noise). Все 2025 papers фиксируют hop limit = 2.

---

## 6. Sources

### 6.1 Papers (arXiv / venues)

- [RAPTOR: Recursive Abstractive Processing for Tree-Organized Retrieval](https://arxiv.org/abs/2401.18059) — Sarthi et al., ICLR 2024.
- [Medical Graph RAG: Towards Safe Medical LLM via Graph RAG](https://arxiv.org/abs/2408.04187) — Wu et al., ACL 2025.
- [MedRAG: Enhancing RAG with KG-Elicited Reasoning for Healthcare Copilot](https://arxiv.org/abs/2502.04413) — Zhao et al., WWW 2025.
- [OpenTCM: A GraphRAG-Empowered LLM-based System for TCM](https://arxiv.org/abs/2504.20118) — He et al., 2025.
- [LightRAG: Simple and Fast Retrieval-Augmented Generation](https://arxiv.org/html/2410.05779v1) — Guo et al., EMNLP 2025.
- [Qwen3 Embedding: Advancing Text Embedding and Reranking Through Foundation Models](https://arxiv.org/abs/2506.05176) — Qwen team, 2025.
- [BGE M3-Embedding: Multi-Lingual, Multi-Functionality, Multi-Granularity Embeddings](https://arxiv.org/html/2402.03216v3) — Chen et al., 2024.
- [LegalBench-RAG: A Benchmark for RAG in the Legal Domain](https://arxiv.org/abs/2408.10343) — Pipitone & Alami, 2024.
- [RareBench: Can LLMs Serve as Rare Diseases Specialists?](https://arxiv.org/abs/2402.06341) — Chen et al., KDD 2024.
- [A-RAG: Scaling Agentic RAG via Hierarchical Retrieval Interfaces](https://arxiv.org/html/2602.03442v1) — 2026.
- [HCAG: Hierarchical Abstraction and RAG on Theoretical Repositories with LLMs](https://arxiv.org/abs/2603.20299) — 2026.
- [Towards Practical GraphRAG: Efficient KG Construction and Hybrid Retrieval at Scale](https://arxiv.org/abs/2507.03226) — 2025.
- [Hierarchical Lexical Graph for Enhanced Multi-Hop Retrieval](https://arxiv.org/html/2506.08074) — 2025.
- [When to use Graphs in RAG: A Comprehensive Analysis](https://arxiv.org/html/2506.05690v3) — 2025.
- [In-depth Analysis of Graph-based RAG in a Unified Framework](https://arxiv.org/pdf/2503.04338) — Zhou et al., 2025.
- [Graph Retrieval-Augmented Generation: A Survey](https://dl.acm.org/doi/10.1145/3777378) — ACM TOIS, 2025.

### 6.2 Repos (OSS)

- [parthsarthi03/raptor](https://github.com/parthsarthi03/raptor) — official RAPTOR.
- [HKUDS/LightRAG](https://github.com/hkuds/lightrag) — LightRAG framework.
- [SuperMedIntel/Medical-Graph-RAG](https://github.com/SuperMedIntel/Medical-Graph-RAG) — production U-Retrieval.
- [FalkorDB/FalkorDB](https://github.com/FalkorDB/FalkorDB) — GraphRAG-first graph DB.
- [FalkorDB/GraphRAG-SDK](https://github.com/FalkorDB/GraphRAG-SDK) — swappable strategies framework.
- [QwenLM/Qwen3-Embedding](https://github.com/QwenLM/Qwen3-Embedding) — Qwen3 embedding/reranker models.
- [Ayanami0730/arag](https://github.com/Ayanami0730/arag) — A-RAG SOTA agentic hierarchical retrieval.
- [zeroentropy-ai/legalbenchrag](https://github.com/zeroentropy-ai/legalbenchrag) — Legal eval harness.
- [chenxz1111/RareBench](https://github.com/chenxz1111/RareBench) — Rare-disease benchmark.
- [prrao87/kuzudb-study](https://github.com/prrao87/kuzudb-study) — Kuzu vs Neo4j benchmark study.

### 6.3 Engineering blogs / docs

- [Kuzu docs — Cypher differences](https://docs.kuzudb.com/cypher/difference/) — официальная документация (read-only после архивации).
- [The Register — KuzuDB graph database abandoned (2025-10-14)](https://www.theregister.com/2025/10/14/kuzudb_abandoned/) — статус архивации.
- [ArcadeDB — From KuzuDB to ArcadeDB: migration guide](https://arcadedb.com/blog/from-kuzudb-to-arcadedb-migration-guide/)
- [Vela Partners — KuzuDB Fork for AI Agents: 374× faster than Neo4j](https://vela.partners/blog/kuzudb-ai-agent-memory-graph-database)
- [FalkorDBLite: Embedded Python Graph Database](https://www.falkordb.com/blog/falkordblite-embedded-python-graph-database/)
- [Neo4j Engineering — Under the Covers With LightRAG: Retrieval](https://neo4j.com/blog/developer/under-the-covers-with-lightrag-retrieval/)
- [Microsoft Tech Community — Combining pgvector and Apache AGE](https://techcommunity.microsoft.com/blog/adforpostgresql/combining-pgvector-and-apache-age---knowledge-graph--semantic-intelligence-in-a-/4508781)
- [The Data Quarry — Kùzu, an extremely fast embedded graph database](https://thedataquarry.com/blog/embedded-db-2/)
- [BAAI/bge-m3 на Hugging Face](https://huggingface.co/BAAI/bge-m3)
- [Qwen/Qwen3-Embedding-0.6B на Hugging Face](https://huggingface.co/Qwen/Qwen3-Embedding-0.6B)
- [Qwen3 Embedding blog — Qwen team](https://qwenlm.github.io/blog/qwen3-embedding/)

---

## 7. Финальная рекомендация для BaCzy_bot

### 7.1 Стек (минимум-риска путь)

**Phase 1-2 (текущий план, до бутстрапа корпуса от учителя — 50 файлов):**
- **Хранилище:** оставить **KuzuDB 0.10.x** из ADR-004 — он работает, wheels доступны. **НО** заложить interface-адаптер `knowledge/store/base.py` (абстракция `GraphStore` с методами `upsert_node / upsert_edge / cypher_query / vector_search`), чтобы Phase 3+ свободно переехать на другой backend без переписывания retrieval-кода.
- **Embeddings:** **Qwen3-Embedding-0.6B** через `sentence-transformers` (или прямой `transformers` + HF model). Размер ~1.2 GB в Docker-образе, latency ~5-15 ms на CPU.
- **Reranker:** **Qwen3-Reranker-0.6B**.

**Phase 4+ (production-bootstrap):**
- **Migrate to FalkorDBLite** (если оставляем embedded) **или Apache AGE + pgvector** на Managed PG (если хочется консолидировать в один движок). Решение принимать после проверки: можно ли поставить AGE extension на Yandex Managed PostgreSQL.
- Migration cost через адаптер: переписать только `knowledge/store/falkordb_adapter.py` (~200-300 строк).

### 7.2 Schema (адаптация плана + uроки MedGraphRAG/OpenTCM)

К существующему плану добавить поля:
- `summary STRING` (LLM-генерированный 200-char TLDR — для cross-encoder rerank без передачи всего body).
- `embedding FLOAT[1024]` (Qwen3-0.6B dim).
- `source_authority INT64 (1-10)` (10 = прямая цитата учителя).
- `citations STRING[]` (откуда взято — для evidence-based ответа Анастасии).
- `language STRING` (ru / zh / mixed — для оптимального retrieval).

### 7.3 Retrieval pattern (композит U-Retrieval + LightRAG dual-keys + RRF rerank)

```
Question → Concept Extractor (low/high keys + target_levels + topics)
        → Parallel: graph_keyword_query + vector_search
        → RRF merge → top-30
        → Bottom-up refinement (pull supporting L≤3 для каждого top L≥5)
        → Cross-encoder rerank → top-7
        → Format [KNOWLEDGE] block (4-5K tokens)
        → Inject в compose_messages
```

### 7.4 Process: eval-harness обязателен с самого старта

Сделать в Phase 2 первый прототип **BaCzy-RAG-eval-mini** по образцу LegalBench-RAG-mini:
- 30-50 (question, expected_answer_span, expected_source_node_id) троек, написанных Богданом или учителем.
- Метрики: Recall@5, Recall@10, MRR, faithfulness (LLM-as-judge: «опирается ли ответ на retrieved nodes?»).
- Запускать **на каждом крупном изменении схемы / retrieval'а**, чтобы регрессий не было.

### 7.5 Что НЕ делать

1. ❌ Не использовать Microsoft GraphRAG как фреймворк — ингест на 100 файлов будет стоить >$400 и идти часы. Для нашего корпуса избыточен.
2. ❌ Не использовать generic multilingual embedding (LaBSE, mpnet) — провалится на 桃花/七杀.
3. ❌ Не делать synthetic иерархию через recursive LLM-clustering (как RAPTOR-only) — потеряем экспертную структуру L1-L7.
4. ❌ Не пытаться достичь >2 hop multi-hop traversal — noise.
5. ❌ Не пропускать reranker — без cross-encoder L7-эвристики растворятся среди L1.

### 7.6 Краткое summary архитектурного решения

| Компонент | Выбор | Обоснование (1 предложение) |
|---|---|---|
| Graph store (Phase 1-2) | KuzuDB 0.10.x + адаптер `GraphStore` | Сохраняет план, минимизирует риск переписывания |
| Graph store (Phase 4+) | FalkorDBLite или AGE+pgvector | После архивации Kuzu выбираем активно развивающийся stack |
| Embedding | Qwen3-Embedding-0.6B | Топ ZH, нативно RU, 32K ctx, Apache 2.0, 1.2 GB |
| Reranker | Qwen3-Reranker-0.6B | Симметрия с embedding, обязательная стадия precision |
| Retrieval | U-Retrieval + LightRAG dual-keys + RRF + rerank | Композит лучших практик 2025 без хака |
| LLM-extractor (ingest) | Kimi (через OpenRouter, уже primary в BaCzy) | OpenTCM подтверждает: Kimi отлично понимает классический ZH |
| Eval | BaCzy-RAG-eval-mini (50 пар) | LegalBench-RAG урок: без eval'а нельзя итеративно настраивать retrieval |
| Hop limit | 2 | 2025 papers единодушно: >2 — noise |
| Cite в ответе | yes | MedGraphRAG, OpenTCM: evidence-based — снижает галлюцинации |

---

**Документ подготовлен:** 2026-05-17, research-agent (Claude Opus 4.7 1M ctx).
**Следующий шаг по плану:** Phase 0 → задача 0.2 (структура `База/teacher/`) + 0.3 (конвертация PDF курса).
