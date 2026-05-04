# БаЦзы-Бот — Бэклог задач

> Статус: 📦 Упакован к разработке (май 2026)
> Методология: AIDD → Plan → Agree → Implement → Verify → Commit

---

## Подготовительные задачи (до кода)

- [x] P-1 Подготовить 24 PNG-ассета иероглифов (10 стволов + 12 ветвей + 2 Инь/Ян) в стиле Mingli
- [ ] P-2 Настроить OpenRouter API аккаунт, получить ключ
- [x] P-3 Создать Yandex Cloud аккаунт, установить `yc` CLI — все ресурсы созданы (PostgreSQL, Redis, VPS, S3)
- [x] P-4 Сделать Gemini Deep Research по 6 архитектурным вопросам (результаты в doc/gemini_research.md)
- [x] P-5 Скаффолд директорий (tests/, knowledge/, monitoring/, web/, tasks/ — все созданы)

---

## Этап 1 — MVP (май–июнь 2026)

### 1.1 Инфраструктура проекта
- [x] 1.1.1 Настроить pyproject.toml (ruff, mypy, pytest, pytest-asyncio)
- [x] 1.1.2 Создать .pre-commit-config.yaml (ruff + mypy + secret scan)
- [x] 1.1.3 Dockerfile (python:3.11-slim + gcc для pyswisseph)
- [x] 1.1.4 docker-compose.yml (bot + web + worker + postgres + redis)
- [x] 1.1.5 GitHub Actions CI/CD (.github/workflows/ci.yml)

### 1.2 Конфигурация и логирование
- [x] 1.2.1 bot/config.py — Pydantic Settings (все env vars из .env.example)
- [x] 1.2.2 Настройка structlog (JSON-формат, trace_id биндинг)
- [x] 1.2.3 Middleware trace_id (bot/middlewares/tracing.py)

### 1.3 База данных
- [x] 1.3.1 db/engine.py — async PostgreSQL engine + session factory
- [x] 1.3.2 db/models.py — SQLAlchemy модели (User, Chart, Consultation, Subscription, Event)
- [x] 1.3.3 Alembic init (migrations/env.py, alembic.ini)
- [x] 1.3.4 Первая миграция: create_initial_tables
- [x] 1.3.5 db/repositories/ — UserRepo, ChartRepo, ConsultationRepo, SubscriptionRepo

### 1.4 Калькулятор Бацзы (stateless ядро)
- [x] 1.4.1 calculator/models.py — ChartInput, ChartOutput (Pydantic)
- [x] 1.4.2 calculator/swiss.py — pyswisseph интеграция (JPL DE431)
- [x] 1.4.3 calculator/true_solar_time.py — TST: LMT + EoT + DST + longitude
- [x] 1.4.4 calculator/solar_terms.py — 24 Цзе Ци (вычисление по эклиптике)
- [x] 1.4.5 calculator/pillars.py — Генерация 4 столпов (年月日時), 60-ричный цикл
- [x] 1.4.6 calculator/hidden_stems.py — Скрытые стволы (3 школы: Traditional, Modern, Ken Lai)
- [x] 1.4.7 calculator/ten_gods.py — Маппинг 10 Божеств
- [x] 1.4.8 calculator/day_master.py — Сила ДМ (полезное/вредное божество)
- [ ] 1.4.9 Тесты калькулятора (tests/unit/test_calculator/) — покрытие 80%+ (единственный модуль с тестами в MVP)

### 1.5 Telegram Bot — базовая структура
- [ ] 1.5.1 bot/main.py — entry point, диспетчер, middleware, роутеры
- [ ] 1.5.2 bot/middlewares/db_session.py — инъекция сессии БД
- [ ] 1.5.3 bot/middlewares/user_middleware.py — get_or_create user
- [ ] 1.5.4 bot/states.py — FSM состояния (BirthDataForm, ConsultationState)
- [ ] 1.5.5 bot/keyboards/ — inline клавиатуры (главное меню, темы, тарифы)

### 1.6 FSM — Сбор данных рождения
- [ ] 1.6.1 bot/routers/start.py — /start, приветствие Анастасии
- [ ] 1.6.2 FSM шаг 1: дата рождения (валидация формата)
- [ ] 1.6.3 FSM шаг 2: время рождения (с вариантом "не знаю")
- [ ] 1.6.4 FSM шаг 3: город рождения → geopy → координаты → timezonefinder
- [ ] 1.6.5 FSM шаг 4: пол
- [ ] 1.6.6 Подтверждение данных + кнопка "Рассчитать" (вызов Calculator из 1.4)

### 1.7 Визуальная карта (Playwright HTML→PNG)
- [ ] 1.7.1 ai/card_renderer.py — рендеринг карты через Playwright (HTML/CSS → PNG screenshot)
- [ ] 1.7.2 Jinja2 HTML-шаблон карты (тёмная тема Mingli, цвета элементов, 4 столпа + баланс)
- [ ] 1.7.3 Загрузка PNG в Yandex Object Storage (aioboto3, кэш по hash данных карты)
- [ ] 1.7.4 Отправка фото в Telegram (send_photo по pre-signed URL)
- [ ] 1.7.5 Fallback: Pillow-композиция из 24 PNG-ассетов если Playwright недоступен

### 1.8 AI Оркестратор (OpenRouter)
- [ ] 1.8.1 ai/orchestrator.py — OpenRouter клиент (httpx async)
- [ ] 1.8.2 Скопировать системный промпт Анастасии в ai/prompts/anastasia_system.md
- [ ] 1.8.3 ai/router.py — семантический маршрутизатор (simple/normal/complex)
- [ ] 1.8.4 ai/context.py — управление контекстом (история в Redis TTL 24ч)
- [ ] 1.8.5 ai/fallback.py — фолбэк Kimi → Claude Sonnet
- [ ] 1.8.6 ai/temporal_context.py — карты текущего года/месяца/дня для временных вопросов

### 1.9 База знаний KuzuDB (RAG для MVP)
- [ ] 1.9.1 knowledge/schema.py — схема граф-узлов KuzuDB (Element, Stem, Branch, Rule, Interpretation)
- [ ] 1.9.2 knowledge/ingest/ — скрипты оцифровки книг в граф
- [ ] 1.9.3 Оцифровка: "База/ba_zi_prompt_anastasia_v2.md" → граф (все правила и связи)
- [ ] 1.9.4 ai/graph_search.py — RAG-поиск по KuzuDB (концепты из вопроса → подграф)
- [ ] 1.9.5 Интеграция graph_search в orchestrator.py

### 1.10 Базовая интерпретация (6 блоков, всегда бесплатно)
- [ ] 1.10.1 ai/base_interpretation.py — генерация 6 блоков через Kimi K2 (использует orchestrator из 1.8)
- [ ] 1.10.2 Блок 1: Баланс элементов (чего не хватает / в избытке)
- [ ] 1.10.3 Блок 2: Господин Дня — описание личности
- [ ] 1.10.4 Блок 3: Реализация по кругу порождения от ГД
- [ ] 1.10.5 Блок 4: Идеальный партнёр (компенсация дисбаланса)
- [ ] 1.10.6 Блок 5: Сильные стороны по всей карте
- [ ] 1.10.7 Блок 6: Влияние текущего года на карту
- [ ] 1.10.8 Форматирование ответа в стиле Анастасии (без "!", 1000-2000 символов)

### 1.11 TaskIQ инфраструктура
- [ ] 1.11.1 tasks/broker.py — настроить TaskIQ broker (Redis backend)
- [ ] 1.11.2 tasks/worker.py — конфигурация воркера, регистрация задач
- [ ] 1.11.3 Запуск воркера в docker-compose (сервис `worker`)

### 1.12 Монетизация и лимиты
- [ ] 1.12.1 Redis rate limiter (счётчик вопросов/день для free)
- [ ] 1.12.2 bot/routers/subscription.py — экран тарифов (Месяц 290₽ / 3 месяца 990₽ / Год 2490₽)
- [ ] 1.12.3 ЮKassa интеграция — создание платежа, получение URL
- [ ] 1.12.4 ЮKassa webhook handler (FastAPI endpoint) — приём уведомлений об оплате
- [ ] 1.12.5 Логика: 1 бесплатный вопрос для новых пользователей
- [ ] 1.12.6 После оплаты: обновить Subscription в БД

### 1.13 Консультация — диалог с Анастасией
- [ ] 1.13.1 bot/routers/consultation.py — кнопка "Задать вопрос", ввод вопроса
- [ ] 1.13.2 Формирование контекста LLM (промпт + карта + история + KuzuDB граф из 1.9)
- [ ] 1.13.3 Детектор временных вопросов (regex) → подгрузка temporal context
- [ ] 1.13.4 TaskIQ для долгих запросов (>30 сек) с "Звёзды считают..." (использует 1.11)
- [ ] 1.13.5 Сохранение Consultation в БД (токены, стоимость, trace_id)

### 1.14 Мониторинг
- [ ] 1.14.1 monitoring/langfuse.py — Langfuse клиент и helpers
- [ ] 1.14.2 Логирование каждого AI-запроса (trace_id, cost_usd, latency)
- [ ] 1.14.3 Алерты в приватный Telegram-канал (timeout, 5xx, budget)

### 1.15 Админ-панель
- [ ] 1.15.1 bot/routers/admin.py — команды для владельца (/admin stats, /admin export, /admin model)
- [ ] 1.15.2 /admin stats — DAU, вопросы/день, выручка, конверсия
- [ ] 1.15.3 /admin export — CSV диалогов в Yandex Object Storage → ссылка
- [ ] 1.15.4 /admin model — смена модели LLM без деплоя (через Redis feature flag)
- [ ] 1.15.5 FastAPI admin page (Basic Auth) — дашборд с теми же метриками

### 1.16 Деплой MVP
- [x] 1.16.1 Создать ресурсы Yandex Cloud (VPS, PostgreSQL, Redis, Object Storage) — созданы 2026-05-02
- [ ] 1.16.2 Загрузить Docker-образ в Yandex Container Registry
- [ ] 1.16.3 Запустить миграции Alembic
- [ ] 1.16.4 Настроить Telegram webhook
- [ ] 1.16.5 Smoke test: /start → карта → бесплатный вопрос → тарифы

---

## Этап 2 — Расширение (июль–август 2026)

### 2.1 Калькулятор — расширение
- [ ] 2.1.1 calculator/luck_pillars.py — Столпы Удачи (Да Юнь) до минуты
- [ ] 2.1.2 calculator/interactions.py — все взаимодействия (合沖刑害破)
- [ ] 2.1.3 calculator/symbolic_stars.py — 50-90 Шэнь Ша
- [ ] 2.1.4 calculator/auxiliary.py — Мин Гун, Тай Юань
- [ ] 2.1.5 calculator/structure.py — Специальные структуры карты (格局)

### 2.2 AI — расширение
- [ ] 2.2.1 Qwen-3.6 как дополнительная модель для верификации (через OpenRouter)
- [ ] 2.2.2 ai/synthesis.py — синтез ответов (Kimi + Qwen)
- [ ] 2.2.3 Маршрутизатор: сложные запросы → Kimi + Qwen + синтез

### 2.3 Новые функции бота
- [ ] 2.3.1 История консультаций (bot/routers/history.py)
- [ ] 2.3.2 Редактирование данных рождения
- [ ] 2.3.3 Совместимость пар (две карты)
- [ ] 2.3.4 bot/routers/profile.py — профиль пользователя

### 2.4 Тесты — расширение покрытия
- [ ] 2.4.1 tests/unit/test_ai/ — юнит-тесты orchestrator, router, fallback
- [ ] 2.4.2 tests/unit/test_db/ — репозитории
- [ ] 2.4.3 tests/integration/ — FSM, консультация end-to-end

---

## Этап 3 — Визуализация (Q3 2026)

- [ ] 3.1 FastAPI — HTML-страницы карты (Jinja2 + HTMX)
- [ ] 3.2 Chart.js radar charts (10 Божеств, баланс элементов)
- [ ] 3.3 Telegram Mini App интеграция
- [ ] 3.4 Уникальные токены для ссылок на карты (TTL)
- [ ] 3.5 Встроенный чат с Анастасией в Mini App

---

## Этап 4 — Рост (Q4 2026)

- [ ] 4.1 Ежедневный прогноз (TaskIQ рассылка)
- [ ] 4.2 Реферальная программа
- [ ] 4.3 Мультиязычность (EN, UA, KZ)
- [ ] 4.4 Ректификация часа рождения
- [ ] 4.5 pgvector — векторная память для долгосрочных консультаций
- [ ] 4.6 A/B тесты монетизации
