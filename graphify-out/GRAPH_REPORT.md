# Graph Report - .  (2026-04-14)

## Corpus Check
- Corpus is ~21,442 words - fits in a single context window. You may not need a graph.

## Summary
- 50 nodes · 78 edges · 6 communities detected
- Extraction: 88% EXTRACTED · 12% INFERRED · 0% AMBIGUOUS · INFERRED: 9 edges (avg confidence: 0.77)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_AI Мульти-модельная Оркестрация|AI Мульти-модельная Оркестрация]]
- [[_COMMUNITY_Продукт и Визуализация|Продукт и Визуализация]]
- [[_COMMUNITY_Калькулятор Бацзы (ядро)|Калькулятор Бацзы (ядро)]]
- [[_COMMUNITY_Метафизические элементы карты|Метафизические элементы карты]]
- [[_COMMUNITY_Бот-инфраструктура (Telegram, Redis, FSM)|Бот-инфраструктура (Telegram, Redis, FSM)]]
- [[_COMMUNITY_Хронобиология (TST, DST, геокодирование)|Хронобиология (TST, DST, геокодирование)]]

## God Nodes (most connected - your core abstractions)
1. `Высокоточный калькулятор Бацзы` - 19 edges
2. `AI Orchestrator (мульти-модельный)` - 12 edges
3. `Техническое видение v3.0` - 12 edges
4. `БаЦзы-Бот Project` - 7 edges
5. `Telegram Bot (aiogram 3.x)` - 6 edges
6. `Истинное солнечное время (TST)` - 5 edges
7. `Claude Sonnet (основная модель)` - 5 edges
8. `Qwen 3.6 (верификация)` - 4 edges
9. `Kimi (Moonshot AI, верификация)` - 4 edges
10. `Фолбэк-механизм` - 4 edges

## Surprising Connections (you probably didn't know these)
- `Pydantic Settings (.env)` --conceptually_related_to--> `БаЦзы-Бот Project`  [EXTRACTED]
  doc/vision.md → MASTER.md
- `БаЦзы-Бот Project` --conceptually_related_to--> `Высокоточный калькулятор Бацзы`  [EXTRACTED]
  MASTER.md → doc/Создание высокоточного калькулятора БаЦзы.md
- `БаЦзы-Бот Project` --conceptually_related_to--> `AI Orchestrator (мульти-модельный)`  [EXTRACTED]
  MASTER.md → doc/vision.md
- `БаЦзы-Бот Project` --conceptually_related_to--> `HTML-визуализация (Jinja2 + HTMX + Chart.js)`  [EXTRACTED]
  MASTER.md → doc/vision.md
- `БаЦзы-Бот Project` --conceptually_related_to--> `Модель монетизации (Free/Pro)`  [EXTRACTED]
  MASTER.md → product_idea.md

## Hyperedges (group relationships)
- **Калькулятор Бацзы — компоненты** — four_pillars, ten_gods, day_master, hidden_stems, interactions, luck_pillars, symbolic_stars, ming_gong, tai_yuan, qi_phases [EXTRACTED 1.00]
- **Мульти-модельный AI** — claude_sonnet, qwen_36, kimi_moonshot [EXTRACTED 1.00]
- **AI Pipeline** — ai_router, ai_orchestrator, ai_synthesis, ai_fallback [EXTRACTED 1.00]
- **Хронобиологический модуль** — true_solar_time, equation_of_time, geocoding, tz_database, dst_history [EXTRACTED 1.00]

## Communities

### Community 0 - "AI Мульти-модельная Оркестрация"
Cohesion: 0.38
Nodes (10): Фолбэк-механизм, AI Orchestrator (мульти-модельный), Семантический маршрутизатор, Синтез ответов, Claude Sonnet (основная модель), Kimi (Moonshot AI, верификация), Langfuse (LLM monitoring), LiteLLM (SDK-агрегатор) (+2 more)

### Community 1 - "Продукт и Визуализация"
Cohesion: 0.22
Nodes (10): AI-консультант Анастасия, БаЦзы-Бот Project, GitHub Actions (CI/CD), Docker + Railway (деплой), FastAPI Web Visualization, HTML-визуализация (Jinja2 + HTMX + Chart.js), ruff + mypy + pre-commit, Модель монетизации (Free/Pro) (+2 more)

### Community 2 - "Калькулятор Бацзы (ядро)"
Cohesion: 0.25
Nodes (9): Высокоточный калькулятор Бацзы, Domain-Driven Design, Дилемма Часа Крысы (Early/Late Rat), Четыре столпа (年月日時), Фазы Ци (процент элементов), 24 сезона Цзе Ци, Swiss Ephemeris (JPL DE431), Столп Зачатия (Тай Юань) (+1 more)

### Community 3 - "Метафизические элементы карты"
Cohesion: 0.25
Nodes (8): Дневной Мастер (日主), Скрытые стволы (3 школы), Взаимодействия (合沖刑害破), Столпы Удачи (大運), Дворец Жизни (Мин Гун), PostgreSQL (UUID primary keys), Символические звёзды (Шэнь Ша), Техническое видение v3.0

### Community 4 - "Бот-инфраструктура (Telegram, Redis, FSM)"
Cohesion: 0.32
Nodes (8): Telegram Bot (aiogram 3.x), Feature flags (Redis), FSM: сбор данных рождения, PII masking в логах, Pydantic Settings (.env), Rate limiting (3 вопроса/день Free), Redis (cache, FSM, rate limiting), structlog + trace_id middleware

### Community 5 - "Хронобиология (TST, DST, геокодирование)"
Cohesion: 0.4
Nodes (5): Исторические DST (pytz + IANA), Уравнение времени (Jean Meeus/NOAA), Геокодирование (geopy + GeoNames), Истинное солнечное время (TST), TZ Database + timezonefinder

## Knowledge Gaps
- **9 isolated node(s):** `LiteLLM (SDK-агрегатор)`, `PostgreSQL (UUID primary keys)`, `Дилемма Часа Крысы (Early/Late Rat)`, `Уравнение времени (Jean Meeus/NOAA)`, `Геокодирование (geopy + GeoNames)` (+4 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `Высокоточный калькулятор Бацзы` connect `Калькулятор Бацзы (ядро)` to `Продукт и Визуализация`, `Метафизические элементы карты`, `Бот-инфраструктура (Telegram, Redis, FSM)`, `Хронобиология (TST, DST, геокодирование)`?**
  _High betweenness centrality (0.604) - this node is a cross-community bridge._
- **Why does `БаЦзы-Бот Project` connect `Продукт и Визуализация` to `AI Мульти-модельная Оркестрация`, `Калькулятор Бацзы (ядро)`, `Бот-инфраструктура (Telegram, Redis, FSM)`?**
  _High betweenness centrality (0.349) - this node is a cross-community bridge._
- **Why does `AI Orchestrator (мульти-модельный)` connect `AI Мульти-модельная Оркестрация` to `Продукт и Визуализация`, `Калькулятор Бацзы (ядро)`, `Бот-инфраструктура (Telegram, Redis, FSM)`?**
  _High betweenness centrality (0.347) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `Высокоточный калькулятор Бацзы` (e.g. with `FastAPI Web Visualization` and `Domain-Driven Design`) actually correct?**
  _`Высокоточный калькулятор Бацзы` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 2 inferred relationships involving `AI Orchestrator (мульти-модельный)` (e.g. with `TaskIQ (background tasks)` and `Domain-Driven Design`) actually correct?**
  _`AI Orchestrator (мульти-модельный)` has 2 INFERRED edges - model-reasoned connections that need verification._
- **What connects `LiteLLM (SDK-агрегатор)`, `PostgreSQL (UUID primary keys)`, `Дилемма Часа Крысы (Early/Late Rat)` to the rest of the system?**
  _9 weakly-connected nodes found - possible documentation gaps or missing edges._