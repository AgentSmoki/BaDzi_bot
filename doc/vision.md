# БаЦзы-Бот — Техническое видение проекта

> Профессиональный AI-консультант по Ба Цзы: высокоточный расчёт + мульти-модельный AI

**Версия:** 3.0 (Technical Vision)
**Дата:** Апрель 2026
**Статус:** Отправная точка для разработки

---

## 0. Миссия и контекст

Создание профессионального Telegram-бота и экосистемы для расчёта карт Бацзы экспертного уровня. Интеграция высокоточных астрономических алгоритмов (Swiss Ephemeris) и LLM-оркестрации для предоставления персонализированных, глубоких метафизических консультаций, превосходящих стандартные шаблонные расшифровки.

**Ключевые принципы:**

- Расчёт карты — в коде (детерминированный, точный), AI — только интерпретация
- Астрономическая точность: Swiss Ephemeris (JPL DE431), TST, уравнение времени
- Мульти-модельный AI: Claude Sonnet + Qwen 3.6 + Kimi
- Domain-Driven Design: чистое разделение бизнес-логики и транспортных слоёв

---

## 1. Технологии

### 1.1. Язык и рантайм

| Компонент | Версия | Обоснование                                                                    |
| --------- | ------ | ------------------------------------------------------------------------------ |
| Python    | 3.11+  | Стабильный, максимальная совместимость (pyswisseph, aiogram, SQLAlchemy async) |

### 1.2. Основные фреймворки

| Компонент     | Технология             | Назначение                                               |
| ------------- | ---------------------- | -------------------------------------------------------- |
| Bot framework | aiogram 3.x (async)    | Telegram-бот, FSM, inline keyboards, middleware, routers |
| Web framework | FastAPI                | HTML-визуализация карты, REST API, Telegram Web App      |
| ORM           | SQLAlchemy 2.0 (async) | Работа с PostgreSQL (async engine)                       |
| Миграции БД   | Alembic                | Управление схемой БД                                     |
| Шаблонизатор  | Jinja2 + HTMX          | Серверный рендеринг + интерактивность без тяжёлого JS    |
| Charts        | Chart.js               | Radar charts для 10 Божеств и баланса элементов          |

### 1.3. AI/LLM

| Компонент       | Технология                    | Назначение                                                     |
| --------------- | ----------------------------- | -------------------------------------------------------------- |
| Основная модель | Claude 3.5 Sonnet (Anthropic) | Основной ответ, русский язык, глубина анализа, длинные промпты |
| Верификация 1   | Qwen 3.6 (DashScope/Alibaba)  | Анализ структуры карты, китайская метафизика, недорогой        |
| Верификация 2   | Kimi (Moonshot AI)            | Проверка тонкостей классической школы, работа с иероглифами    |
| SDK-агрегатор   | LiteLLM                       | Унифицированный интерфейс для всех LLM-провайдеров             |

### 1.4. Астрономическое ядро

| Компонент       | Технология                       | Назначение                                         |
| --------------- | -------------------------------- | -------------------------------------------------- |
| Swiss Ephemeris | pyswisseph (Python-биндинги к C) | Точные расчёты положения Солнца, сезонов Цзе Ци    |
| Ephemeris data  | JPL DE431 (через Swiss Eph)      | Астрономические данные, точность < 0.001"          |
| Solar Terms     | Собственный алгоритм             | Вычисление 24 сезонов по эклиптической долготе (λ) |

### 1.5. Хронобиология и гео

| Компонент        | Технология                   | Назначение                                              |
| ---------------- | ---------------------------- | ------------------------------------------------------- |
| Геокодирование   | geopy (Nominatim) + GeoNames | Город → координаты (lat, lon)                           |
| Таймзоны         | timezonefinder               | Координаты → таймзона                                   |
| DST история      | pytz + TZ Database (IANA)    | Исторические переходы на летнее время                   |
| Equation of Time | Алгоритм Jean Meeus / NOAA   | Коррекция ±16 минут (эллиптичность орбиты + наклон оси) |

### 1.6. Инфраструктура

| Компонент      | Технология              | Назначение                                                    |
| -------------- | ----------------------- | ------------------------------------------------------------- |
| База данных    | PostgreSQL (production) | Основное хранилище (user, chart, consultation, subscription)  |
| Кэширование    | Redis                   | FSM-состояния, сессии, расчёты, типовые ответы, feature flags |
| Брокер задач   | TaskIQ                  | Фоновые задачи для долгих AI-генераций (>10 сек)              |
| Мониторинг LLM | Langfuse (self-hosted)  | Логирование вызовов LLM, cost, latency, quality tracking      |
| Хостинг        | Railway                 | Деплой бота, FastAPI, PostgreSQL, Redis                       |

### 1.7. Внешние зависимости

```
# Core
aiogram>=3.0
fastapi>=0.110
uvicorn[standard]>=0.29
sqlalchemy>=2.0
alembic>=1.13
pydantic>=2.0
pydantic-settings>=2.0

# AI
litellm>=1.40

# Astronomy & Geo
pyswisseph>=2.10
geopy>=2.4
timezonefinder>=6.0
pytz>=2024.1

# Infra
redis>=5.0
taskiq>=0.11
httpx>=0.27
python-dotenv>=1.0

# Templates & Charts
jinja2>=3.1
htmx (CDN)
chart.js (CDN)

# Dev
ruff>=0.4
mypy>=1.10
pytest>=8.0
pytest-asyncio>=0.23
structlog>=24.1
pre-commit>=3.7
```

---

## 2. Принцип разработки

### 2.1. Архитектурный подход: Domain-Driven Design (DDD)

**Ключевые принципы:**

- **Жёсткое разделение слоёв:** бизнес-логика (расчёт Бацзы) полностью независима от транспортного слоя (Telegram, HTTP API)
- **Calculator — чистое ядро:** stateless, на вход получает `datetime + координаты + tz`, на выход отдаёт стандартизированный JSON с картой и графом взаимодействий
- **Порты и адаптеры:** AI-провайдеры, БД, геокодирование — всё через абстрактные интерфейсы

### 2.2. Code style и стандарты

| Инструмент   | Назначение                                                                   |
| ------------ | ---------------------------------------------------------------------------- |
| `ruff`       | Линтинг + форматирование (заменяет flake8, black, isort — в 10-100x быстрее) |
| `mypy`       | Строгая статическая типизация (strict mode)                                  |
| `pre-commit` | Хуки перед коммитом: ruff check + ruff format + mypy                         |

**Стандарты кода:**

- Строгая типизация: все функции с type hints, `mypy --strict`
- Документация сложных алгоритмов в docstrings (расчёт Цзе Ци, TST, 60-ричный цикл)
- Запрет `!` в строках ответов Анастасии (правило валидации в коде)

### 2.3. Git workflow

- **GitHub Flow:** защищённая ветка `main`, разработка в `feature/<name>` ветках
- **PR обязатель:** code review минимум 1 ревьюер перед merge
- **Commit messages:** Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`)
- **Семантическое версионирование:** `v<major>.<minor>.<patch>`

### 2.4. Документация

| Тип              | Инструмент                | Описание                                             |
| ---------------- | ------------------------- | ---------------------------------------------------- |
| Алгоритмы Бацзы  | MkDocs                    | Правила слияний, расчёт часов Крысы, Цзе Ци, Шэнь Ша |
| API документация | Swagger/OpenAPI           | Автогенерация из FastAPI (из коробки)                |
| README.md        | Markdown                  | Быстрый старт, деплой, конфигурация                  |
| inline docs      | Docstrings (Google style) | Каждый модуль, класс, публичная функция              |

### 2.5. Тестирование

| Уровень     | Инструмент              | Покрытие                                 |
| ----------- | ----------------------- | ---------------------------------------- |
| Unit        | pytest + pytest-asyncio | Калькулятор, парсеры, утилиты            |
| Integration | pytest + TestContainer  | БД, Redis, AI-вызовы (mock)              |
| E2E         | aiogram testing         | Критичные user flows (FSM, консультация) |

**Целевое покрытие:** 80%+ для `calculator/`, 60%+ для `bot/`

---

## 3. Структура проекта

```
BaDzi_bot/
├── bot/                          # Telegram-бот слой
│   ├── main.py                   # Entry point бота
│   ├── config.py                 # Pydantic Settings
│   ├── routers/                  # aiogram routers
│   │   ├── start.py              # /start, сбор данных рождения
│   │   ├── consultation.py       # Консультация, выбор темы
│   │   ├── chart.py              # Просмотр карты, визуализация
│   │   ├── profile.py            # Профиль пользователя
│   │   ├── history.py            # История консультаций
│   │   ├── subscription.py       # Управление подпиской
│   │   ├── admin.py              # Админ-панель
│   │   └── support.py            # Поддержка
│   ├── middlewares/
│   │   ├── db_session.py         # Инъекция DB сессии
│   │   ├── user_middleware.py    # Авторизация пользователя
│   │   └── tracing.py            # trace_id middleware
│   ├── keyboards/                # Inline keyboards
│   ├── states.py                 # FSM states
│   └── filters.py                # Magic filters
│
├── calculator/                   # Чистое ядро Бацзы (stateless)
│   ├── __init__.py
│   ├── models.py                 # Pydantic модели карты (ChartInput, ChartOutput)
│   ├── swiss.py                  # pyswisseph интеграция
│   ├── solar_terms.py            # 24 сезона Цзе Ци (вычисление моментов)
│   ├── true_solar_time.py        # TST: LMT + EoT + DST + longitude
│   ├── pillars.py                # Генерация 4 столпов (年月日時)
│   ├── hidden_stems.py           # Скрытые стволы (3 школы)
│   ├── ten_gods.py               # Маппинг 10 Божеств
│   ├── interactions.py           # Слияния, столкновения, наказания, вред
│   ├── luck_pillars.py           # Столпы Удачи (Да Юнь) до минуты
│   ├── symbolic_stars.py         # 50-90 Шэнь Ша
│   ├── auxiliary.py              # Мин Гун, Тай Юань
│   ├── day_master.py             # Сила ДМ, полезное/вредное божество
│   └── structure.py              # Структура карты (格局), Фазы Ци
│
├── ai/                           # AI Orchestrator
│   ├── orchestrator.py           # Главный AI-сервис (LiteLLM)
│   ├── router.py                 # Семантический маршрутизатор намерений
│   ├── fallback.py               # Фолбэк-механизм между моделями
│   ├── synthesis.py              # Синтез ответов от нескольких моделей
│   ├── prompts/
│   │   ├── anastasia_system.md   # Системный промпт Анастасии (68 КБ)
│   │   ├── verifier_qwen.md      # Промпт для Qwen
│   │   └── verifier_kimi.md      # Промпт для Kimi
│   ├── context.py                # Управление контекстом (history, memory)
│   └── models.py                 # AI request/response модели
│
├── web/                          # FastAPI — визуализация + API
│   ├── main.py                   # Entry point FastAPI
│   ├── routes/
│   │   ├── chart.py              # GET /chart/{id} — HTML-страница карты
│   │   ├── api.py                # REST API endpoints
│   │   └── telegram_webapp.py    # Telegram Mini App webhook
│   ├── templates/                # Jinja2 шаблоны
│   │   ├── base.html
│   │   ├── chart.html            # Основная страница карты
│   │   └── components/           # HTMX компоненты
│   ├── static/
│   │   ├── css/
│   │   ├── js/                   # HTMX, Chart.js
│   │   └── images/
│   └── schemas.py                # Pydantic схемы API
│
├── db/                           # Database
│   ├── models.py                 # SQLAlchemy модели (User, Chart, Consultation, ...)
│   ├── engine.py                 # Async engine + session factory
│   └── repositories/
│       ├── user_repo.py
│       ├── chart_repo.py
│       ├── consultation_repo.py
│       └── subscription_repo.py
│
├── tasks/                        # TaskIQ фоновые задачи
│   ├── main.py                   # TaskIQ worker entry point
│   ├── ai_generation.py          # Долгие AI-генерации
│   └── notifications.py          # Ежедневные прогнозы, алерты
│
├── monitoring/                   # Langfuse + observability
│   ├── langfuse.py               # Langfuse клиент и helpers
│   └── metrics.py                # Кастомные метрики
│
├── migrations/                   # Alembic миграции
│   ├── env.py
│   └── versions/
│
├── tests/                        # Тесты
│   ├── unit/
│   │   ├── test_calculator/
│   │   ├── test_ai/
│   │   └── test_pillars/
│   ├── integration/
│   └── conftest.py
│
├── docs/                         # MkDocs документация
│   ├── algorithms/               # Описание алгоритмов Бацзы
│   └── api/                      # API документация
│
├── .github/
│   └── workflows/
│       └── ci.yml                # GitHub Actions CI/CD
│
├── .env.example                  # Шаблон переменных окружения
├── .pre-commit-config.yaml       # Pre-commit хуки
├── pyproject.toml                # Проектная конфигурация (ruff, mypy, pytest)
├── requirements.txt              # Зависимости
├── Dockerfile                    # Docker-образ
├── docker-compose.yml            # Локальная разработка
├── Procfile                      # Railway deployment
└── README.md                     # Быстрый старт
```

---

## 4. Архитектура проекта

### 4.1. Общая схема компонентов

```
┌─────────────────────────────────────────────────────────────┐
│                        Telegram Clients                      │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                   Telegram Bot Layer (aiogram)               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐ │
│  │ Routers  │  │ Middle-  │  │ FSM      │  │ Keyboards    │ │
│  │          │  │ wares    │  │ States   │  │              │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘ │
└──────────────────────┬──────────────────────────────────────┘
                       │
          ┌────────────┼────────────┐
          ▼            ▼            ▼
┌─────────────┐ ┌─────────────┐ ┌──────────────┐
│ Calculator  │ │  AI Orch.   │ │  Database     │
│  (stateless)│ │  (LiteLLM)  │ │  (PostgreSQL) │
└──────┬──────┘ └──────┬──────┘ └──────┬───────┘
       │               │               │
       ▼               ▼               ▼
┌─────────────┐ ┌─────────────┐ ┌──────────────┐
│ Swiss Eph.  │ │  Langfuse   │ │  Redis       │
│  (pyswiss)  │ │ (monitoring)│ │  (cache/FSM) │
└─────────────┘ └─────────────┘ └──────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              Web Visualization Layer (FastAPI)               │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────────┐ │
│  │ Jinja2   │  │ HTMX     │  │ Chart.js │  │ Mini App     │ │
│  └──────────┘  └──────────┘  └──────────┘  └──────────────┘ │
└─────────────────────────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                  TaskIQ Background Workers                   │
│  ┌──────────────────┐  ┌──────────────────────────────────┐ │
│  │ AI Generation    │  │ Notifications / Daily Forecasts  │ │
│  └──────────────────┘  └──────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### 4.2. Telegram Bot слой

- **Асинхронная обработка** через aiogram 3.x
- **Router-архитектура:** каждый домен — отдельный router (start, consultation, chart, profile, history, subscription, admin, support)
- **Magic Filters** для фильтрации сообщений и callback queries
- **Middleware chain:** trace_id → user auth → db session → handler
- **Graceful degradation:** при недоступности AI — понятное сообщение пользователю

### 4.3. Bazi Calculator слой

- **Stateless:** не хранит состояние, только вычисляет
- **Вход:** `ChartInput(birth_datetime, latitude, longitude, tz_offset, gender, early_rat: bool)`
- **Выход:** `ChartOutput` — полный JSON с картой:
  - 4 столпа (Небесные Стволы + Земные Ветви)
  - Скрытые стволы (3 школы)
  - 10 Божеств (для всех открытых и скрытых)
  - Взаимодействия (合沖刑害破)
  - Столпы Удачи (с точным возрастом перехода)
  - Символические звёзды
  - Мин Гун, Тай Юань
  - Фазы Ци (процент элементов)
  - Пустота (Kong Wang)

### 4.4. AI Orchestrator слой

- **LiteLLM** — единый интерфейс для Claude, Qwen, Kimi
- **Семантический роутер** — лёгкая модель классифицирует намерение и направляет к нужному агенту:
  - Простой вопрос → Claude Sonnet (быстрый ответ)
  - Глубокий анализ → Claude Sonnet + Qwen + Kimi (верификация)
  - Структурные данные → Qwen (генерация JSON, код)
- **Синтез ответов** — объединение результатов в персонализированный ответ
- **Фолбэк** — при падении провайдера автоматическое переключение на резервную модель

### 4.5. Web Visualization слой

- **FastAPI** рендерит HTML-страницы через Jinja2
- **HTMX** для интерактивности (раскрытие скрытых стволов, переключение школ, фильтры)
- **Chart.js** для radar charts (10 Божеств, баланс элементов)
- **Telegram Mini App** интеграция — веб-страница открывается внутри Telegram
- **Уникальные токены** для защиты ссылок на карты

### 4.6. Database слой

- **PostgreSQL** — основное хранилище
- **SQLAlchemy 2.0 async** — асинхронные запросы
- **Alembic** — миграции схемы
- **Репозитории** — абстракция над БД, тестируемые

### 4.7. Кэширование и очереди

| Компонент             | Назначение                                                            |
| --------------------- | --------------------------------------------------------------------- |
| Redis — FSM           | Состояния aiogram (сбор данных рождения)                              |
| Redis — кэш расчётов  | Кэш результатов калькулятора (одинаковые данные = одинаковая карта)   |
| Redis — кэш AI        | Кэш типовых интерпретаций (повторяющиеся вопросы)                     |
| Redis — feature flags | Включение/отключение функций (ai_enabled, maintenance_mode)           |
| Redis — rate limiting | Лимиты вопросов (3/день для free)                                     |
| TaskIQ                | Фоновые задачи: долгие AI-генерации, ежедневные прогнозы, уведомления |

---

## 5. Модель данных

### 5.1. Сущности

Все первичные ключи — **UUID v4**.

#### User

| Поле          | Тип                    | Описание                   |
| ------------- | ---------------------- | -------------------------- |
| `id`          | UUID                   | Первичный ключ             |
| `telegram_id` | BigInt (unique)        | ID пользователя в Telegram |
| `username`    | String (nullable)      | Username из Telegram       |
| `first_name`  | String                 | Имя из Telegram            |
| `locale`      | String (default: "ru") | Язык                       |
| `created_at`  | DateTime               | Дата регистрации           |
| `updated_at`  | DateTime               | Последнее обновление       |

#### Chart

| Поле                      | Тип                             | Описание                                                                       |
| ------------------------- | ------------------------------- | ------------------------------------------------------------------------------ |
| `id`                      | UUID                            | Первичный ключ                                                                 |
| `user_id`                 | UUID (FK → User)                | Владелец карты                                                                 |
| `name`                    | String                          | Название карты (по умолчанию: "Основная карта")                                |
| `birth_datetime_utc`      | DateTime                        | Время рождения в UTC (после TST коррекции)                                     |
| `birth_datetime_original` | DateTime                        | Время рождения без коррекции                                                   |
| `latitude`                | Float                           | Широта места рождения                                                          |
| `longitude`               | Float                           | Долгота места рождения                                                         |
| `tz_offset`               | Float                           | Часовой пояс (с учётом исторического DST)                                      |
| `early_rat`               | Boolean                         | Early Rat / Late Rat для часа Крысы                                            |
| `hidden_stems_school`     | String (default: "traditional") | Школа скрытых стволов                                                          |
| `chart_data`              | JSONB                           | Полный результат расчёта (4 столпа, 10 Божеств, взаимодействия, звёзды и т.д.) |
| `has_birth_time`          | Boolean                         | Известно ли точное время рождения                                              |
| `created_at`              | DateTime                        | Дата создания                                                                  |

#### Consultation

| Поле                | Тип                         | Описание                                 |
| ------------------- | --------------------------- | ---------------------------------------- |
| `id`                | UUID                        | Первичный ключ                           |
| `user_id`           | UUID (FK → User)            | Пользователь                             |
| `chart_id`          | UUID (FK → Chart, nullable) | Привязка к карте                         |
| `topic`             | String                      | Тема консультации                        |
| `user_message`      | Text                        | Сообщение пользователя                   |
| `ai_response`       | Text                        | Ответ AI                                 |
| `model_used`        | String                      | Использованная модель (claude/qwen/kimi) |
| `prompt_tokens`     | Integer                     | Потрачено входных токенов                |
| `completion_tokens` | Integer                     | Потрачено выходных токенов               |
| `cost_usd`          | Float                       | Стоимость запроса                        |
| `latency_ms`        | Integer                     | Время ответа                             |
| `trace_id`          | String                      | Langfuse trace ID                        |
| `created_at`        | DateTime                    | Дата консультации                        |

#### Subscription

| Поле                    | Тип                      | Описание                            |
| ----------------------- | ------------------------ | ----------------------------------- |
| `id`                    | UUID                     | Первичный ключ                      |
| `user_id`               | UUID (FK → User, unique) | Пользователь                        |
| `plan`                  | String                   | free / monthly / quarterly / yearly |
| `status`                | String                   | active / expired / cancelled        |
| `daily_questions_used`  | Integer                  | Счётчик вопросов за сегодня         |
| `daily_questions_reset` | DateTime                 | Дата сброса счётчика                |
| `started_at`            | DateTime                 | Начало подписки                     |
| `expires_at`            | DateTime                 | Окончание подписки                  |
| `payment_provider`      | String                   | telegram_payments / yookassa        |

#### Event (для ректификации)

| Поле          | Тип               | Описание                               |
| ------------- | ----------------- | -------------------------------------- |
| `id`          | UUID              | Первичный ключ                         |
| `chart_id`    | UUID (FK → Chart) | Привязка к карте                       |
| `event_date`  | Date              | Дата события                           |
| `event_type`  | String            | marriage / accident / promotion / etc. |
| `description` | Text (nullable)   | Описание                               |
| `created_at`  | DateTime          | Дата добавления                        |

### 5.2. Связи между сущностями

```
User (1) ──────< Chart (N)
User (1) ──────< Consultation (N)
User (1) ────── (1) Subscription
Chart (1) ─────< Event (N)
Chart (1) ─────< Consultation (N)
```

### 5.3. Миграции

- **Alembic** для управления схемой
- Каждая миграция — отдельный файл в `migrations/versions/`
- **CI проверка:** миграции тестируются в CI перед деплоем
- **Откат миграций:** всегда должен быть возможен `alembic downgrade`

---

## 6. Работа с LLM

### 6.1. Мульти-модельная архитектура

```
Запрос пользователя
       │
       ▼
┌─────────────────────┐
│  Semantic Router     │  ← LiteLLM (лёгкая модель / правило)
│  (классификация)     │
└──────────┬──────────┘
           │
    ┌──────┼──────┐
    ▼      ▼      ▼
  Простой  Обычный  Сложный
    │       │       │
    ▼       ▼       ▼
 Claude   Claude   Claude +
 Sonnet   Sonnet   Qwen + Kimi
                    │
                    ▼
              ┌───────────┐
              │ Synthesis │
              └─────┬─────┘
                    ▼
              Финальный ответ
```

### 6.2. Промпт-инженерия

**Системный промпт Анастасии** (`ai/prompts/anastasia_system.md`, 68 КБ):

- Профиль личности (имя, возраст, опыт, школа)
- Стиль коммуникации (тон, длина, эмодзи, запрет "!")
- Структура ответа (прямой ответ → объяснение → рекомендация)
- Этические ограничения (не диагностирует, не предсказывает смерть)
- Полная методология Цзы Пин: 10 Божеств, взаимодействия, Шэнь Ша

**Формат входных данных для LLM:**
Карта передаётся в структурированном JSON/Markdown, не сырые данные:

```markdown
## Карта Бацзы

**Дневной Мастер:** 甲 (Дерево Ян)
**Структура:** 七杀格 (Семь Убийств)
**Полезное божество:** 癸 (Вода Инь)

| Столп | Небесный Ствол | Земная Ветвь  | 10 Божеств  |
| ----- | -------------- | ------------- | ----------- |
| Год   | 丙 (Огонь Ян)  | 辰 (Дракон)   | 食神 / 偏财 |
| Месяц | 戊 (Земля Ян)  | 午 (Лошадь)   | 偏财 / 伤官 |
| День  | 甲 (Дерево Ян) | 子 (Крыса)    | 日主 / 正印 |
| Час   | 壬 (Вода Ян)   | 申 (Обезьяна) | 偏印 / 七杀 |

**Взаимодействия:** 子辰合 (Крыса-Дракон → Вода)
**Пустота:** 戌, 亥
**Символические звёзды:** 文昌 (Змея), 桃花 (Кролик)
```

### 6.3. AI-маршрутизатор

**Семантический роутер** определяет сложность запроса:

| Класс запроса | Модель               | Примеры                                                                      |
| ------------- | -------------------- | ---------------------------------------------------------------------------- |
| Простой       | Claude Sonnet        | "Какой мой Дневной Мастер?", "Покажи карту"                                  |
| Обычный       | Claude Sonnet        | "Подходит ли мне IT-сфера?", "Расскажи про характер"                         |
| Сложный       | Claude + Qwen + Kimi | "Проанализируй совместимость с партнёром", "Прогноз на год с рекомендациями" |

### 6.4. Синтез ответов

Для сложных запросов с верификацией:

1. **Claude Sonnet** генерирует основной ответ на русском
2. **Qwen 3.6** анализирует структуру карты, даёт альтернативный взгляд
3. **Kimi** проверяет тонкости классической школы, корректность работы с иероглифами
4. **Synthesis module** объединяет: берёт основной ответ Claude, обогащает инсайтами из Qwen/Kimi, форматирует в стиле Анастасии

### 6.5. Фолбэк-механизм

```
Claude Sonnet доступен? → Да → используем Claude
                          ↓ Нет
Qwen 3.6 доступен?     → Да → используем Qwen
                          ↓ Нет
Kimi доступен?         → Да → используем Kimi
                          ↓ Нет
→ Ответ пользователю: "Извините, звёзды сейчас скрыты за облаками, повторите запрос через минуту"
```

### 6.6. Управление контекстом

- **В рамках сессии:** история сообщений хранится в Redis (TTL 24 часа)
- **Долгосрочная память:** summary прошлых консультаций в JSONB поле `Consultation`
- **Контекст карты:** при повторных визитах бот подгружает карту из БД и передаёт в промпт
- **Максимальная длина контекста:** 128K токенов (Claude Sonnet limit)

### 6.7. Rate limiting и контроль расходов

| Механизм           | Реализация                                                    |
| ------------------ | ------------------------------------------------------------- |
| Daily limit (Free) | Redis counter, сброс в 00:00 UTC, 3 вопроса/день              |
| Token budget       | Макс 4096 output tokens на ответ (контроль cost)              |
| Timeout            | 30 секунд на ответ от LLM (TaskIQ для долгих запросов)        |
| Cost tracking      | Каждый запрос логируется в Langfuse + Consultation (cost_usd) |
| Cache              | Повторяющиеся вопросы → кэш Redis (TTL 7 дней)                |

---

## 7. Мониторинг LLM

### 7.1. Langfuse — основная платформа

| Функция             | Описание                                                             |
| ------------------- | -------------------------------------------------------------------- |
| Логирование вызовов | Каждый запрос к LLM записывается с input/output, моделью, токенами   |
| Cost tracking       | Автоматический расчёт стоимости по моделям                           |
| Latency tracking    | Время от запроса до ответа                                           |
| Traces              | Полный trace каждого запроса (router → model → synthesis → response) |
| Sessions            | Группировка по пользовательским сессиям                              |

### 7.2. Метрики

| Метрика                    | Источник          | Порог алерта    |
| -------------------------- | ----------------- | --------------- |
| `llm_latency_ms`           | Langfuse          | > 20 000 ms     |
| `llm_error_rate`           | Langfuse          | > 5% за 1 час   |
| `llm_cost_per_user`        | БД (Consultation) | > 0.05 USD/день |
| `llm_tokens_total`         | Langfuse          | —               |
| `ai_generation_time`       | TaskIQ            | > 30 секунд     |
| `fallback_activation_rate` | БД                | > 10% за 1 час  |

### 7.3. Логирование запросов/ответов

- **Каждый AI-запрос** записывается в таблицу `Consultation`
- **Langfuse trace** — полный лог с input/output, используемой моделью, токенами
- **trace_id** — уникальный ID, проходящий через все слои (bot → calculator → ai → response)

### 7.4. Алерты

Оповещения в приватный Telegram-канал админа:

- Превышение таймаута LLM (> 20 секунд)
- Ошибки 5xx от провайдеров (Anthropic, DashScope, Moonshot)
- Превышение дневного бюджета на AI (> $5/день)
- Активация фолбэка > 10% за час

### 7.5. Дашборды

- **Langfuse UI** — основной дашборд: cost, latency, model usage, error rate
- **Telegram админ-панель** — базовая статистика: пользователи, консультации, конверсия

---

## 8. Сценарии работы

### 8.1. Первое взаимодействие (/start → расчёт → консультация)

```
1. Пользователь → /start
2. Бот → FSM: запрашивает дату рождения
3. Пользователь → дата
4. Бот → FSM: запрашивает время рождения
5. Пользователь → время (или "не знаю")
6. Бот → FSM: запрашивает город рождения
7. Пользователь → город → geopy → координаты → timezonefinder → tz_offset
8. Бот → FSM: запрашивает пол
9. Пользователь → пол
10. Бот → Calculator: расчёт карты (TST → 4 столпа → всё остальное)
11. Бот → Сохраняет карту в БД (Chart)
12. Бот → Генерирует ссылку на HTML-визуализацию (FastAPI)
13. Бот → Анастасия: "[Карта текстом] + [Ссылка на визуализацию]. Что волнует?"
14. Пользователь → выбирает тему или свободный вопрос
15. Бот → AI Orchestrator: классификация → модель → генерация ответа
16. Бот → Анастасия: ответ (с trace_id в Langfuse)
17. Цикл 14-16 повторяется (диалог)
18. Пользователь → завершение или бот предлагает резюме
```

### 8.2. Повторный визит

```
1. Пользователь → /start или любое сообщение
2. Бот → user_middleware: узнаёт пользователя (telegram_id)
3. Бот → Подгружает карту из БД
4. Бот → Главное меню: [Консультация] [Моя карта] [Визуализация] [История] [Профиль] [Подписка]
5. Пользователь → выбирает действие
```

### 8.3. Просмотр карты

```
1. Пользователь → [Моя карта]
2. Бот → Текстовое отображение 4 столпов + 10 Божеств
3. Бот → Ссылка на HTML-визуализацию (уникальный токен)
4. Пользователь → Открывает страницу → интерактивная карта с Chart.js
```

### 8.4. История консультаций

```
1. Пользователь → [История]
2. Бот → Загружает последние 10 консультаций из БД
3. Бот → Список: дата, тема, краткое резюме
4. Пользователь → Может открыть конкретную консультацию
```

### 8.5. Управление подпиской

```
1. Пользователь → [Подписка]
2. Бот → Текущий тариф, остаток вопросов, дата окончания
3. Пользователь → [Оплатить] → Telegram Payments / ЮKassa
4. Бот → Обновляет Subscription в БД
```

### 8.6. Нет времени рождения (Graceful degradation)

```
1. Пользователь → "Не знаю время"
2. Бот → Устанавливает время 12:00 (полдень)
3. Бот → has_birth_time = False
4. Calculator → Строит 3 точных столпа (год, месяц, день), часовой — приблизительный
5. Бот → Анастасия предупреждает: "Без точного времени часовой столп приблизителен.
           Анализ Дворца Детей, инвестиций и старости ограничен."
6. AI Orchestrator → Отключает анализ Столпа Часа в промпте
```

### 8.7. Edge cases

| Ситуация                          | Обработка                                                                 |
| --------------------------------- | ------------------------------------------------------------------------- |
| LLM недоступен                    | Фолбэк на резервную модель (Claude → Qwen → Kimi)                         |
| LLM timeout (>30 сек)             | TaskIQ: задача в фон, бот: "Звёзды считают, жду пару минут..."            |
| Ошибка геокодирования             | Бот: "Не нашёл город. Попробуйте другой вариант или введите координаты"   |
| Ошибка pyswisseph                 | Retry 3 раза, потом: "Технические сложности с расчётом, попробуйте позже" |
| Пользователь спамит               | Rate limiter Redis: "3 вопроса в день бесплатно. Хотите Pro?"             |
| Пользователь отправляет голосовое | Бот: "Пока не распознаю голос. Напишите текстом)"                         |
| Пользователь на "ты"              | Бот запоминает в user.settings, Анастасия переходит на "ты"               |

---

## 9. Деплой

### 9.1. Инфраструктура (Railway)

| Сервис        | Railway resource | Описание                             |
| ------------- | ---------------- | ------------------------------------ |
| Telegram Bot  | Service 1        | aiogram бот (Python)                 |
| Web API       | Service 2        | FastAPI + Uvicorn                    |
| PostgreSQL    | Database         | PostgreSQL managed (Railway)         |
| Redis         | Database         | Redis managed (Railway)              |
| TaskIQ Worker | Service 3        | Фоновые задачи                       |
| Langfuse      | Service 4        | Self-hosted мониторинг (опционально) |

### 9.2. Docker-контейнеризация

**Критически важно для pyswisseph** — требует компиляции C-кода и файлов эфемерид.

```dockerfile
# Dockerfile
FROM python:3.11-slim

# Swiss Ephemeris C-библиотека
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Swiss Ephemeris data
COPY swisseph /usr/share/swisseph

COPY . .

# Бот
CMD ["python", "-m", "bot.main"]
```

```yaml
# docker-compose.yml (локальная разработка)
version: "3.9"
services:
  bot:
    build: .
    command: python -m bot.main
    env_file: .env
    depends_on: [db, redis]

  web:
    build: .
    command: uvicorn web.main:app --reload --host 0.0.0.0
    ports: ["8000:8000"]
    env_file: .env
    depends_on: [db, redis]

  worker:
    build: .
    command: taskiq worker start
    env_file: .env
    depends_on: [db, redis]

  db:
    image: postgres:16
    environment:
      POSTGRES_DB: badzi
      POSTGRES_USER: badzi
      POSTGRES_PASSWORD: badzi
    volumes: [pgdata:/var/lib/postgresql/data]

  redis:
    image: redis:7

volumes:
  pgdata:
```

### 9.3. CI/CD пайплайн (GitHub Actions)

```yaml
# .github/workflows/ci.yml
name: CI/CD

on:
  push:
    branches: [main]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.11" }
      - run: pip install -r requirements.txt
      - run: ruff check .
      - run: ruff format --check .
      - run: mypy .
      - run: pytest --cov=calculator --cov=ai --cov-report=xml

  deploy:
    needs: test
    if: github.ref == 'refs/heads/main'
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: railwayapp/cli-action@v2
        with:
          railwayToken: ${{ secrets.RAILWAY_TOKEN }}
      - run: railway up
```

### 9.4. Environment'ы

| Environment  | Описание                                     |
| ------------ | -------------------------------------------- |
| `dev`        | Локально, docker-compose, SQLite, debug mode |
| `staging`    | Railway, отдельная БД, тестовые API ключи    |
| `production` | Railway, production БД, production API ключи |

### 9.5. Масштабирование

| Компонент     | Стратегия                                               |
| ------------- | ------------------------------------------------------- |
| Bot           | Stateless, Railway автоматически масштабирует           |
| Web API       | Stateless, Railway автоматически масштабирует           |
| PostgreSQL    | Railway managed, vertical scaling (увеличение ресурсов) |
| Redis         | Railway managed, horizontal при необходимости           |
| TaskIQ Worker | Отдельный сервис, можно масштабировать independently    |

---

## 10. Конфигурирование

### 10.1. Pydantic Settings

```python
# bot/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # Telegram
    bot_token: str
    admin_telegram_id: int

    # Database
    database_url: str  # PostgreSQL DSN
    redis_url: str     # Redis DSN

    # AI (LiteLLM)
    anthropic_api_key: str
    dashscope_api_key: str
    moonshot_api_key: str
    llm_timeout: int = 30        # секунды
    max_output_tokens: int = 4096

    # Calculator
    swiss_ephemeris_path: str = "/usr/share/swisseph"
    geocoding_provider: str = "nominatim"  # nominatim | google

    # Web
    web_base_url: str = "https://badzi-bot.railway.app"
    chart_link_ttl: int = 86400  # 24 часа

    # Rate limiting
    free_daily_limit: int = 3

    # Feature flags
    ai_enabled: bool = True
    visualization_enabled: bool = True
    payments_enabled: bool = True

    # Logging
    log_level: str = "INFO"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

settings = Settings()
```

### 10.2. .env.example

```env
# Telegram
BOT_TOKEN=
ADMIN_TELEGRAM_ID=

# Database
DATABASE_URL=postgresql+asyncpg://user:pass@host:5432/badzi
REDIS_URL=redis://host:6379/0

# AI Providers
ANTHROPIC_API_KEY=
DASHSCOPE_API_KEY=
MOONSHOT_API_KEY=

# Web
WEB_BASE_URL=https://badzi-bot.railway.app

# Feature Flags
AI_ENABLED=true
VISUALIZATION_ENABLED=true
PAYMENTS_ENABLED=true

# Logging
LOG_LEVEL=INFO
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
```

### 10.3. Секреты

- **API keys** — только через Railway Secrets или GitHub Secrets (для CI)
- **Никогда** не коммитить `.env` в репозиторий
- `.env` в `.gitignore`
- Pre-commit hook: проверка на наличие паттернов `sk-`, `anthropic`, `dashscope` в коммите

### 10.4. Feature flags

Реализованы через Redis для динамического включения/отключения без перезапуска:

```python
# Через Redis
async def is_feature_enabled(feature: str) -> bool:
    flag = await redis.get(f"flag:{feature}")
    if flag is not None:
        return flag == "true"
    return settings.model_dump()[feature]  # fallback из Settings
```

---

## 11. Логгирование

### 11.1. Библиотека: structlog

- **Структурированные JSON-логи** — легко парсить, индексировать, искать
- **Контекст** — автоматическое добавление `user_id`, `trace_id`, `chart_id`
- **Интеграция** — работает с standard logging, stdlib logging

### 11.2. Формат и структура логов

```json
{
  "timestamp": "2026-04-14T12:34:56.789Z",
  "level": "info",
  "event": "consultation_completed",
  "trace_id": "abc-123-def",
  "user_id": "user-uuid",
  "telegram_id": 123456789,
  "chart_id": "chart-uuid",
  "topic": "career",
  "model_used": "claude-sonnet-3.5",
  "prompt_tokens": 2048,
  "completion_tokens": 512,
  "cost_usd": 0.012,
  "latency_ms": 4520,
  "langfuse_trace_id": "langfuse-trace-uuid"
}
```

### 11.3. Корреляция запросов (trace_id)

- **Middleware в aiogram** генерирует `trace_id` (UUID v4) для каждого апдейта
- **Trace_id прокидывается** через все слои: bot → calculator → ai → db → response
- **Langfuse** использует тот же trace_id для связывания
- **Логи всех сервисов** содержат trace_id → полная трассировка одного запроса

```python
# bot/middlewares/tracing.py
from aiogram import BaseMiddleware
import uuid
from structlog.contextvars import clear_contextvars, bind_contextvars

class TracingMiddleware(BaseMiddleware):
    async def __call__(self, handler, event, data):
        clear_contextvars()
        trace_id = str(uuid.uuid4())
        bind_contextvars(trace_id=trace_id)
        data["trace_id"] = trace_id
        return await handler(event, data)
```

### 11.4. Централизованный сбор логов

| Environment | Сбор логов                                    |
| ----------- | --------------------------------------------- |
| Dev         | stdout (docker-compose logs)                  |
| Staging     | Railway logs (built-in)                       |
| Production  | Railway logs + Langfuse для AI-specific логов |

### 11.5. Sensitivity (PII, GDPR)

- **Маскирование PII:** в логи не попадают реальные имена, telegram usernames, точные координаты
- **Округление координат:** до уровня города (2 знака после запятой)
- **Telegram ID:** хешируется (SHA-256 truncated) в публичных логах
- **Банковские данные:** не логируются (обрабатываются через Telegram Payments / ЮKassa)

```python
# sanitize helper
def sanitize_coords(lat: float, lon: float) -> tuple:
    return (round(lat, 2), round(lon, 2))  # ~1km precision

def sanitize_telegram_id(tid: int) -> str:
    import hashlib
    return hashlib.sha256(str(tid).encode()).hexdigest()[:12]
```

---

## 12. Дорожная карта

### Этап 1 — MVP (март-апрель 2026)

```
☐ Структура проекта (бот, калькулятор, AI, web, db)
☐ Модели БД (User, Chart, Consultation, Subscription)
☐ Alembic миграции
☐ FSM: сбор данных рождения (дата → время → город → пол)
☐ pyswisseph интеграция
☐ Хронобиологический модуль (TST, LMT, EoT, DST, TZ Database)
☐ Геокодирование (город → координаты → таймзона)
☐ Калькулятор: 4 столпа, скрытые стволы, Дневной Мастер
☐ 60-ричный цикл (Цзя Цзы) для каждого столпа
☐ Дилемма Часа Крысы (Early/Late Rat переключатель)
☐ Определение силы ДМ, полезное/вредное божество
☐ Маппинг 10 Божеств для всех элементов
☐ Базовые взаимодействия (слияния, столкновения)
☐ LiteLLM интеграция (Claude Sonnet)
☐ Системный промпт Анастасии
☐ Хендлер консультации (выбор темы → диалог → завершение)
☐ Отображение карты в текстовом формате
☐ Лимиты (3 вопроса/день бесплатно)
☐ Подписка Pro через Telegram Payments
☐ structlog + trace_id middleware
☐ Админ-панель со статистикой
☐ Docker + docker-compose
☐ GitHub Actions CI/CD
☐ Деплой на Railway
```

### Этап 2 — Расширение (май-июнь 2026)

```
☐ 24 сезона Цзе Ци — вычисление моментов наступления с точностью до минуты
☐ Столпы Удачи (Да Юнь) — расчёт возраста перехода до минуты (3 дня = 1 год)
☐ Все взаимодействия (слияния, столкновения, наказания, вред, разрушения)
☐ 3 школы Скрытых Стволов (Traditional, Modern, Ken Lai)
☐ Символические звёзды (50-90 Шэнь Ша)
☐ Дворец Жизни (Мин Гун) и Столп Зачатия (Тай Юань)
☐ Фазы Ци — процентное соотношение элементов и 10 Божеств
☐ Темы: Здоровье, Таланты
☐ Совместимость пар (две карты)
☐ Редактирование данных рождения
☐ История консультаций (просмотр прошлых сессий)
☐ Qwen 3.6 + Kimi интеграция через LiteLLM
☐ AI-маршрутизатор (семантический роутинг)
☐ Синтез ответов (Claude + Qwen + Kimi)
☐ Фолбэк-механизм
☐ Langfuse мониторинг
☐ TaskIQ фоновые задачи
```

### Этап 3 — Визуализация (Q3 2026)

```
☐ FastAPI сервер для HTML-страниц
☐ Jinja2 шаблоны + HTMX интерактивность
☐ Chart.js radar charts (10 Божеств, баланс элементов)
☐ Цветовое кодирование элементов
☐ Интерактивные подсказки по клику
☐ Отправка ссылки на карту в Telegram
☐ Защита ссылок (уникальные токены, TTL)
☐ Telegram Mini App интеграция
☐ Встроенный мини-чат с Анастасией на странице
```

### Этап 4 — Рост (Q4 2026)

```
☐ Ежедневный прогноз (автоматическая рассылка через TaskIQ)
☐ Реферальная программа
☐ Мультиязычность (EN, UA, KZ)
☐ Кэширование типовых интерпретаций (Redis)
☐ A/B тесты лимитов и ценообразования
☐ Оптимизация AI-расходов (маршрутизатор + кэш)
☐ Векторная база для долгосрочной памяти (pgvector)
☐ Ректификация часа рождения (Event + AI анализ)
```
