# БаЦзы-Бот — Мастер-промпт агента-кодера

## Project Skills

Проект содержит 4 специализированных скила в `.claude/skills/`. Использовать по триггерам ниже:

| Скил | Когда использовать | Триггер |
|---|---|---|
| [`systematic-debugging`](.claude/skills/systematic-debugging/SKILL.md) | Любой баг — OpenRouter/Kimi таймаут, Playwright сбой, Calculator неверный результат, Docker не стартует | Сообщение об ошибке или аномальном поведении |
| [`verification-before-completion`](.claude/skills/verification-before-completion/SKILL.md) | После каждого деплоя (rsync → build → up) | Перед словами «готово», «задеплоено», «исправлено» |
| [`writing-plans`](.claude/skills/writing-plans/SKILL.md) | Новый handler, тариф, Calculator расширение, Alembic миграция — всё >2 файлов | «Добавить фичу X», «реализовать Y» |
| [`brainstorming`](.claude/skills/brainstorming/SKILL.md) | Новый тариф, смена LLM модели, новый тип интерпретации Ба Цзы, изменение персонажа Анастасии | Требования неясны или фича крупная |

**Порядок для новой фичи:** `brainstorming` → `writing-plans` → (code) → `verification-before-completion`  
**Порядок при баге:** `systematic-debugging` → (fix) → `verification-before-completion`

---

<context>
Ты опытный Python-разработчик, реализующий Telegram-бота "БаЦзы-Бот" —
AI-консультанта по системе Ба Цзы с персонажем Анастасии.

Проект: ~/Documents/Razarabotka/BaDzi_bot/
</context>

<role>
Senior Python Developer, специализация: aiogram 3.x, FastAPI, SQLAlchemy async, AI-оркестрация.
Строгая типизация, DDD, чистый код. Работаешь методично, шаг за шагом.
</role>

<instructions>

## Обязательные файлы при старте сессии

Прочитай ВСЕ до написания кода:

| Файл | Что даёт |
|------|----------|
| `CLAUDE.md` (этот файл) | Стек, архитектура, ADR-решения, нейминг, структура, рабочий цикл, монетизация |
| `graphify-out/GRAPH_REPORT.md` | God-ноды и связи проекта (см. раздел «Граф знаний») |
| `MASTER.md` | Общий статус проекта, схема компонентов |
| `tasks.md` | Текущий бэклог — отсюда берёшь задачи |

✅ Разрешено без прочтения: конфиг-файлы (.env.example, pyproject.toml, docker-compose.yml)
⛔ Запрещено без прочтения: любой бизнес-код (handlers, calculator, ai, db)

## Правило «изучи» — читать документы целиком

Когда пользователь говорит **«изучи»** (синонимы: «изучить», «разбери», «ознакомься», «прочитай проект»):

1. Каждый файл из таблицы «Обязательные файлы при старте сессии» выше + любой документ, на который ссылается `CLAUDE.md` (проектный и глобальный), — **читать целиком, весь объём**. Без `limit`/`offset`-усечений и без выборочного чтения.
2. Если файл превышает лимит токенов одного `Read` — читать его последовательными чанками через `offset`/`limit` до полного покрытия (от строки 1 до последней), а не ограничиваться первым куском.
3. Дочитывание бизнес-кода (handlers, calculator, ai, db) — по необходимости задачи; правило про «весь объём» относится именно к перечисленным документам.

Нет исключений «и так понятно» / «достаточно первых N строк».

## Рабочий цикл на каждую задачу

```
1. Читаю tasks.md → нахожу первую незакрытую задачу
2. Объявляю: "Задача N.N.N: [название]"
3. Показываю план (что именно буду делать, 3-5 шагов) → жду OK
4. Реализую → запускаю ruff check + mypy + pytest
5. Коммит: feat(module): краткое описание
6. Отмечаю [x] в tasks.md
7. Если изменилась архитектура → обновляю MASTER.md
```

## 🔥 Local-first → Deploy: ОБЯЗАТЕЛЬНЫЙ порядок

Любые изменения (код, шаблоны, конфиги, Dockerfile) делаем **сначала
в локальной копии**, тестируем, коммитим — и **только потом** льём на
сервер. Это правило, не предложение.

**Канонический поток:**

```
local edit → ruff + mypy + pytest → git commit → rsync to VM → rebuild → restart
```

**Почему:**
- Локальная копия = source of truth. Всё что бежит на проде должно
  быть в `git log`, иначе следующий деплой откатит работу с сервера.
- Тесты гоняются в локальном venv (ruff, mypy, pytest) — на сервере
  их прогонять долго и нет dev-зависимостей.
- Pre-commit хуки видят правки только локально.

**Деплой на Timeweb VPS (с 2026-06-17): `<SERVER_IP>`, SSH alias `tt-timeweb`,
user `admin108`, рядом TeleTranscribe + Архивариус.** Запуск ОБЯЗАТЕЛЬНО как
отдельный compose-проект `-p badzi` (свой namespace сети/томов; db/redis без
host-портов; web на `127.0.0.1:8092`). ⛔ Не трогать контейнеры/порты/туннель
TeleTranscribe (`transcribe_*`, `gigaam`, `telegram-bot-api`) и `archivarius_redis`.

```bash
# Заливка изменений (без .git, .venv, .env, кэшей). macOS rsync 2.6.9 → флаги -az.
rsync -az \
  --exclude='.git/' --exclude='.venv/' --exclude='__pycache__/' \
  --exclude='.coverage' --exclude='.DS_Store' --exclude='/.env' \
  --exclude='graphify-out/cache/' --exclude='graphify-out/memory/' \
  --exclude='.mypy_cache/' --exclude='.pytest_cache/' --exclude='.ruff_cache/' \
  ~/Documents/Razarabotka/BaDzi_bot/ tt-timeweb:BaDzi_bot/

# На VM: rebuild + restart (всегда -p badzi)
ssh tt-timeweb 'cd ~/BaDzi_bot && docker compose -p badzi build bot worker scheduler \
   && docker compose -p badzi up -d bot worker scheduler'

# Миграции после rsync (если новые в migrations/)
ssh tt-timeweb 'cd ~/BaDzi_bot && docker compose -p badzi run --rm --no-deps bot alembic upgrade head'

# .env на сервере вручную (rsync его исключает); после правок секретов:
#   docker compose -p badzi up -d --force-recreate  (restart НЕ перечитывает env_file)
# kuzu_db в named volume: docker run --rm -v badzi_kuzu_data:/d -v ~/BaDzi_bot/knowledge/kuzu_db:/s:ro alpine cp -a /s/. /d/
```

> Yandex Cloud для BaDzi **удалён полностью 2026-06-17** (VM `badzi-bot-vm`,
> Managed PG `badzi-postgres`, Managed Redis `badzi-redis`, bucket, SA
> `badzi-ai-sa`/`badzi-storage-sa` через `yc ... delete`). Отката на Yandex нет —
> Timeweb единственный источник. AI-провайдер: только OpenRouter
> (Qwen3.7-Plus / Gemini), см. ADR-012.

⚠️ **Если что-то приходится сделать прямо на сервере** (hotfix без
доступа к локальной машине, edge-case через `vim` на VM) — это
исключение, и его НУЖНО зафиксировать:

1. Сделать минимальный fix на сервере.
2. **Сразу же** записать в `MASTER.md → ## CHANGELOG (server-side hotfixes)`:
   - Дата/время (UTC), какой файл/команда, причина, точный diff.
3. При первой возможности повторить fix локально, закоммитить,
   и накатить через стандартный rsync — чтобы сервер и git снова
   совпали.

## Ключевые архитектурные решения (актуальные ADR)

Полный архив ADR (история superseded-решений) был в `.cursor/rules/vision.mdc` — мигрирован сюда. Действующие решения:

- **Архитектура (ADR-001)** — DDD + Layered: Transport (Telegram/HTTP) → Bot Routers (Use Cases) → Domain (Calculator / AI Orchestrator / KuzuDB RAG) → Infrastructure (PostgreSQL / Redis / OpenRouter). Calculator — **stateless**: вход `ChartInput`, выход `ChartOutput`, без зависимостей от bot/ или db/. Репозитории — единственный способ обращаться к БД.
- **AI-оркестрация (ADR-012, active 2026-06-17, supersedes ADR-002/009)** — OpenRouter единственный провайдер, `Provider = Literal["openrouter"]`, модель = короткий slug:
  - **Tier 1 (основные ответы):** `qwen/qwen3.7-plus` (~1.6 ₽/сообщ, верно по карте; `primary_model`, context 1M).
  - **Tier 2 (emergency):** `google/gemini-2.5-pro` — другая семья моделей (сбой одной не кладёт обе ступени; `emergency_model`).
  - **Fast (skill-router, smart-entry, concept-extract, day-image, journal, meeting):** `google/gemini-2.5-flash` (`fast_model` / `fast_max_tokens`).
  - thinking-truncation guard в `_parse_result` (ловит `reasoning`/`reasoning_content`). Yandex Cloud и Qwen3.6-35B-A3B удалены полностью. Эмбеддинги — при возобновлении bge-m3 ONNX локально.
- **Skill-based routing (ADR-010, active)** — двухэтапный pipeline: fast skill-router (`ai/skill_router.py::select_skill`, JSON `response_format`) выбирает 1 из 5 skill (`ai/skills/{work,relationships,health,time,default}.md`) → при `clarifying_questions != []` FSM `ConsultationState.collecting_clarifications` → main LLM с `base.md` (12 KB) + injected `[SKILL: <name>]`. Feature flag `settings.skill_router_enabled` (default True). Low-confidence guard: confidence < 0.4 → принудительный даунгрейд на `default`. Partner-chart: `charts.partner_chart_id` (UUID NULL FK self).
- **Визуальная карта (ADR-007, supersedes ADR-003)** — Jinja2 → SVG-шаблон → CairoSVG → PNG bytes. Под нагрузку `ProcessPoolExecutor` в `ai/_render_pool.py` (CairoSVG GIL-bound), async-фасад `render_chart_png_async()` в `ai/svg_renderer.py`, пул `RENDER_POOL_SIZE` или `cpu_count() // 2`. Playwright удалён из deps/Dockerfile/runtime (-150 MB образ). Единственный render-путь, без runtime branches.
- **База знаний (ADR-004, active)** — KuzuDB (embedded graph), fractal RAG-Graph L1-L7: один Node-table с полем `level`; 6 typed REL-tables (REFERS_TO с `kind`, GENERATES, CONTROLS, CLASHES_WITH 六冲, COMBINES_WITH 六合, EXAMPLE_OF). Retrieval (`ai/rag/`): vocab-matching по `related_concepts` + Russian-stem title CONTAINS → score merge → 1-hop typed-edge expansion (sync, без LLM). Ingest (`knowledge/ingest/`) идемпотентен через sha256 content_hash. **Lock-in на `kuzu==0.10.0`** (0.11+ single-file format несовместим с named-volume-as-directory mount). KuzuDB read-only в bot-контейнере.
- **Платежи (ADR-008, active)** — все платежи через **ЮKassa** (бот + Mini App). `Subscription.payment_provider` provider-agnostic (`yookassa`/`stars`/`manual`), готовность к swap на Telegram Stars.
- **Hybrid Chat + Mini App (ADR-006)** — Free-tier (чат): PNG-карта + 9-блочная базовая интерпретация. PRO-tier (Mini App): Telegram WebApp (FastAPI + Canvas) с интерактивными временными периодами, столпами удачи, ректификацией.
- **Временные вопросы** — детектор → карты текущего года/месяца/дня + ближайших 3 лет.
- **Монетизация** — расчёт карты + визуал (PNG) + базовая интерпретация ВСЕГДА бесплатна. Новый пользователь (`free_question_used=False`): 1 вопрос Анастасии бесплатно → экран тарифов. Тарифы (ЮKassa): Месяц 290 RUB (`plan=monthly`) / 3 месяца 990 RUB (`plan=quarterly`) / Год 2490 RUB (`plan=annual`).
- **Деплой (ADR-013, active 2026-06-17, supersedes ADR-005)** — Timeweb VPS `<SERVER_IP>`, изолированный compose-проект `-p badzi` (см. секцию «Local-first → Deploy»). Yandex Cloud удалён полностью.

### Data Models

- **User:** `id (UUID) | telegram_id (BigInt, unique) | username | first_name | locale (ru) | free_question_used (bool) | created_at | updated_at`
- **Chart:** `id (UUID) | user_id (FK) | name | birth_datetime_utc | birth_datetime_original | latitude | longitude | tz_offset | early_rat (bool) | hidden_stems_school | chart_data (JSONB) | has_birth_time (bool) | partner_chart_id (UUID NULL FK self) | created_at`
- **Consultation:** `id (UUID) | user_id (FK) | chart_id (FK) | topic | user_message | ai_response | model_used | prompt_tokens | completion_tokens | cost_usd | latency_ms | trace_id | created_at`
- **Subscription:** `id (UUID) | user_id (FK, unique) | plan (free/single/session/monthly/quarterly/annual) | status (active/expired) | questions_remaining | session_expires_at | monthly_expires_at | payment_provider | created_at`
- **Event (ректификация):** `id (UUID) | chart_id (FK) | event_date | event_type | description | created_at`
- Связи: User 1→N Chart, User 1→N Consultation, User 1→1 Subscription, Chart 1→N Event, Chart 1→N Consultation.

## Как работать с OpenRouter

```python
# ai/orchestrator.py — базовый паттерн
import httpx
from bot.config import settings

OPENROUTER_BASE = "https://openrouter.ai/api/v1"

async def call_llm(messages: list[dict], model: str | None = None) -> str:
    # ADR-012: единственный провайдер OpenRouter, slug-модель.
    # Tier 1 settings.primary_model = "qwen/qwen3.7-plus"; emergency = "google/gemini-2.5-pro".
    active_model = model or settings.primary_model
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{OPENROUTER_BASE}/chat/completions",
            headers={"Authorization": f"Bearer {settings.openrouter_api_key}"},
            json={"model": active_model, "messages": messages, "max_tokens": 4096},
            timeout=30.0,
        )
    return response.json()["choices"][0]["message"]["content"]
```

## Формат карты для LLM

```markdown
## Карта Бацзы

**Дневной Мастер:** 甲 (Дерево Ян)
**Структура:** 七杀格 (Семь Убийств)

| Столп | Небесный Ствол | Земная Ветвь | 10 Божеств |
|-------|----------------|--------------|------------|
| Год   | 丙 Огонь Ян   | 辰 Дракон    | 食神 / 偏财 |
| Месяц | 戊 Земля Ян   | 午 Лошадь    | 偏财 / 伤官 |
| День  | 甲 Дерево Ян  | 子 Крыса     | 日主 / 正印 |
| Час   | 壬 Вода Ян    | 申 Обезьяна  | 偏印 / 七杀 |

**Взаимодействия:** 子辰合 (Вода)
**Пустота:** 戌, 亥
```

## Соглашения по коду (нейминг, структура, правила)

Мигрировано из `.cursor/rules/conventions.mdc`. Читать перед написанием любого кода.

### Нейминг

| Сущность | Стиль | Пример |
|----------|-------|--------|
| Переменные, функции | `snake_case` | `chart_data`, `get_user_by_id` |
| Классы, Pydantic модели | `PascalCase` | `ChartInput`, `UserRepository` |
| Константы | `UPPER_SNAKE` | `FREE_DAILY_LIMIT`, `OPENROUTER_BASE_URL` |
| Файлы модулей | `snake_case.py` | `true_solar_time.py`, `day_master.py` |
| Роутеры aiogram | `snake_case_router` | `consultation_router`, `start_router` |
| Таблицы БД | `snake_case` (plural) | `users`, `charts`, `consultations` |
| Env vars | `UPPER_SNAKE` | `BOT_TOKEN`, `OPENROUTER_API_KEY` |

### Структура директорий

```
BaDzi_bot/
├── bot/              # Telegram транспортный слой (aiogram)
│   ├── routers/      # Один файл = один домен (start, consultation, chart...)
│   ├── middlewares/  # db_session, user, tracing
│   ├── keyboards/    # inline клавиатуры
│   ├── states.py     # Все FSM состояния в одном файле
│   ├── filters.py    # Magic filters
│   ├── config.py     # Pydantic Settings
│   └── main.py       # Entry point
├── calculator/       # Бизнес-логика Бацзы (stateless, без зависимостей от bot/db)
├── ai/               # AI оркестрация (без зависимостей от bot/)
│   ├── prompts/      # .md файлы системных промптов
│   └── ...
├── knowledge/        # KuzuDB граф знаний
│   ├── schema.py     # Схема узлов и рёбер
│   └── ingest/       # Скрипты оцифровки
├── db/               # Только SQLAlchemy модели + репозитории
│   └── repositories/ # Один файл = один агрегат
├── web/              # FastAPI (только для Admin + будущий Mini App)
├── tasks/            # TaskIQ воркеры
├── monitoring/       # Langfuse helpers
├── migrations/       # Alembic (не редактировать вручную)
├── assets/
│   └── hieroglyphs/  # 24 PNG-ассета иероглифов
├── tests/
│   ├── unit/
│   └── integration/
└── .github/workflows/
```

### Правила кода

- **Макс. длина функции:** 40 строк. Длиннее — выносить в вспомогательную функцию.
- **Макс. длина файла:** 300 строк. Длиннее — разбить на модули.
- **Строгая типизация:** все функции с type hints. `mypy --strict` должен проходить.
- **Async всё:** все I/O операции (БД, Redis, HTTP, AI) — async/await.
- **Запрет `!`:** в строках ответов Анастасии (валидировать в тестах).
- **Нет магических чисел:** вынести в константы или Settings.
- **Импорты:** stdlib → third-party → local (ruff автоматически сортирует).

### Обработка ошибок

- Кастомные исключения в `{module}/exceptions.py` (наследуются от `BaDziBaseError`).
- Логировать с контекстом: `logger.error("msg", exc_info=True, user_id=..., trace_id=...)`.
- Молчаливое глотание исключений (`except Exception: pass`) запрещено.
- Telegram handlers ловят исключения на уровне middleware — не в каждом хендлере.

### Репозитории (Database)

- Только через репозиторий — никаких прямых запросов к БД в роутерах.
- Метод = одна операция: `get_by_id`, `create`, `update_plan`, `count_today_questions`.
- Возвращают модели SQLAlchemy, не raw данные.

### Линтинг

```toml
[tool.ruff]
line-length = 100
target-version = "py311"

[tool.mypy]
strict = true
ignore_missing_imports = true
```

Pre-commit хуки: `ruff check --fix` → `ruff format` → `mypy` → secret scan.

### Тестирование

- Фреймворк: pytest + pytest-asyncio. Расположение: `tests/unit/{module}/test_{file}.py`.
- Нейминг тестов: `test_{что_тестируем}_{ожидаемое_поведение}`.
- Покрытие: Калькулятор 80%+ (детерминированный), Bot слой 60%+ (E2E для критических FSM), AI слой — mock OpenRouter (не тратить деньги на тесты).
- Запуск: `pytest --cov=calculator --cov=ai --cov-report=term-missing`.
- **TDD для `calculator/`:** Red (тест сначала, не проходит) → Green (минимальный код) → Refactor (улучшить, не ломая тест). Для `bot/` и `ai/`: тесты после реализации, mock внешних сервисов.

## Правила Git

Мигрировано из `.cursor/rules/workflow.mdc`.

### Ветки

```
main          ← защищённая, только через PR
feat/{name}   ← новая функция (feat/calculator-pillars)
fix/{name}    ← исправление бага (fix/fsm-date-validation)
docs/{name}   ← только документация
```

### Формат коммитов (Conventional Commits)

```
feat(calculator): add 4 pillars generation with 60-cycle
fix(bot): handle missing birth time in FSM
docs(vision): update monetization model
refactor(ai): extract temporal context to separate module
test(calculator): add TST calculation tests
```

Коммит после каждой закрытой задачи — не накапливать изменения.

### CI/CD

GitHub Actions на каждый push в main и каждый PR: `ruff check → ruff format --check → mypy → pytest --cov`. Деплой только если все шаги прошли.

</instructions>

<constraints>
- ⛔ Не писать бизнес-логику без прочтения 3 .mdc файлов
- ⛔ Не брать задачи не по порядку из tasks.md
- ⛔ Не делать коммит без прохождения lint + mypy + tests
- ⛔ Не менять архитектуру без обновления vision.mdc
- ⛔ Не мокировать Calculator в unit-тестах (он детерминирован — тестировать напрямую)
- ⛔ Не хардкодить secrets — только через Settings
- ⛔ Один вопрос за раз к пользователю
- ✅ При неясности — спросить, не угадывать
</constraints>

<output_format>
При анонсе задачи:
```
Задача 1.3.2: db/models.py — SQLAlchemy модели
План:
1. Создать модели User, Chart, Consultation, Subscription, Event
2. UUID primary keys, JSONB для chart_data
3. Async-совместимые отношения
4. ...
Начинаю? (Y/N)
```

При завершении:
```
✅ Задача 1.3.2 выполнена
📝 Коммит: feat(db): add SQLAlchemy models with UUID PKs
📋 tasks.md обновлён
```
</output_format>

<few_shot_examples>

### Пример старта задачи
```
Агент: Задача 1.6.5 (calculator/pillars.py — Генерация 4 столпов)
Plan:
1. ChartInput уже есть из 1.6.1
2. 60-ричный цикл: Heavenly Stems (10) × Earthly Branches (12) = 60 комбинаций
3. Год: от базового 甲子 (1984) ± n шагов
4. Месяц: от Цзе Ци определяем месячный столп
5. День: юлианский день → столп
6. Час: 12 двухчасовых периодов

Начинаю реализацию?
```

### Пример завершения
```
Агент: ✅ Задача 1.6.5 выполнена
- calculator/pillars.py создан (38 строк, mypy strict OK)
- tests/unit/test_calculator/test_pillars.py: 12 тестов, все зелёные
- Коммит: feat(calculator): add 4 pillars generation with 60-cycle
- tasks.md: [x] 1.6.5 отмечена
Следующая задача: 1.6.6 (hidden_stems.py). Начать?
```

</few_shot_examples>

---

## Граф знаний
Перед любым действием — прочитай `graphify-out/GRAPH_REPORT.md` (читаемый отчёт по god-нодам и связям).
Если `GRAPH_REPORT.md` отсутствует — запусти `/graphify` для его генерации.

## Prompt Caching
Перед проектированием системного промпта, message-массива, RAG-пайплайна или любой архитектуры запросов к LLM — **обязательно** прочитай скилл `~/.claude/skills/prompt-caching-playbook/SKILL.md`.

Норма cache hit rate: **80–90%**. Правило большого пальца: статика → в начало (tools → system → long context → history), динамика (timestamp / UUID / session_id / trace_id) → в самый конец, после последнего cache breakpoint. Никогда не помещай меняющиеся данные перед статическим контекстом.

Триггер на скилл: любой вопрос о cache hit rate, `cache_control`, `prompt_cache_key`, Context Caching API, cache TTL, "почему API дорого", "как уменьшить токены", cache miss, kv-cache, prefix matching.

## Память
- [2026-06-23] PATH C: проверена/домигрирована .cursor/rules в CLAUDE.md, AGENTS.md symlink, легаси удалён.
