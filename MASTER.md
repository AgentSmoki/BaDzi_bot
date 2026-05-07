# БаЦзы-Бот — Мастер-документ проекта

> Telegram-бот для персональных AI-консультаций по системе Ба Цзы (四柱命理)
> с консультантом Анастасией. Высокоточный расчёт + мульти-модельный AI.

**Разработчик:** Богдан
**Дата старта:** март 2026
**Статус:** 🚧 Разделы 1.5, 1.6 и большая часть 1.7 закрыты (2026-05-07). End-to-end FSM собирает данные → Calculator → БД → SVG/CairoSVG-карта (PNG) → Telegram. ⚠️ **Открытые баги визуала после последнего деплоя** — см. секцию «Известные проблемы» ниже. 369/369 тестов ✓ покрытие 97%.
**Версия документа:** 3.4

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
| [doc/product_idea.md](doc/product_idea.md)                                                                 | Бизнес-идея: проблема, решение, ЦА, монетизация, метрики, конкуренты, риски                                                             |
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

| Компонент        | Технология                                                |
| ---------------- | --------------------------------------------------------- |
| Swiss Ephemeris  | pyswisseph (JPL DE431)                                    |
| Геокодирование   | Google Geocoding → Yandex HTTP Geocoder → Nominatim chain |
| Таймзоны         | Google TimeZone API + timezonefinder fallback (IANA)      |
| DST история      | pytz                                                      |
| Equation of Time | Jean Meeus / NOAA                                         |

### Mini App PRO

| Компонент        | Технология                                         |
| ---------------- | -------------------------------------------------- |
| Web framework    | FastAPI + Jinja2                                   |
| Frontend         | Canvas API (vanilla JS), без React/Vue             |
| Auth             | Telegram WebApp.initData → HMAC-SHA256 валидация   |
| State            | Telegram cloudStorage (last_period_view)           |
| Render           | CairoSVG + Pillow (ProcessPoolExecutor pool)       |
| Платежи          | ЮKassa redirect (см. ADR-008)                      |

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
| Yandex Cloud ресурсы | VPS + PostgreSQL + Redis + Object Storage | ⏳ Настроить (см. doc/deploy.md) |

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

## Прогресс разработки

**Последний коммит:** `00354bc` (2026-05-07)
**Тесты:** 369/369 ✓ покрытие 97%
**Линтеры:** ruff ✓, ruff-format ✓, mypy strict ✓, pre-commit ✓

### ⚠️ Известные проблемы (на момент 2026-05-07, до фикса)

После последней волны UX (`00354bc`) при живом тестировании в Telegram пользователь видит регрессии в карте:

1. **Emoji в круге У-син не отображаются.** На локальном `cairosvg.svg2png()` (macOS) Apple Color Emoji 🌳🔥⛰⚙💧 рендерятся в цвете — это подтверждено выводом в `/tmp/v8.png`. Но в полученной из бота карте у пользователя они отсутствуют либо рисуются как пустые. **Гипотезы:**
   - Кэш Jinja2 шаблонов не обновился — бот мог не подхватить новый `chart.svg.j2` без рестарта (хотя бот рестартовали).
   - У пользователя другой запуск/инстанс бота, где emoji-шрифт не доступен.
   - При вызове через `asyncio.to_thread` контекст шрифтов отличается от прямого вызова.
   - Проверить: запустить рендер из бота с дампом SVG в файл, сравнить с прямым вызовом.
2. **«Расположение шрифтов съехало».** Полоса «Господин дня» / соседние блоки по словам пользователя выглядят неаккуратно (вероятно: позиционирование `dm-stem-big` поехало после увеличения карты до 1400 px, либо новый шрифт не подхватывается). Нужны свежие скриншоты в новом диалоге.
3. **Чат может всё ещё накапливаться** на некоторых путях. `_step` редактирует FSM-якорь, но нужно проверить:
   - Что после photo (handle_confirm_calc) `fsm_msg_id=None` корректно сбрасывается перед naming-промптом.
   - Что после `state.clear()` в `handle_naming_*` следующий `send_main_menu(state=state)` правильно заводит новый якорь.
   - Что повторный `/start` не пытается отредактировать сообщение из прошлой сессии (state очищается, ОК).
4. **Удаление дублей карт уже работает** в `list_unique_by_user`, но нужно подтвердить визуально: после повторного создания идентичной карты в «Мои карты» виден только один экземпляр.

**Точки входа для отладки:**
- `ai/svg_renderer.py` — `_build_context` + `_wuxing_wheel`
- `web/templates/chart.svg.j2` — секция wuxing wheel + `.dm-stem-big` в strip
- `bot/routers/birth_data.py` — `_step` helper и FSM-msg_id треккинг
- Прямой тест: `python -c "from ai.svg_renderer import render_chart_png ..."` + сравнение с `bot.main` runtime-выводом

### ✅ Сессия 2026-05-07 (вторая половина) — Wave A: карта v2 + UX bundle

| Задача | Файлы | Коммит | Содержание |
|--------|-------|--------|------------|
| Plan-mode | `~/.claude/plans/crispy-cooking-scone.md` | — | Зафиксирован roadmap: Wave A (Card v2) → 1.8 AI → Wave C (Mini App). Старый Этап 3 заменён на детальный Этап 5 |
| Docs | `tasks.md`, `MASTER.md`, `vision.mdc` | `c405987` | Реструктуризация секции 1.7, новый Этап 5 (Mini App PRO 5.1-5.8), ADR-006/007/008 |
| 1.7.6/7/8 | `ai/svg_renderer.py`, `web/templates/chart.svg.j2`, `pyproject.toml` | `658dc01` | SVG-рендер (CairoSVG + Pillow + Jinja2). Light-Mingli шаблон. Playwright fallback в `card_renderer.py` |
| Card v2 polish | + | `a7aa0cc` | У-син redesign: пентагон с ДМ сверху, role-labels («Личность, друзья», «Самовыражение», «Богатство, жена», «Власть, муж», «Ресурсы»), generation arrows |
| Hidden stems hex grid | + | `abca00d` | Скрытые стволы: каждый stem в цвете элемента + русская подпись «Инь/Ян Стихия» под каждым. Контрольный цикл (звезда из пунктирных стрелок) |
| Big UX bundle | `ai/svg_renderer.py`, `bot/services/menu.py`, `bot/services/birth_data.py` (refactor), `bot/routers/start.py`, `db/repositories/chart_repo.py` | `00354bc` | **5 фич:** (1) emoji-иконки 🌳🔥⛰⚙💧 в У-син + центрирование пентагона, (2) увеличенный шрифт «Господина дня» с горизонтальным разделителем, (3) `send_main_menu` после naming-шага, (4) `list_unique_by_user` дедуп карт, (5) edit-in-place чат через `_step` helper и `fsm_msg_id` |

**Ключевые архитектурные решения:**
- **ADR-006 Hybrid Bot+MiniApp** — PNG в чате (free) + WebApp (PRO).
- **ADR-007 Render = Pillow + CairoSVG** — миграция с Playwright (5-10× быстрее, без 150 MB Chromium binary). Playwright остаётся fallback'ом до стабилизации.
- **ADR-008 Payments = ЮKassa везде** — provider-agnostic Subscription, готов к миграции на Telegram Stars если ToS изменится.

**Что переименовалось в `tasks.md`:**
- Старый «Этап 3 Визуализация» (5 пунктов) → новый «Этап 5 Mini App PRO» (5.1-5.8: scaffold, static view, period slider, luck pillars timeline, symbolic stars overlay, hour rectification, cloudStorage, ЮKassa).
- Раздел 1.7 переразбит на 1.7.1-1.7.11 (v1 закрыт как legacy, v2 на CairoSVG).
- 4.4 Ректификация перенесена в 5.6 (Mini App).

### ✅ Сессия 2026-05-06 / 07 — разделы 1.5, 1.6 + калькулятор-фасад

| Задача | Файлы | Коммит | Содержание |
|--------|-------|--------|------------|
| 1.5.1 | `bot/main.py` | `6a123b1` | Entry point: aiogram Bot + Dispatcher + RedisStorage для FSM, polling |
| 1.5.2 | `bot/middlewares/db_session.py` | `c5e3705` | Инъекция `AsyncSession` через `session_scope()` |
| 1.5.3 | `bot/middlewares/user_middleware.py` | `d662ab2` | `get_or_create` пользователя с FOR UPDATE SKIP LOCKED |
| 1.5.4 | `bot/states.py` | `7e78a7e` | FSM `BirthDataForm` + `ConsultationState` |
| 1.5.5 | `bot/keyboards/__init__.py` | `bbfcf88` | Inline-клавиатуры (главное меню, темы, тарифы) |
| 1.6.1 | `bot/routers/start.py` | `2c1ad40` | `/start` с веткой по картам (Variant B), цитата мастера ЭдоХа |
| 1.6.2 | `bot/routers/birth_data.py` | `afcee2b` | FSM шаг 1: дата (dateparser, DATE_ORDER=DMY) |
| 1.6.3 | + | `23c0211` | FSM шаг 2: время с опцией «не знаю» |
| 1.6.4 | `bot/services/geocoding.py` | `1d86fe2` | FSM шаг 3: город + inline-выбор top-3 |
| 1.6.5 | + | `6f50472` | FSM шаг 4: пол + summary для подтверждения |
| 1.6.6 | `calculator/__init__.py` (facade) | `0508928` | Подтверждение → Calculator → БД (chart_data JSONB), все 2.1 расширения сохраняются |

### 🔧 Ключевые правки и улучшения

- **Calculator facade** ([calculator/__init__.py](calculator/__init__.py)) — `calculate_chart()` оркеструет все модули: pillars, hidden_stems, ten_gods, element_balance, true_solar_time, luck_pillars, interactions, symbolic_stars, auxiliary, structures. Всё сохраняется в `Chart.chart_data` JSONB.
- **Геокодер чейн** Google → Yandex → Nominatim ([bot/services/geocoding.py](bot/services/geocoding.py)) — Google и Yandex умеют fuzzy («Волхоград» → «Волгоград»), Nominatim как страховка. Nominatim CA-fix через Apple `Install Certificates.command`. Yandex требует HTTP-заголовок `Referer` чтобы пускать в HTTP-Geocoder API (иначе `403 Invalid api key`).
- **Календарь карт** — после расчёта пользователь даёт имя карте (или пропускает → показ как `{ДМ} {дата}`). Returning-user kb выводит ВСЕ карты юзера (10 на страницу, ◀/▶ пагинация). `chart:open:{uuid}` хендлер выводит полную сводку из JSONB.
- **Контекстный «Изменить»** — на каждом шаге FSM кнопка переименовывается («Изменить дату» / «Время» / «Город»). На confirm-шаге — picker с выбором поля для surgical edit.
- **Час без времени** — когда `has_birth_time=False`, столп часа из noon-fallback скрыт в выводе, заголовок «Карта рассчитана (без столпа часа)».
- **Время — лёгкий парсинг**: `23:55`, `23.55`, `23,55`, `23-55`, `1430`, `2355`, `955`, голый час `14`, `14ч`. 5+ цифр отвергается.
- **Дата — DD.MM.YYYY**: `dateparser` с `settings={"DATE_ORDER": "DMY"}` чтобы `12.09.1999` парсилось как 12 сентября.
- **uvloop удалён** — у него SSL-handshake bug на macOS, валил коннект к Telegram. aiogram теперь использует штатный asyncio.

### ✅ Сессия 2026-05-05 — раздел 2.1 «Калькулятор — расширение» закрыт

| Задача | Файлы | Коммит | Содержание |
|--------|-------|--------|------------|
| 2.1.1 | `calculator/luck_pillars.py` | `f8ec46b` | Столпы Удачи (大運) до минуты + абсолютные `start_datetime` границ |
| 2.1.2 | `calculator/interactions.py` | `6ba0e95` | 9 типов взаимодействий 合沖刑害破: 5合, 6沖, 6合, 3合, 半合, 3刑, 自刑, 6害, 6破 |
| 2.1.3 | `calculator/symbolic_stars.py` + `_tables.py` | `8434c9e` | 60 классических Шэнь Ша (神煞) в 7 категориях детекторов |
| 2.1.4 | `calculator/auxiliary.py` | `0f85d2f` | 胎元 (Тай Юань) + 命宫 (Мин Гун) — выверены против Mingli-эталона Волжский 1999 |
| 2.1.5-A | `calculator/symbolic_stars.py` | `18672cf` | Отложенные Шэнь Ша: 空亡 (Сюнь), 元辰 (Y/N формула), 勾绞 (±3) |
| 2.1.5-B | `calculator/structures.py` + `_tables.py` | `269c515` | 25 классических 格局 в каскаде 化→从→一气→月令-special→正格 |

### 📚 Ключевые артефакты сессии

- **Research-документация:**
  - [doc/research/symbolic_stars_v2_gemini.md](doc/research/symbolic_stars_v2_gemini.md) — 75 Шэнь Ша (выгрузка Gemini)
  - [doc/research/structures_v2_perplexity_deep.md](doc/research/structures_v2_perplexity_deep.md) — 73KB справочник 30 格局 (Perplexity sonar-deep-research, верифицирован против 三命通会 / 渊海子平 / 神峰通考 / 子平真詮)
- **Утилиты для дальнейшего research:**
  - [scripts/research_bazi_structures.py](scripts/research_bazi_structures.py) — переиспользуемый скрипт через OpenRouter Perplexity с Bazi-специфичным system prompt (без галлюцинаций PyPI и Python-кода)
- **Канонический эталон:** карта Волжский 1999 (己卯/癸酉/丁亥/庚子) → 偏财格, 胎元=甲子, 命宫=癸酉.

### 🔜 Следующая сессия — стартовать с

**Сначала — пофиксить регрессии визуала** (см. «Известные проблемы» выше):
1. Воспроизвести проблему с emoji в карте: получить SVG-дамп от runtime-бота, сравнить с прямым `cairosvg.svg2png()`.
2. Проверить расположение шрифтов в полосе «Господин дня» после изменений 1400-px холста.
3. Live-тест полного потока с свежими скриншотами от пользователя.

**После фикса — раздел 1.8 «AI Оркестратор» (Wave B):**
- [ ] **1.8.1** `ai/orchestrator.py` — OpenRouter клиент (httpx async)
- [ ] **1.8.2** Скопировать промпт Анастасии в `ai/prompts/anastasia_system.md`
- [ ] **1.8.3** `ai/router.py` — семантический маршрутизатор (simple/normal/complex)
- [ ] **1.8.4** `ai/context.py` — управление контекстом (история в Redis TTL 24ч)
- [ ] **1.8.5** `ai/fallback.py` — фолбэк Kimi → Claude Sonnet
- [ ] **1.8.6** `ai/temporal_context.py` — карты текущего года/месяца/дня

**После 1.8 → 1.10 (базовая интерпретация 6 блоков) → Wave C (Этап 5 Mini App PRO).**

### ⏭️ Отложено на v3 (Determinism Low/Very Low)

В `structures.py` не реализованы (требуют экспертного слоя): 拱禄, 飞天禄马, 倒冲, 邀禄, 两神成象, 子辰双美.

### 🧭 Что читать первым при возобновлении

1. **MASTER.md** (этот файл) — общий статус и прогресс.
2. **[tasks.md](tasks.md)** — backlog с `[x]` отметками выполненных задач.
3. **[.cursor/rules/vision.mdc](.cursor/rules/vision.mdc)** + **[conventions.mdc](.cursor/rules/conventions.mdc)** + **[workflow.mdc](.cursor/rules/workflow.mdc)** — обязательное чтение перед бизнес-кодом.
4. **doc/research/** — справочники по Бацзы для дальнейших задач калькулятора.
5. `git log --oneline -10` — последние коммиты для быстрой ориентации.

---

## Дорожная карта

### Этап 1 — MVP (март-апрель 2026)

Структура проекта → Модели БД → FSM → pyswisseph → TST → Калькулятор (4 столпа, ДМ, 10 Божеств) → LiteLLM (Claude) → Промпт Анастасии → Консультация → Лимиты → Подписка → Docker → CI/CD → Деплой на Railway

### Этап 2 — Расширение (май-июнь 2026)

Цзе Ци → Столпы Удачи → Все взаимодействия → 3 школы скрытых стволов → 50-90 звёзд → Мин Гун/Тай Юань → Qwen + Kimi → AI-маршрутизатор → Синтез → Фолбэк → Langfuse → TaskIQ

### Этап 4 — Рост (Q4 2026)

Ежедневные прогнозы → Реферальная программа → Мультиязычность → Кэш интерпретаций → A/B тесты → Векторная память (pgvector)

### Этап 5 — Mini App PRO (Q3-Q4 2026, заменяет старый Этап 3)

FastAPI scaffold + initData HMAC → static chart view (Canvas) → интерактивный period slider (PRO Lvl 2) → Luck Pillars timeline (PRO Lvl 1) → Symbolic stars overlay (PRO Lvl 3) → Hour rectification (PRO Lvl 4) → cloudStorage persistence → ЮKassa в Mini App

Подробности — [tasks.md](tasks.md) Этап 5, ADR-006 в [vision.mdc](.cursor/rules/vision.mdc).
