# БаЦзы-Бот — Мастер-документ проекта

> Telegram-бот для персональных AI-консультаций по системе Ба Цзы (四柱命理)
> с консультантом Анастасией. Высокоточный расчёт + мульти-модельный AI.

**Разработчик:** Богдан
**Дата старта:** март 2026
**Статус:** 📦 Упакован к разработке (май 2026)
**Версия документа:** 3.1

---

## Суть проекта

AI-бот в Telegram, который:

1. Рассчитывает карту Ба Цзы по данным рождения (Python, высокоточный калькулятор на Swiss Ephemeris)
2. Генерирует интерактивную HTML-визуализацию карты (FastAPI + HTMX + Chart.js)
3. Ведёт персональные консультации через мульти-модельный AI (Claude Sonnet + Qwen 3.6 + Kimi)
4. Монетизируется через подписку Pro (Free: 3 вопроса/день, Pro: безлимит)

---

## Документация

| Документ                                                                                                   | Описание                                                                                                                                |
| ---------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| [product_idea.md](product_idea.md)                                                                         | Бизнес-идея: проблема, решение, ЦА, монетизация, метрики, конкуренты, риски                                                             |
| [doc/vision.md](doc/vision.md)                                                                             | **Техническое видение v3.0**: стек, DDD, структура, архитектура, модель данных, LLM, мониторинг, деплой, конфигурирование, логгирование |
| [doc/Создание высокоточного калькулятора БаЦзы.md](doc/Создание%20высокоточного%20калькулятора%20БаЦзы.md) | Архитектурные стандарты калькулятора: Swiss Ephemeris, TST, Цзе Ци, Шэнь Ша, Да Юнь                                                     |
| [База/ba_zi_prompt_anastasia_v2.md](База/ba_zi_prompt_anastasia_v2.md)                                     | Системный промпт (68 КБ): полная методология Цзы Пин, 10 Божеств, взаимодействия, примеры                                               |

---

## Ключевые решения

| Решение        | Выбор                                 | Почему                                               |
| -------------- | ------------------------------------- | ---------------------------------------------------- |
| AI провайдер   | OpenRouter API                        | Один ключ: Kimi + Claude                            |
| AI основная    | Kimi 2.6 (moonshotai)                 | Специализация на китайских текстах (Бацзы)           |
| AI fallback    | Claude 3.5 Sonnet                     | Резервная при недоступности Kimi                     |
| Визуал карты   | Playwright HTML→PNG                   | 100% точные иероглифы, CSS верстка в стиле Mingli   |
| Ассеты         | 24 PNG иероглифов ✅                  | Иероглифы как картинки, Pillow fallback              |
| База знаний    | KuzuDB (embedded graph)               | RAG: граф правил Бацзы → в контекст LLM             |
| Расчёт карты   | Высокоточный сервис (Swiss Ephemeris) | Точность < 0.001", TST, 24 сезона, 50-90 звёзд      |
| Architecture   | DDD (Domain-Driven Design)            | Чистое разделение бизнес-логики и транспортных слоёв |
| БД             | PostgreSQL + UUID                     | Production-ready, безопасные ID                      |
| Хостинг        | Yandex Cloud (VPS + managed)          | PostgreSQL, Redis, Object Storage — всё managed      |
| Хранилище файл | Yandex Object Storage (S3)            | PNG карты, CSV экспорт диалогов                      |
| Мониторинг LLM | Langfuse (self-hosted)                | Cost, latency, quality tracking                      |
| Очереди        | TaskIQ                                | Async Python, фоновые AI-генерации                   |
| Монетизация    | Базовая интерпретация ВСЕГДА бесплатно + 3 тарифа | Конверсия через демонстрацию ценности |
| Тарифы         | Месяц 290₽ / 3 месяца 990₽ / Год 2490₽ | Unit-экономика: ~1-6 RUB/запрос через Kimi |
| Платежи        | ЮKassa                                | Привычно для русскоязычной аудитории                 |
| Админ-панель   | Telegram /admin + FastAPI Basic Auth  | Статистика, экспорт диалогов, смена модели LLM       |

---

## Стек

### Core

| Компонент     | Технология              |
| ------------- | ----------------------- |
| Язык          | Python 3.11+            |
| Bot framework | aiogram 3.x (async)     |
| Web framework | FastAPI + Jinja2 + HTMX |
| ORM           | SQLAlchemy 2.0 (async)  |
| Миграции      | Alembic                 |
| БД            | PostgreSQL (production) |
| Кэш           | Redis                   |

### AI/LLM

| Компонент        | Технология                             |
| ---------------- | -------------------------------------- |
| AI провайдер     | OpenRouter API (единая точка)          |
| Основная модель  | Kimi 2.6 (moonshotai/kimi-2.6)        |
| Резервная модель | Claude 3.5 Sonnet (anthropic)          |
| Рендеринг карты  | Playwright (Headless Chrome HTML→PNG)  |
| База знаний      | KuzuDB (embedded graph database)       |
| Мониторинг       | Langfuse                               |

### Астрономическое ядро

| Компонент        | Технология                          |
| ---------------- | ----------------------------------- |
| Swiss Ephemeris  | pyswisseph (JPL DE431)              |
| Геокодирование   | geopy (Nominatim) + GeoNames        |
| Таймзоны         | timezonefinder + TZ Database (IANA) |
| DST история      | pytz                                |
| Equation of Time | Jean Meeus / NOAA                   |

### Инфраструктура и DevOps

| Компонент        | Технология                               |
| ---------------- | ---------------------------------------- |
| Очереди задач    | TaskIQ                                   |
| Контейнеризация  | Docker + docker-compose                  |
| CI/CD            | GitHub Actions                           |
| Хостинг          | Yandex Cloud (Compute Cloud VPS)         |
| БД managed       | Yandex Managed PostgreSQL                |
| Кэш managed      | Yandex Managed Redis                     |
| Файлы            | Yandex Object Storage (S3-совместимый)   |
| SSL              | Yandex Certificate Manager              |
| Линтинг          | ruff + mypy + pre-commit                |
| Тесты            | pytest + pytest-asyncio                  |
| Логи             | structlog + trace_id middleware          |

### Подготовительные ресурсы

| Ресурс | Описание | Статус |
|--------|----------|--------|
| 24 PNG ассета иероглифов | 10 стволов + 12 ветвей + 2 Инь/Ян в стиле Mingli | ✅ Готово |
| Swiss Ephemeris данные | JPL DE431 ephe files (se1-ephe.zip) | ⏳ Скачать |
| OpenRouter API key | Зарегистрирован, ключ в .env | ✅ Готово |
| Gemini Deep Research | 6 исследований по архитектуре | ✅ Готово |
| Yandex Cloud ресурсы | VPS + PostgreSQL + Redis + Object Storage | ⏳ Настроить (см. deploy.md) |

---

## Исследования (Gemini Deep Research)

Перед финальным закреплением стека провести исследование:

1. **KuzuDB vs Neo4j** — для embedded RAG в Python-сервисе
2. **Playwright vs Pillow** — для fallback рендеринга карты если gpt-image-1 недоступен
3. **OpenRouter Kimi K2 pricing** — актуальные цены vs прямой Kimi API
4. **Yandex Cloud vs Selectel** — стоимость для нашей конфигурации
5. **FSM паттерны в aiogram 3.x + Redis** — для многошагового сбора данных рождения
6. **Yandex Object Storage SDK** — aioboto3 vs yandex-cloud-python-sdk

---

## Архитектура проекта

### Общая схема

```
Telegram Clients
       │
       ▼
┌──────────────────────────────────┐
│  Telegram Bot (aiogram 3.x)      │
│  Routers → Middlewares → FSM     │
└────────┬───────────┬─────────────┘
         │           │
         ▼           ▼
┌──────────────┐ ┌────────────────┐
│ Calculator   │ │ AI Orchestrator│
│ (stateless)  │ │ (LiteLLM)      │
│ pyswisseph   │ │ Claude/Qwen/Kimi│
└──────┬───────┘ └───────┬────────┘
       │                 │
       ▼                 ▼
┌──────────────┐ ┌────────────────┐
│ PostgreSQL   │ │ Langfuse       │
│ Redis        │ │ (monitoring)   │
└──────────────┘ └────────────────┘
                       │
                       ▼
┌──────────────────────────────────┐
│  Web Visualization (FastAPI)     │
│  Jinja2 + HTMX + Chart.js        │
│  Telegram Mini App               │
└──────────────────────────────────┘
```

### Структура проекта

```
BaDzi_bot/
├── bot/                          # Telegram-бот слой (aiogram)
│   ├── main.py                   # Entry point
│   ├── config.py                 # Pydantic Settings
│   ├── routers/                  # start, consultation, chart, profile, ...
│   ├── middlewares/              # db_session, user, tracing
│   ├── keyboards/                # Inline keyboards
│   ├── states.py                 # FSM states
│   └── filters.py                # Magic filters
│
├── calculator/                   # Чистое ядро Бацзы (stateless, DDD)
│   ├── models.py                 # Pydantic модели (ChartInput, ChartOutput)
│   ├── swiss.py                  # pyswisseph интеграция
│   ├── solar_terms.py            # 24 сезона Цзе Ци
│   ├── true_solar_time.py        # TST: LMT + EoT + DST
│   ├── pillars.py                # Генерация 4 столпов
│   ├── hidden_stems.py           # Скрытые стволы (3 школы)
│   ├── ten_gods.py               # 10 Божеств
│   ├── interactions.py           # 合沖刑害破
│   ├── luck_pillars.py           # Столпы Удачи (до минуты)
│   ├── symbolic_stars.py         # 50-90 Шэнь Ша
│   ├── auxiliary.py              # Мин Гун, Тай Юань
│   └── day_master.py             # Сила ДМ, полезное/вредное
│
├── ai/                           # AI Orchestrator
│   ├── orchestrator.py           # LiteLLM сервис
│   ├── router.py                 # Семантический маршрутизатор
│   ├── fallback.py               # Фолбэк между моделями
│   ├── synthesis.py              # Синтез ответов
│   ├── context.py                # Управление контекстом
│   └── prompts/                  # Системные промпты
│
├── web/                          # FastAPI — визуализация
│   ├── main.py                   # Entry point
│   ├── routes/                   # chart, api, telegram_webapp
│   ├── templates/                # Jinja2 + HTMX
│   └── static/                   # CSS, JS (Chart.js)
│
├── db/                           # Database
│   ├── models.py                 # SQLAlchemy (User, Chart, Consultation, ...)
│   ├── engine.py                 # Async engine
│   └── repositories/             # User, Chart, Consultation, Subscription
│
├── tasks/                        # TaskIQ фоновые задачи
│   ├── ai_generation.py          # Долгие AI-генерации
│   └── notifications.py          # Прогнозы, алерты
│
├── monitoring/                   # Langfuse
├── migrations/                   # Alembic
├── tests/                        # pytest (unit, integration, e2e)
├── docs/                         # MkDocs (алгоритмы Бацзы)
├── .github/workflows/ci.yml      # CI/CD
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
├── .env.example
└── MASTER.md
```

### Модель данных (ключевые сущности)

| Сущность         | Описание                             | Ключевые поля                                             |
| ---------------- | ------------------------------------ | --------------------------------------------------------- |
| **User**         | Пользователь Telegram                | telegram_id, locale, created_at                           |
| **Chart**        | Карта Бацзы                          | birth_datetime, lat/lon, chart_data (JSONB), early_rat    |
| **Consultation** | Лог AI-консультации                  | user_id, chart_id, model_used, tokens, cost_usd, trace_id |
| **Subscription** | Подписка                             | plan, status, daily_questions_used, expires_at            |
| **Event**        | Жизненное событие (для ректификации) | chart_id, event_date, event_type                          |

Все первичные ключи — **UUID v4**.

---

## Сценарии работы

### Основное flow

```
/start → FSM (дата → время → город → пол) → Calculator → Карта в БД
→ AI-консультация (Claude/Qwen/Kimi) → Диалог → История в БД
```

### Edge cases

| Ситуация              | Обработка                                                          |
| --------------------- | ------------------------------------------------------------------ |
| Нет времени рождения  | Карта на 12:00, предупреждение о точности, отключение анализа часа |
| LLM недоступен        | Фолбэк: Claude → Qwen → Kimi                                       |
| LLM timeout (>30 сек) | TaskIQ: задача в фон, бот: "Звёзды считают..."                     |
| Пользователь спамит   | Redis rate limiter: 3 вопроса/день (Free)                          |

---

## Монетизация

| Тариф     | Цена       | Включено                                   |
| --------- | ---------- | ------------------------------------------ |
| Free      | 0 руб.     | Расчёт карты + визуал + 1 бесплатный вопрос |
| Месяц     | 290 руб.   | Безлимит, все темы, история консультаций   |
| 3 месяца  | 990 руб.   | Выгода 43%                                 |
| Год       | 2 490 руб. | Выгода 28%                                 |

---

## Дорожная карта

### Этап 1 — MVP (март-апрель 2026)

Структура проекта → Модели БД → FSM → pyswisseph → TST → Калькулятор (4 столпа, ДМ, 10 Божеств) → LiteLLM (Claude) → Промпт Анастасии → Консультация → Лимиты → Подписка → Docker → CI/CD → Деплой на Railway

### Этап 2 — Расширение (май-июнь 2026)

Цзе Ци → Столпы Удачи → Все взаимодействия → 3 школы скрытых стволов → 50-90 звёзд → Мин Гун/Тай Юань → Qwen + Kimi → AI-маршрутизатор → Синтез → Фолбэк → Langfuse → TaskIQ

### Этап 3 — Визуализация (Q3 2026)

FastAPI → Jinja2 + HTMX → Chart.js → Цветовое кодирование → Интерактивные подсказки → Уникальные токены → Telegram Mini App → Встроенный чат

### Этап 4 — Рост (Q4 2026)

Ежедневные прогнозы → Реферальная программа → Мультиязычность → Кэш интерпретаций → A/B тесты → Векторная память (pgvector) → Ректификация
