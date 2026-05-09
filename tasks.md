![1778154346381](image/tasks/1778154346381.png)![1778154360599](image/tasks/1778154360599.png)# БаЦзы-Бот — Бэклог задач
![1778157066075](image/tasks/1778157066075.png)
> Статус: 🚀 Live на YC VM 130.193.51.15 как @EdoHa_Badzi_bot (2026-05-08)
> Методология: AIDD → Plan → Agree → Implement → Verify → Commit

---

## ✅ Выполнено

### Подготовительные задачи
- [x] **P-1** 24 PNG-ассета иероглифов (10 стволов + 12 ветвей + 2 Инь/Ян) в стиле Mingli
- [x] **P-3** YC-аккаунт + `yc` CLI; ресурсы созданы (PostgreSQL, Redis, VPS, Object Storage)
- [x] **P-4** Gemini Deep Research по 6 архитектурным вопросам ([doc/gemini_research.md](doc/gemini_research.md))
- [x] **P-5** Скаффолд директорий (`tests/`, `knowledge/`, `monitoring/`, `web/`, `tasks/`)

### Этап 1 MVP — закрытое

#### 1.1 Инфраструктура проекта
- [x] 1.1.1 `pyproject.toml` (ruff, mypy, pytest, pytest-asyncio)
- [x] 1.1.2 `.pre-commit-config.yaml` (ruff + mypy + secret scan)
- [x] 1.1.3 Dockerfile (python:3.11-slim + gcc для pyswisseph)
- [x] 1.1.4 docker-compose.yml (bot + worker + postgres + redis)
- [x] 1.1.5 GitHub Actions CI/CD ([.github/workflows/ci.yml](.github/workflows/ci.yml))

#### 1.2 Конфигурация и логирование
- [x] 1.2.1 [bot/config.py](bot/config.py) — Pydantic Settings (все env vars из `.env.example`)
- [x] 1.2.2 structlog (JSON-формат, trace_id биндинг)
- [x] 1.2.3 [bot/middlewares/tracing.py](bot/middlewares/tracing.py) — trace_id middleware

#### 1.3 База данных
- [x] 1.3.1 [db/engine.py](db/engine.py) — async PostgreSQL engine + session factory
- [x] 1.3.2 [db/models.py](db/models.py) — SQLAlchemy модели (User, Chart, Consultation, Subscription, Event)
- [x] 1.3.3 Alembic init (`migrations/env.py`, `alembic.ini`)
- [x] 1.3.4 Первая миграция: `create_initial_tables` (revision `151398db4f39`)
- [x] 1.3.5 [db/repositories/](db/repositories/) — UserRepo, ChartRepo, ConsultationRepo, SubscriptionRepo

#### 1.4 Калькулятор Бацзы (stateless ядро)
- [x] 1.4.1 [calculator/models.py](calculator/models.py) — ChartInput, ChartOutput (Pydantic)
- [x] 1.4.2 [calculator/swiss.py](calculator/swiss.py) — pyswisseph + JPL DE431
- [x] 1.4.3 [calculator/true_solar_time.py](calculator/true_solar_time.py) — TST: LMT + EoT + DST + longitude
- [x] 1.4.4 [calculator/solar_terms.py](calculator/solar_terms.py) — 24 Цзе Ци
- [x] 1.4.5 [calculator/pillars.py](calculator/pillars.py) — 4 столпа (年月日時), 60-цикл
- [x] 1.4.6 [calculator/hidden_stems.py](calculator/hidden_stems.py) — 3 школы (Traditional, Modern, Ken Lai)
- [x] 1.4.7 [calculator/ten_gods.py](calculator/ten_gods.py) — 10 Божеств
- [x] 1.4.8 [calculator/day_master.py](calculator/day_master.py) — Сила ДМ
- [x] 1.4.9 Тесты калькулятора — покрытие 80%+

#### 1.5 Telegram Bot — базовая структура
- [x] 1.5.1 [bot/main.py](bot/main.py) — entry point, диспетчер, middleware, роутеры
- [x] 1.5.2 [bot/middlewares/db_session.py](bot/middlewares/db_session.py)
- [x] 1.5.3 [bot/middlewares/user_middleware.py](bot/middlewares/user_middleware.py) — get_or_create
- [x] 1.5.4 [bot/states.py](bot/states.py) — FSM (BirthDataForm, ConsultationState)
- [x] 1.5.5 [bot/keyboards/](bot/keyboards/) — inline клавиатуры

#### 1.6 FSM — Сбор данных рождения
- [x] 1.6.1 [bot/routers/start.py](bot/routers/start.py) — /start, приветствие Анастасии (Variant B)
- [x] 1.6.2 FSM шаг 1: дата рождения (валидация формата)
- [x] 1.6.3 FSM шаг 2: время рождения (с вариантом «не знаю»)
- [x] 1.6.4 FSM шаг 3: город → geopy → координаты → timezonefinder (top-3 inline)
- [x] 1.6.5 FSM шаг 4: пол + сводка
- [x] 1.6.6 Подтверждение → `calculate_chart` → Chart в БД

#### 1.7 Визуальная карта (CairoSVG + Pillow + ProcessPool)
- [x] 1.7.1–1.7.2 v1 Playwright (legacy, deprecated)
- [x] 1.7.4 Отправка фото в Telegram (BufferedInputFile)
- [x] 1.7.6 [ai/svg_renderer.py](ai/svg_renderer.py) — Jinja2 → SVG → CairoSVG → PNG pipeline
- [x] 1.7.7 [web/templates/chart.svg.j2](web/templates/chart.svg.j2) — light Mingli grid + цвета стихий
- [x] 1.7.8 У-син пентагон с подсветкой ДМ (radius 130, безье-стрелки порождения/контроля)
- [x] 1.7.9 [ai/_render_pool.py](ai/_render_pool.py) — `ProcessPoolExecutor` (`RENDER_POOL_SIZE` или `cpu_count()//2`)
- [x] 1.7.10 Playwright удалён из deps + Dockerfile (-150 MB образа)
- [x] 1.7.11 [doc/benchmarks/render.md](doc/benchmarks/render.md) — bench: pool=4 даёт 2× rps на N=200

#### 1.8 AI Оркестратор (OpenRouter) — закрыт 2026-05-07
- [x] 1.8.1 [ai/orchestrator.py](ai/orchestrator.py) — OpenRouter клиент (httpx async, иерархия исключений). 15 unit-тестов.
- [x] 1.8.2 [ai/prompts/anastasia_system.md](ai/prompts/anastasia_system.md) — 39 KB, `load_system_prompt()` с `lru_cache`. 4 теста.
- [x] 1.8.3 [ai/router.py](ai/router.py) — semantic router (simple/normal/complex, cyrillic-aware). 17 тестов.
- [x] 1.8.4 [ai/context.py](ai/context.py) — `HistoryStore` поверх Redis, TTL 24h, max 20 msgs. 8 тестов.
- [x] 1.8.5 [ai/fallback.py](ai/fallback.py) — `chat_with_fallback`: primary → fallback на 429/5xx. 6 тестов.
- [x] 1.8.6 [ai/temporal_context.py](ai/temporal_context.py) — `compose_messages()` с system + history + chart + temporal. 9 тестов.

#### 1.10 Базовая интерпретация (6 блоков, всегда бесплатно) — закрыт 2026-05-07
- [x] 1.10.1 [ai/base_interpretation.py](ai/base_interpretation.py) — генератор 6 блоков одним вызовом, `parse_blocks` regex, `format_for_telegram` HTML-форматирование. 11 тестов.
- [x] 1.10.2–1.10.7 Шесть блоков: «Баланс пяти стихий», «Господин Дня — личность», «Реализация по кругу порождения», «Идеальный партнёр», «Сильные стороны карты», «Влияние текущего года».
- [x] 1.10.8 `format_for_telegram` + `_strip_exclaim` (защита от `!`).

#### 1.11 TaskIQ инфраструктура — закрыт 2026-05-07
- [x] 1.11.1 [tasks/broker.py](tasks/broker.py) — `ListQueueBroker` поверх Redis, TTL результатов 1ч.
- [x] 1.11.2 [tasks/consultation.py](tasks/consultation.py) — `run_consultation()` для будущих тяжёлых запросов (>30s).
- [x] 1.11.3 [docker-compose.yml](docker-compose.yml) `worker` сервис.

#### 1.13 Консультация — диалог с Анастасией — закрыт 2026-05-07, доработан 2026-05-08
- [x] 1.13.1 [bot/routers/consultation.py](bot/routers/consultation.py) — `handle_ask_pressed`, `handle_question`, `handle_reset`.
- [x] 1.13.2 Контекст через `compose_messages()` (system + history + chart + temporal? + question).
- [x] 1.13.3 Детектор временных вопросов через `route()`.
- [x] 1.13.4 Typing-индикатор `_keep_typing()` каждые 4 сек.
- [x] 1.13.5 Сохранение в `Consultation` со всеми полями телеметрии.
- [x] 1.13.X **Bonus:** [bot/middlewares/history.py](bot/middlewares/history.py) — `HistoryMiddleware`. 7 тестов.
- [x] **1.13.6 (2026-05-08)** UI: `chart_actions_kb` («Получить разбор карты», «Задать вопрос по карте», «В меню») на фото карты. `handle_ask_pressed` использует `message.answer` вместо `edit_text`. `chart_id` пиннится в FSM при `chart:open`.
- [x] **1.13.7 (2026-05-08)** Навигация: `menu:back`, `menu:pricing`, `pay:*` хендлеры (тарифы пока заглушка).
- [x] **1.13.8 (2026-05-08)** Свитч на Claude 3.5 Sonnet (latency 55s → ~5-10s) + strict-cite в `_INSTRUCTION` против context-leakage.

#### 1.16 Деплой MVP — частично (3 из 6 пунктов)
- [x] 1.16.1 YC ресурсы созданы (VPS, PostgreSQL, Redis, Object Storage) — 2026-05-02
- [x] 1.16.3 Миграции Alembic накатаны на managed PG (revision `151398db4f39 (head)`, подтверждено SSH-аудитом 2026-05-08)
- [x] **1.16.6 (2026-05-08)** Live-bot на YC VM: контейнеры `badzi_bot-bot-1` + `badzi_bot-worker-1` healthy, доступен в Telegram как `@EdoHa_Badzi_bot`

### Этап 2 — закрытое

#### 2.1 Калькулятор — расширение
- [x] 2.1.1 [calculator/luck_pillars.py](calculator/luck_pillars.py) — Столпы Удачи (大運) до минуты + `start_datetime`
- [x] 2.1.2 [calculator/interactions.py](calculator/interactions.py) — 9 типов взаимодействий 合沖刑害破
- [x] 2.1.3 [calculator/symbolic_stars.py](calculator/symbolic_stars.py) — 60 классических Шэнь Ша в 7 категориях
- [x] 2.1.4 [calculator/auxiliary.py](calculator/auxiliary.py) — 胎元 (Тай Юань) + 命宫 (Мин Гун)
- [x] 2.1.5 [calculator/structures.py](calculator/structures.py) — 25 格局 каскадный priority 化→从→一气→月令-special→正格

#### 2.1.6 Воспроизводимость калькулятора — закрыт 2026-05-07
**Итог:** калькулятор детерминирован (1000/1000 одинаковых результатов в одном процессе и между процессами). «Плавание» в MASTER.md полностью объяснено парой `(tz_offset, early_rat)` — DST-aware tz_offset для 1999 = 4.0, не 3.0. Регрессионные тесты: [tests/unit/test_calculator/test_determinism.py](tests/unit/test_calculator/test_determinism.py) и [tests/unit/test_bot/test_birth_datetime.py](tests/unit/test_bot/test_birth_datetime.py). Отдельный вопрос точности (наш `丁卯` vs классический эталон `丁亥`) — задача 2.1.7.

---

## 🔴 Текущая итерация (live-fix wave + минимальная защита перед релизом)

### 🟡 L. После live-теста на проде
- [ ] **L-1 Эмодзи в SVG-карте.** На проде эмодзи 🌳🔥⛰⚙💧 не рендерятся (видны белые SVG-плейсхолдеры). Twemoji не подходит (тусклый). Нужен другой 3D-emoji-шрифт. План: рекомендация Gemini по open-source 3D-эмодзи (Microsoft Fluent Emoji 3D / JoyPixels / Apple Color Emoji extracted) → установка в Dockerfile через `apt`/`curl` + fontconfig alias → проверка через `BAZI_DEBUG_DUMP_SVG=1` → деплой.
- [ ] **L-2 Live-валидация Claude Sonnet.** После коммита `ff21ef2` проверить в Telegram: latency ~10с (вместо 55), баланс стихий цитируется дословно (15% Огня, не 40%), стиль Анастасии сохранился (тёплый, без `!`).

### 🟢 1.12.0 Минимальный free-question guard (защита от безлимитного жжения токенов)
- [ ] **1.12.0 (новое)** `User.free_question_used` флаг + проверка в `handle_question`: первый вопрос → флаг `True`, второй → заглушка «оплата подключается» через `pricing_kb`. Нужно ДО широкого релиза, иначе любой пользователь жжёт OpenRouter-токены.

---

## 🟢 До закрытия MVP

### 1.7 Визуальная карта (отложенное в 1.16)
- [ ] 1.7.3 Загрузка PNG в Yandex Object Storage (aioboto3 + хеш-кэш)
- [ ] 1.7.5 Fallback: Pillow-композиция из 24 PNG-ассетов если CairoSVG недоступен

### 1.9 Knowledge graph RAG (фрактальный) — отдельная итерация
> Богдан хочет **fractal RAG-Graph** методику, не классический Kuzu schema. Требует отдельного исследования и плана.
- [ ] 1.9.1 Исследовать fractal RAG-Graph (статьи + примеры внедрений)
- [ ] 1.9.2 Спроектировать схему графа Бацзы (Element/Stem/Branch/Rule + fractal levels)
- [ ] 1.9.3 Оцифровка [База/ba_zi_prompt_anastasia_v2.md](База/ba_zi_prompt_anastasia_v2.md) → граф
- [ ] 1.9.4 RAG-поиск по концептам вопроса
- [ ] 1.9.5 Интеграция в `compose_messages` (заменит часть system_prompt)

### 1.12 Монетизация — полная реализация
- [ ] 1.12.1 Redis rate limiter (счётчик вопросов/день для free)
- [ ] 1.12.2 [bot/routers/subscription.py](bot/routers/subscription.py) — экран тарифов (290₽ / 990₽ / 2490₽)
- [ ] 1.12.3 ЮKassa интеграция — создание платежа, redirect URL
- [ ] 1.12.4 ЮKassa webhook handler (FastAPI endpoint)
- [ ] 1.12.5 1 бесплатный вопрос для новых пользователей (поверх 1.12.0)
- [ ] 1.12.6 После оплаты: обновление Subscription в БД

### 1.14 Мониторинг (Langfuse)
- [ ] 1.14.1 [monitoring/langfuse.py](monitoring/langfuse.py) — клиент и helpers
- [ ] 1.14.2 Логирование каждого AI-запроса (trace_id, cost_usd, latency)
- [ ] 1.14.3 Алерты в приватный Telegram-канал (timeout, 5xx, budget)

### 1.15 Админ-панель
- [ ] 1.15.1 [bot/routers/admin.py](bot/routers/admin.py) — `/admin stats`, `/admin export`, `/admin model`
- [ ] 1.15.2 `/admin stats` — DAU, вопросы/день, выручка, конверсия
- [ ] 1.15.3 `/admin export` — CSV диалогов в YC Object Storage → ссылка
- [ ] 1.15.4 `/admin model` — смена модели LLM без деплоя (Redis feature flag)
- [ ] 1.15.5 FastAPI admin page (Basic Auth) — дашборд

### 1.16 Деплой MVP — оставшийся хвост
- [ ] **1.16.2** YC Container Registry — *отложено*. Текущий пайплайн `rsync → docker compose build на VM` работает, переход на YCR + GitHub Actions откладывается до отдельной итерации.
- [ ] **1.16.4** Telegram webhook вместо polling. Сейчас `Start polling for bot @EdoHa_Badzi_bot`. Нужно: FastAPI endpoint `/webhook/<token>` + `setWebhook` через Bot API + SSL через YC Certificate Manager. Polling работает, но webhook нужен для масштаба.
- [ ] **1.16.5** Финальный smoke-test: /start → расчёт → бесплатный вопрос → второй блокируется → тарифы. Зависит от 1.12.0 + 1.16.4.

---

## 🌱 Этап 2 — Расширение (после MVP)

### 2.2 AI — расширение
- [ ] 2.2.1 Qwen-3.6 как доп.модель для верификации (через OpenRouter)
- [ ] 2.2.2 [ai/synthesis.py](ai/synthesis.py) — синтез ответов (Kimi + Qwen)
- [ ] 2.2.3 Маршрутизатор: сложные запросы → Kimi + Qwen + синтез

### 2.3 Новые функции бота
- [ ] 2.3.1 История консультаций (`bot/routers/history.py`)
- [ ] 2.3.2 Редактирование данных рождения
- [ ] 2.3.3 Совместимость пар (две карты)
- [ ] 2.3.4 [bot/routers/profile.py](bot/routers/profile.py) — профиль пользователя

### 2.4 Тесты — расширение покрытия
- [ ] 2.4.1 `tests/unit/test_ai/` — юнит-тесты orchestrator/router/fallback
- [ ] 2.4.2 `tests/unit/test_db/` — репозитории
- [ ] 2.4.3 `tests/integration/` — FSM + консультация end-to-end

---

## 🌳 Этап 4 — Рост (Q4 2026)

- [ ] 4.1 Ежедневный прогноз (TaskIQ рассылка)
- [ ] 4.2 Реферальная программа
- [ ] 4.3 Мультиязычность (EN, UA, KZ)
- [ ] 4.5 pgvector — векторная память для долгосрочных консультаций
- [ ] 4.6 A/B тесты монетизации
- *4.4 (ректификация) перенесена в 5.6 — будет реализована в Mini App*

---

## 🪐 Этап 5 — Mini App PRO (заменяет старый Этап 3)

> Гибридная архитектура (ADR-006): PNG-карта в чате — бесплатно;
> интерактивные периоды, столпы удачи, ректификация — Mini App PRO.

### 5.1 Scaffold (FastAPI + initData security)
- [ ] 5.1.1 [web/main.py](web/main.py) — FastAPI app, mount static/templates, lifespan
- [ ] 5.1.2 dev tunnel (cloudflared / ngrok) для https://localhost
- [ ] 5.1.3 Регистрация Mini App в @BotFather (webapp URL)
- [ ] 5.1.4 [web/security.py](web/security.py) — HMAC-SHA256 валидация Telegram initData
- [ ] 5.1.5 FastAPI dependency `get_current_user` из validated initData
- [ ] 5.1.6 [web/routes/chart.py](web/routes/chart.py) — GET /chart/{id} с проверкой ownership

### 5.2 Static chart view (parity с PNG)
- [ ] 5.2.1 GET /chart/{id} → HTML c теми же 4 столпами + У-син круг
- [ ] 5.2.2 [web/static/js/chart_canvas.js](web/static/js/chart_canvas.js) — Canvas API render
- [ ] 5.2.3 themeParams sync (light/dark) с Telegram WebApp
- [ ] 5.2.4 Адаптивная вёрстка mobile-first

### 5.3 Interactive period slider (PRO Lvl 2)
- [ ] 5.3.1 GET /chart/{id}/with-period?year=&month=&day=&hour=
- [ ] 5.3.2 UI: 4 слайдера / стрелочки ▲▼ для года/месяца/дня/часа
- [ ] 5.3.3 client-side кэш 60-цикла → инстантный пересчёт
- [ ] 5.3.4 анимация подсветки активных 冲/合 при overlay periods

### 5.4 Luck Pillars timeline (PRO Lvl 1)
- [ ] 5.4.1 [web/components/luck_timeline.js](web/components/luck_timeline.js) — горизонтальная шкала 8-10 такт
- [ ] 5.4.2 клик по такту → раскрытие месяцев + дней
- [ ] 5.4.3 текущий возраст → подсветка активного такта
- [ ] 5.4.4 bot/keyboards: «Открыть Столпы удачи» (chart-card kb)
- [ ] 5.4.5 callback `chart:open-luck-pillars` → Telegram WebApp.openLink

### 5.5 Symbolic stars overlay (PRO Lvl 3)
- [ ] 5.5.1 при выборе периода — фильтр Шэнь Ша которые активируются
- [ ] 5.5.2 модальное окно с Markdown-описанием каждой звезды (RAG)

### 5.6 Hour rectification (PRO Lvl 4) — перенесено из 4.4
- [ ] 5.6.1 inline-инструмент: ±1 час / ±15 минут на time-stepper
- [ ] 5.6.2 список Event'ов с проверкой резонанса
- [ ] 5.6.3 финальное «фиксирование» новой даты в Chart

### 5.7 cloudStorage state persistence
- [ ] 5.7.1 `last_period_view` → Telegram cloudStorage
- [ ] 5.7.2 Восстановление при повторном открытии WebApp

### 5.8 PRO монетизация (ЮKassa) — ADR-008
- [ ] 5.8.1 [web/payments.py](web/payments.py) — ЮKassa CreatePayment + redirect URL
- [ ] 5.8.2 ЮKassa webhook → activate Subscription (plan=pro_monthly/yearly)
- [ ] 5.8.3 `@requires_pro` decorator на FastAPI-роутах /chart/{id}/with-period
- [ ] 5.8.4 Pricing page в Mini App с кнопкой «Оплатить»
- [ ] 5.8.5 Subscription provider-agnostic + миграция-план на Stars
