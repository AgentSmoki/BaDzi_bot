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
- [~] **L-1 Эмодзи в SVG-карте** — **ОТМЕНЕНО (2026-06-10, решение Богдана)**: 3D-emoji-шрифт делать не будем. Белые SVG-иконки элементов остаются как штатный визуал.
- [ ] **L-2 Live-валидация Claude Sonnet.** После коммита `ff21ef2` проверить в Telegram: latency ~10с (вместо 55), баланс стихий цитируется дословно (15% Огня, не 40%), стиль Анастасии сохранился (тёплый, без `!`).

### 🟢 1.12.0 Минимальный free-question guard (защита от безлимитного жжения токенов)
- [x] **1.12.0** `User.free_question_used` флаг + проверка в `handle_question`: первый вопрос → флаг `True`, второй → заглушка «оплата подключается» через `pricing_kb`. **Зафиксировано в [bot/routers/consultation.py:241-255](bot/routers/consultation.py#L241-L255), admin-skip через `pricing:skip`.** Сделано до Wave 6.

### 🌊 1.17 Wave 6: AI Skill-Router (ADR-010) — Phase 0-6 закрыты 2026-05-19

- [x] **1.17.0 Phase 0** — prompt surgery + Qwen3-3B probe + 9-блочная база-интерпретация ([base.md](ai/prompts/base.md) 12 KB, 5×`ai/skills/*.md`, [base_interpretation.py](ai/base_interpretation.py) 6→9 блоков с follow-up «**Дальше можно спросить:**»). Пункты 8+9 Богдана. Commit `25f16c9`.
- [x] **1.17.1 Phase 1** — `ai/skills/` каталог + Pydantic SkillSpec/SkillSelection + frontmatter loader. 25 тестов. Commit `25f16c9`.
- [x] **1.17.2 Phase 2** — [ai/skill_router.py](ai/skill_router.py) `select_skill` (Qwen3.6 max_tokens=2000, JSON output, graceful fallback). [skill_router_system.md](ai/prompts/skill_router_system.md) с 6 few-shot. [orchestrator.py](ai/orchestrator.py) `chat` теперь принимает опц. `response_format`. 11 тестов. Commit `25f16c9`.
- [x] **1.17.3 Phase 3** — `charts.partner_chart_id` UUID NULL FK self (migration `5c7804a9c2c3`), `ChartRepository.set_partner`, [birth_data.handle_add_partner_chart](bot/routers/birth_data.py) entry + `mode="partner"` flow в `_calculate_and_persist`. 9 тестов. Commit `e95f200`.
- [x] **1.17.4 Phase 4** — `ConsultationState.collecting_clarifications` + [handle_clarification_answer](bot/routers/consultation.py) FSM loop. 6 тестов. Commit `fe5c0e7`.
- [x] **1.17.5 Phase 5** — [compose_messages](ai/temporal_context.py) расширен: `[PARTNER_CHART]`, `[SKILL: <name>]`, `[CLARIFICATIONS]` секции; `concept_hints` в [load_knowledge_for_question](ai/rag/public.py). 11 тестов, backward-compat. Commit `d987e76`.
- [x] **1.17.6 Phase 6** — wire-up в [consultation.py](bot/routers/consultation.py): `_continue_consultation_with_skill` extracted; `handle_question` 3 ветки (clarifying/partner/straight); `handle_partner_skip`; low-confidence downgrade; feature flag `skill_router_enabled`. +5 skill-router тестов, +6 рефактор clarifications, 9 регрессий. Commit `76819cd`.
- [x] **1.17.7 Phase 7** — deploy + verify (закрыто 2026-05-20 через Telegram MCP userbot):
  - [x] Wave 6 файлы уже задеплоены (Phase 0-6 коммиты + rsync), bot-image содержит всё. Local pytest 820/820 ✓
  - [x] Live Telegram smoke в `@EdoHa_Badzi_bot` под акк `@Bogman108` через MCP `telegram`: **5/6 кейсов ✅, 1 регрессия** ↓
    - Кейс 1 work ✅ — `skill=work, conf=0.92, concept_hints=6`, latency 17.3s
    - Кейс 2 relationships ⚠️ — `skill=relationships, conf=0.95`, clarifying loop сработал, **но `partner:add` кнопка не показана** несмотря на `needs_partner_chart=true` → см. **1.17.9 regression** ниже
    - Кейс 3 health ✅ — `skill=health, conf=0.9`, ТКМ-методология (Огонь→сердце, Земля→ЖКТ)
    - Кейс 4 time ✅ — `skill=time, conf=0.95`, годовой столп 丙午, такт 庚午, резонансы натала с текущим моментом
    - Кейс 5 clarifying ✅ — FSM `collecting_clarifications` работает (`clarifications_requested` → `clarifications.collected` события), проверено в рамках Кейсов 2,4,6
    - Кейс 6 default ✅ — router сам уверенно выбрал default (conf 0.9) для философского «В чём смысл судьбы?»; downgrade-механизм не активирован, потому что router и так корректно маршрутизирует
  - **3 hotfix-а в процессе Phase 7** (skill-router был сломан в проде):
    1. `ai/skill_router.py` теперь строит полный `gpt://<folder>/<model>/latest` URI вместо короткого имени модели (YC `/v1/chat/completions` ругался «Failed to parse model URI» на короткое имя — main LLM через `ai.fallback._build_model_id` всегда так и делал, но skill router делал по-старому)
    2. Убран `response_format={"type":"json_object"}` из skill router (YC отвергает; JSON enforce через system prompt + `_extract_json` regex)
    3. `yc_fast_max_tokens` default 2000→**4000** (thinking model съедала весь бюджет на `reasoning_content` → finish_reason=length; на live router тратил ~1949 токенов на reasoning, 4000 = ~3000 reasoning headroom + 1000 на JSON; unused budget не биллится)
  - [ ] Optional: `/graphify . --update` для пересборки семантического графа после fixes

- [x] **1.17.10 UX bug: smart-entry экран без выхода в меню** (закрыт 2026-05-20 после report от @S_Kate2011)
  - **Симптом:** при нажатии «Добавить новую карту» (`menu:calc`) бот шёл в FSM `BirthDataForm.waiting_full_text` и показывал promp «Напишите данные рождения в одной строке…» с **единственной кнопкой «Ввести по шагам»**. Юзер не мог вернуться в меню без ввода данных или `/start`.
  - **Fix:** [bot/keyboards/__init__.py::calc_intro_kb](bot/keyboards/__init__.py) — добавлена кнопка «В меню» (`menu:back`). `handle_menu_back` в start.py уже сбрасывает FSM state и шлёт main menu, fix сводится к двум строкам в keyboard builder. Live-verified через MCP: prompt теперь показывает 2 кнопки, «В меню» возвращает в `С возвращением, Богдан...`.
  - **Reproduction & fix log:** воспроизведено через @Bogman108 (нажатие «Добавить новую карту» → засветился bug со скриншота Кати) → edit `calc_intro_kb` → rsync + rebuild bot → re-test ✓.

- [x] **1.17.9a Regression: partner:add кнопка не показывается после clarifying** (закрыт 2026-05-20)
  - **Корневая причина:** `handle_question` Branch 1 (clarifying-questions) сохранял в FSM `clarifying_questions`/`answers`/`skill`/`concept_hints`/`original_question`/`chart_id`, но НЕ `needs_partner_chart`. `handle_clarification_answer` после сбора ответов терял этот флаг и шёл сразу в main LLM (минуя Branch 2 = partner_chart_kb).
  - **Fix (3 точки в [bot/routers/consultation.py](bot/routers/consultation.py)):**
    1. `handle_question` Branch 1: добавлено `needs_partner_chart=bool(skill_sel.needs_partner_chart)` в `state.update_data`.
    2. `handle_clarification_answer`: после сбора всех ответов проверяется флаг. Если `True` и `chart.partner_chart_id is None` — pre-staging данных (`pending_question`/`pending_skill`/`pending_concept_hints`/`pending_clarifications`/`chart_id`) + показ `add_partner_chart_kb`. Новый log event `consultation.partner_chart_requested_after_clarifications`.
    3. `handle_partner_skip`: читает `pending_clarifications` и пробрасывает в `_continue_consultation_with_skill(... clarifications=clarifications)` — собранные ответы не теряются при skip.
  - **Live-verified через MCP 2026-05-20:** relationships-вопрос → 3 clarifying → ответы → бот показал «Добавить карту партнёра / Ответить без неё» → tap skip → Анастасия отвечает с relationships skill и явно использует контекст clarifications («Сейчас, живя вместе, вы как раз на этапе, когда эти границы можно закрепить»).

- [x] **1.17.9b Auto-resume после успешного `partner:add`** (закрыт 2026-05-20, commit `063b331`)
  - Новый public helper `bot/routers/consultation.py::resume_after_partner_added` + wire-up в `bot/routers/birth_data.py::handle_confirm_calc` (partner-mode branch). После set_partner бот сразу продолжает диалог с partner_chart в `[PARTNER_CHART]` секции, юзеру не нужно заново задавать вопрос. `handle_add_partner_chart` теперь сохраняет `pending_skill/concept_hints/clarifications` (раньше терялись через `state.set_data`). `callback.answer()` перенесён ДО долгого LLM-вызова чтобы не словить «query is too old».

- [x] **1.17.11 Partner-chart selector + rename + long-message split** (закрыт 2026-05-20)
  - **A — Partner selector** ([bot/keyboards/__init__.py::partner_chart_selector_kb](bot/keyboards/__init__.py)): когда у юзера уже есть OTHER карты в библиотеке, при relationships-вопросе бот сначала предлагает их как кандидатов («Татьяна Тестовая / Женя Видеограф Вайшнав») вместо сразу partner FSM. Tap → `set_partner` + auto-resume через новый `partner:use:*` handler. Fallback на старый add/skip когда других карт нет.
  - **B — Partner auto-save в Мои карты** (verified, уже работало через `_chart_repo.create(user_id=user.id, name="Партнёр")` + `list_unique_by_user`).
  - **C — Rename chart** ([bot/keyboards/__init__.py::chart_actions_kb](bot/keyboards/__init__.py) + new handler `chart:rename:*` в [bot/routers/start.py](bot/routers/start.py)): кнопка «✏️ Переименовать» в карточке. Reuse existing `BirthDataForm.naming` state + `handle_naming_input` который уже умеет обновлять имя через `update_name`.
  - **Bonus — Split long messages** ([bot/routers/consultation.py::_split_for_telegram](bot/routers/consultation.py)): ответы с partner-comparison + clarifications часто > 4096 chars → Telegram 400 «message is too long» → exception → rollback всей session_scope (включая set_partner). Теперь split на paragraph boundaries, kb attached only to last chunk.
  - **Live-verified через MCP:** /start → «Добавить новую карту» (smart-entry fallback to classic FSM) → calc → rename → relationships question → selector с 2 кандидатами → выбор «Татьяна Тестовая» → auto-resume с полным сравнением столпов (卯/巳 родство порождения, 癸酉/丙午 разные акценты, баланс обоих partner'ов). DB: `partner_chart_id=cb22692f` committed.

### 🔮 Wave 6 backlog (после деплоя)

- [ ] **1.17.8 Qwen3-3B миграция** (бывший 1.9.17) — когда модель появится в YC каталоге, swap `settings.yc_fast_model` + проверить JSON-output mode. Дешевле в 5× и быстрее на 1-1.5 сек.

### 🌊 Wave 7 — Переработка Анастасии: 3 школы + алгоритмы мышления (ADR-011)

> **Контекст:** разбор сенсея 2026-05-21 показал что Анастасия даёт поверхностные ответы (видит одно 六冲, пропускает 3-vs-1 паттерн). Архитектурное решение Богдана: три параллельных версии Анастасии — Классическая / Мастер ЭдоХа / Современная — с inline-выбором в начале каждой консультации. Алгоритмы мышления (chain-of-thought) встроены в школу ЭдоХа. Полный план: `~/.claude/plans/misty-enchanting-parnas.md` (часть 2).

#### Phase 1 — Quick wins по формату ответа (закрыт 2026-05-22)

- [x] **1.18.0 Phase 1** — нарратив вместо raw dump + расшифровка иероглифов inline + HTML-bold + 4-5 эмодзи. Коммиты `0ad9d29` + `09c02e8`:
  - HTML конверсия `**X**` → `<b>X</b>` ([bot/routers/consultation.py::_markdown_to_html](bot/routers/consultation.py))
  - Запрет на bullet-dump аналитики в [INSTRUCTION_PREFIX](ai/prompts/__init__.py) — «Что я вижу в вашей карте» теперь 2-3 абзаца нарративом
  - Правило inline-расшифровки иероглифов в [base.md](ai/prompts/base.md): формат `<b>иероглиф</b> (русский перевод)`, без 「」
  - Эмодзи бюджет 1-2 → 4-5 indicating
  - Live-verified через MCP: вопрос «какая моя главная сильная сторона?» → нарратив, иероглифы все расшифрованы, 5 эмодзи

#### Phase 4 (pre-проект) — Драфты алгоритмов мышления

> Сначала пишем 6 markdown-драфтов в `ai/prompts/algorithms/`, показываем Богдану, итерируем. Не интегрируем в код в этой фазе — это документы для согласования.

- [x] **1.18.1 risk_assessment.md** — 3-vs-1 паттерн для опасных периодов (commit `0ad9d29`). Полный разбор на эталонной карте Богдана (март 2026 — реальная катастрофа, не май). После Option X (commit `03502bc`) живёт в [`ai/prompts/algorithms/risk_assessment.md`](ai/prompts/algorithms/risk_assessment.md) как драфт + конкретный алгоритм перенесён в [`ai/prompts/base_edoha.md`](ai/prompts/base_edoha.md). Skill [`ai/skills/risk.md`](ai/skills/risk.md) теперь школо-нейтральный дисциплинатор («ЧТО анализировать + КАК форматировать»).
- [x] **1.18.2 opportunity_window.md** (драфт готов 2026-05-24, runtime-integration на ревью сенсея) — благоприятные периоды через 三合 + 桃花 + благородные звёзды → [`ai/prompts/algorithms/opportunity_window.md`](ai/prompts/algorithms/opportunity_window.md)
- [x] **1.18.3 relationships_match.md** (драфт готов 2026-05-24, runtime-integration на ревью сенсея) — сравнение двух карт: столпы дня + Дворец Супруга + 六合 vs 六冲 → [`ai/prompts/algorithms/relationships_match.md`](ai/prompts/algorithms/relationships_match.md)
- [x] **1.18.4 career_alignment.md** (драфт готов 2026-05-24, runtime-integration на ревью сенсея) — какая работа подходит: 偏官/正官 на месяце + Полезное Божество + талант (食神/伤官) → [`ai/prompts/algorithms/career_alignment.md`](ai/prompts/algorithms/career_alignment.md)
- [x] **1.18.5 decision_chain.md** (драфт готов 2026-05-24, runtime-integration на ревью сенсея) — «делать X или Y?»: шахматная аналогия, оценка позиций обеих сторон, расчёт ходов → [`ai/prompts/algorithms/decision_chain.md`](ai/prompts/algorithms/decision_chain.md)
- [x] **1.18.6 health_diagnostics.md** (драфт готов 2026-05-24, runtime-integration на ревью сенсея) — баланс стихий → ТКМ-системы → ослабленный / гипер орган → [`ai/prompts/algorithms/health_diagnostics.md`](ai/prompts/algorithms/health_diagnostics.md)
- [x] **1.18.7 term_unpack.md** (драфт готов 2026-05-24, runtime-integration на ревью сенсея) — мета-алгоритм: при незнакомом термине остановись, расшифруй, потом продолжай → [`ai/prompts/algorithms/term_unpack.md`](ai/prompts/algorithms/term_unpack.md)
- [x] **1.18.8 Sensei review 6 драфтов** — **ЗАКРЫТ 2026-06-10 (5 из 6 + решение по #6).** Ревью мастера состоялось 2026-05-31, правки применены к 5 алгоритмам (opportunity/relationships/career/decision/health) в commit `f43d3dd` (Phase 9 / 1.18.80). Integration option выбран: гибрид A+B — нейтральное аналитическое ядро → `ai/skills/*.md` (видят все школы через [SKILL]), голос/доктрина ЭдоХи → `base_edoha.md`. Драфты `algorithms/*.md` остаются canonical reference.
  - **#6 term_unpack — закрыт БЕЗ ревью сенсея (решение 2026-06-10):** это UX-правило подачи (источник — фидбэк Богдана, не доктрина школы), и его суть уже live в трёх местах: правило inline-расшифровки в [base.md](ai/prompts/base.md) («Голый иероглиф без расшифровки — критическая ошибка»), INSTRUCTION_PREFIX в [ai/prompts/__init__.py](ai/prompts/__init__.py), «Алгоритм расшифровки термина (4 шага)» в [base_modern.md](ai/prompts/base_modern.md). Ревьюить мастеру там нечего — астрологического содержания нет. Если Богдан захочет формальное ревью — написать 6-й промпт в `doc/algorithm_review_prompts.md` по шаблону (сейчас там только 5).

#### Phase 2 — Три версии base.md + UX выбор школы

- [x] **1.18.10 base_classic.md** (закрыт 2026-05-23, commit `aa3a4d6`) — школа Yuan Hai Zi Ping / Раймонд Ло. Структурный анализ через 10 Богов, 25 格局, сила Дневного Мастера, Полезное Божество. После Option X добавлена секция «# Алгоритм оценки рисков» (六冲 + 三刑) → [`ai/prompts/base_classic.md`](ai/prompts/base_classic.md)
- [x] **1.18.11 base_edoha.md** (закрыт 2026-05-23, commit `aa3a4d6`) — школа мастера ЭдоХа. Embedded 3-vs-1 алгоритм (после Option X). Метафоры обязательны. → [`ai/prompts/base_edoha.md`](ai/prompts/base_edoha.md)
- [x] **1.18.12 base_modern.md** (закрыт 2026-05-23, commit `aa3a4d6`) — синтез нескольких школ + язык психологии. После Option X добавлена секция «# Алгоритм оценки рисков» (growth zones). → [`ai/prompts/base_modern.md`](ai/prompts/base_modern.md)
- [x] **1.18.13 UX выбор школы** (закрыт 2026-05-23, commit `aa3a4d6` + hotfix `dfb857e` для `_safe_load_skill` whitelist):
  - `ConsultationState.choosing_school` в [bot/states.py](bot/states.py) ✓
  - `school_selector_kb()` в [bot/keyboards/__init__.py](bot/keyboards/__init__.py) ✓
  - `handle_school_chosen` callback в [bot/routers/consultation.py](bot/routers/consultation.py) ✓
  - `_continue_consultation_with_skill(chosen_school=...)` прокидывает school в [compose_messages](ai/temporal_context.py) ✓
  - `load_base_prompt(school: SchoolName | None)` с `lru_cache` per school в [ai/prompts/__init__.py](ai/prompts/__init__.py) ✓
  - **Hotfix `dfb857e`**: `_safe_load_skill` использовал hardcoded whitelist без `"risk"` → router выбирал risk (conf 0.95), а loader тихо downgrade'ил до default → все 3 школы давали одинаковые ответы. Исправлено через `valid = set(get_args(SkillName))`.
- [x] **1.18.14 Опция «запомнить выбор»** (закрыт 2026-06-02) — `Chart.default_school` NULLABLE (migration `b2c3d4e5f6a7`). Кнопка «⚙️ Школа по умолчанию» в меню карты ([default_school_kb](bot/keyboards/__init__.py) + handlers `chart:defschool`/`defschool:set`/`defschool:clear` в [start.py](bot/routers/start.py)). Консультация и покупка прогноза пропускают селектор школы если дефолт задан. Тесты: repo set/clear + skip-селектора.
- [x] **1.18.15 Phase 2 live-verify через MCP** (закрыт 2026-05-23) — через @Bogman108 → @EdoHa_Badzi_bot задан вопрос «какой опасный месяц 2026?» на трёх школах. После hotfix `dfb857e` все три школы дают разные ответы (edoha — март/3-vs-1, classic — структурный 六冲, modern — psychology overlay). Подтверждено в логах VM (`grep KNOWLEDGE` + structlog `rag.retrieve.*`).

#### Phase 5 — Knowledge base разметка по школам + Edoha KB

- [x] **1.18.20 KB разметка** (закрыт 2026-05-23) — frontmatter `school: classic | edoha | modern | universal` во всех 46 teacher-docs через [scripts/tag_teacher_school.py](scripts/tag_teacher_school.py). Распределение: 14 classic + 32 universal + 0 modern. Parser ([knowledge/ingest/parser.py](knowledge/ingest/parser.py)) читает `school:`, writer ([knowledge/ingest/writer.py](knowledge/ingest/writer.py)) пишет в `n.school`, schema ([knowledge/schema.py](knowledge/schema.py)) добавила колонку через `MIGRATION_DDL` + `ALTER TABLE Node ADD school STRING DEFAULT 'universal'`.
- [x] **1.18.21 RAG retrieve фильтрация** (закрыт 2026-05-23) — [ai/rag/retrieve.py](ai/rag/retrieve.py) принимает `school: SchoolFilter | None`, фильтрует через `_school_clause()` → `WHERE n.school IS NULL OR n.school IN ['universal', $school]`. Прокинуто в `retrieve_nodes / concept_hits / title_hits / expand_neighbours`. [load_knowledge_for_question](ai/rag/public.py) и [compose_messages](ai/temporal_context.py) передают school из `_continue_consultation_with_skill`.
- [x] **1.18.22 Edoha KB expansion (закрыт 2026-05-24)** — вместо single sensei-транскрипта импортирован ВЕСЬ Digital Twin Мастера из `/Users/admin/Documents/Razarabotka/EdoHa` (7742 узла из 298 YouTube-транскриптов + 4 PDF + 20 курсов). 2-фазный pipeline ([scripts/edoha_export_json.py](scripts/edoha_export_json.py) через EdoHa venv kuzu 0.11.3 → JSONL → [scripts/import_edoha_kuzu.py](scripts/import_edoha_kuzu.py) через BaDzi venv kuzu 0.10 → 7742 nodes + 7850 edges). Маппинг: Manifesto/Quote/Fact (212+112+788) → L8 auth 9-10, MentalModel/CausalBelief/Document (808+1595+537) → L7 auth 8-9, Relation/StyleMarker (539+3151) → L6 auth 7-8. Все с `school='edoha'`, id-префикс `edoha:<type>:<original_pk>`. Highlights ~524 .md в [`База/edoha/highlights/`](База/edoha/highlights/) для git-видимости через [scripts/export_edoha_to_md.py](scripts/export_edoha_to_md.py). RAG smoke: edoha-вопрос возвращает 11 KB цитат мастера (vs 0 раньше). Pytest 871/871 ✓. Полная сессия — в MASTER.md «Сессия 2026-05-24».
- [ ] **1.18.23 Self-improvement loop** (отложить) — кнопки «👍 / 👎 / ✏️» под каждым ответом, накопление feedback'ов в KB с `school: <выбранная>`.
- [x] **1.18.24 Phase 5 live-verify** (закрыт 2026-05-24) — edoha-вопрос про опасные периоды → `[KNOWLEDGE]` блок содержит цитаты сенсея про 3-vs-1 (≈11 KB цитат, фигурируют `edoha:fact:*` / `edoha:manifesto:*` IDs); classic-вопрос на тот же запрос → `[KNOWLEDGE]` без edoha-материалов (структурный 六冲 из teacher-KB). Подтверждено через MCP @Bogman108 + `grep KNOWLEDGE` в логах VM.

#### Phase E — Unsplash hero image в прогнозе (закрыт 2026-05-24, commit `a3abadc`)

- [x] **1.18.30 day_image hero** — [ai/day_image.py](ai/day_image.py): YC fast LLM генерирует Unsplash query из энергии дня → API `/photos/random` отдаёт фото 1080×1920 → URL в кэше + в первой части блок-сообщения forecast'а. `unsplash_application_id/access_key/secret_key` в `bot/config.py`. Hotfix YC URI 400 (короткое имя модели → нужен `gpt://{folder}/{model}/latest`). Деплой на VM: `scp` ключей фрагментом + `docker compose up -d --force-recreate` (restart не перечитывает env_file → новая запись в [feedback memory](.claude/projects/.../feedback_env_keys_to_vm.md)).

#### Phase 3.5 — LLM concept extraction для RAG (закрыт 2026-05-24)

- [x] **1.18.31 ai/rag/llm_extract** — [ai/rag/llm_extract.py](ai/rag/llm_extract.py) выделяет concept-hints из вопроса пользователя через fast LLM. `ConceptCache(Redis)` с sha256-ключом + 24h TTL для дедупликации. Graceful fallback на пустой список при ошибке LLM. 15 тестов в [tests/unit/test_ai/test_rag/test_llm_extract.py](tests/unit/test_ai/test_rag/test_llm_extract.py). `close_concept_cache` в `_shutdown` ([bot/main.py](bot/main.py)).

#### Option X — Школо-нейтральный risk skill (закрыт 2026-05-24, commit `03502bc`)

- [x] **1.18.32 risk skill neutralization** — [ai/skills/risk.md](ai/skills/risk.md) переписан как дисциплинатор («ЧТО анализировать (карта рождения / приходящие столпы / смягчающие факторы) + КАК форматировать ответ»). Конкретный 3-vs-1 алгоритм переехал в [`ai/prompts/base_edoha.md`](ai/prompts/base_edoha.md) как секция «# Алгоритм оценки рисков». Аналогичные секции в `base_classic.md` (六冲 + 三刑) и `base_modern.md` (growth zones). Архитектурный разбор в [`doc/school_layered_flow.md`](doc/school_layered_flow.md).
- [x] **1.18.33 SkillName extension** — [ai/skills/models.py](ai/skills/models.py): `SkillName = Literal["work","relationships","health","time","risk","default"]`. [ai/skills/loader.py](ai/skills/loader.py) автоматически использует `get_args(SkillName)` вместо hardcoded списка.

#### UX «3 бесплатных вопроса» (закрыт 2026-05-24, commit `85269d1`)

- [x] **1.18.40 free_questions counter** — миграция [migrations/versions/20260524_4af483b51b7e_free_questions_used_as_counter_wave_7_ux.py](migrations/versions/20260524_4af483b51b7e_free_questions_used_as_counter_wave_7_ux.py): `free_question_used: bool` → `free_questions_used: int` с backfill (True→3, False→0). `free_questions_limit: int = 3` в [bot/config.py](bot/config.py).
- [x] **1.18.41 footer + auto-resume** — [bot/routers/consultation.py](bot/routers/consultation.py) добавляет `_remaining_footer()` («осталось N/3 бесплатных запросов») после каждого ответа. `handle_pricing_skip` больше не admin-only. Кнопки оплаты неактивные (`pay:disabled:*` callback) после исчерпания лимита. `handle_payment_disabled` отвечает «оплата временно недоступна». Auto-resume сохраняет вопрос: после нажатия «Пропустить» бот отвечает на ранее заданный вопрос без повторного ввода.

#### Phase 6 — Architecture documentation (закрыт 2026-05-24)

- [x] **1.18.50 doc/school_layered_flow.md** — карта где каждый .md загружается, 2 touchpoints (base overlay + RAG school-filter), integration options A/B/C/D для 6 алгоритмов. [`doc/school_layered_flow.md`](doc/school_layered_flow.md).
- [x] **1.18.51 doc/algorithm_review_prompts.md** — 6 review-промптов с критериями для сенсея. [`doc/algorithm_review_prompts.md`](doc/algorithm_review_prompts.md).

#### Phase 7 — UX полировка покупок и follow-up (закрыт 2026-05-26)

> Серия live-fix'ов по результатам прогона с реальным клиентом (@S_Kate2011) и тестов Богдана через @Bogman108. Главное: убрать слово «натал», поправить скип цен с потерей вопроса, доставить первый weekly-прогноз без ожидания scheduler-loop, сделать follow-up tap-to-copy с двумя кнопками.

- [x] **1.18.60 6 UX правок** (commit `fee7710`):
  - **Pricing-skip пропадал** — `handle_pricing_skip` иногда терял FSM-данные → Redis-fallback через `HistoryStore.stash_pending_question` / `pop_pending_question` (GETDEL, TTL 1ч). См. [ai/context.py:130-152](ai/context.py#L130-L152).
  - **Даты в прошлом для @S_Kate2011** — добавлен `[TODAY: <iso>]` маркер в system-prompt + правило «не предлагай прошедшие даты» в [base.md](ai/prompts/base.md).
  - **Месячный прогноз приходил фото-без-текста** — Telegram caption cap 4096. Размер блоков сокращён (daily 50-120 / monthly 60-130 слов) + `split_for_telegram` в `_send_or_record_error`.
  - **Замена «натал» → «карта Ба Цзы»** во всех 8 источниках (анастасия, INSTRUCTION_PREFIX, base.md, journal.py, baihu_white_tiger.md, anastasia_v2.md, risk_assessment.md). Локальный re-ingest kuzu + `docker compose cp` на VM.
  - **Образы животных в edoha** — анимал-метафоры с leading questions в [base_edoha.md](ai/prompts/base_edoha.md).
  - **Follow-up подчёркнут** — формат «Чтобы узнать больше, задайте вопрос по этой карте: …» с `<u>…</u>` обёрткой в [INSTRUCTION_PREFIX](ai/prompts/__init__.py).

- [x] **1.18.61 Абсолютный запрет «натал»** (commit `c42233f`):
  - Усиленная формулировка в [base.md](ai/prompts/base.md) + INSTRUCTION_PREFIX с явной replacement-таблицей (`натал → карта Ба Цзы`, `в натале → в карте`, `натальный → карты Ба Цзы`).
  - `partner_chart` UI добавлен для skill=`work` (бизнес-партнёрство, соучредители) — был только для relationships.

- [x] **1.18.62 First-week inline kick + анимация + follow-up tap-to-copy** (commits `909e6ec` + `f1142c3` + `a544697`):
  - **Первый месячный weekly не доходил** — APScheduler стартовал >1ч после `sub.create`, guard `fire_at < now-1h` тихо пропускал week=1. Inline kick через `asyncio.create_task(_kick_first_delivery)` + 60с sleep + `send_monthly_forecast_job(week=1)`. Модуль-global `_kick_tasks: set[asyncio.Task]` против GC-collection. 3 unit-теста в [tests/unit/test_bot/test_forecast_handlers.py](tests/unit/test_bot/test_forecast_handlers.py).
  - **Анимация ожидания LLM** — placeholder-message со сменяющимся текстом «🕯 Зажигаю свечу… 🌌 Смотрю на небо… 📜 Читаю карту…» каждые ~3с пока LLM генерирует ответ. После доставки — `delete_message` placeholder'а с `except (TelegramBadRequest, TypeError)` для MagicMock в тестах.
  - **Suggested follow-up UI** — Анастасия выдаёт follow-up в `<code>…</code>` (tap-to-copy на iOS/Android) + 2 кнопки: `⬆️ Задать предложенный вопрос` (Redis stash через `stash_suggested_followup`/`pop_suggested_followup`, TTL 1ч) и `🔄 Задать другой вопрос` (переименовано из «Задать ещё вопрос» по запросу Богдана). См. [ai/context.py:154-179](ai/context.py#L154-L179).

#### Phase 8 — Forecast school selection + relationships UX + history-leak (закрыт 2026-05-30, commit `69e79a8`)

> Три проблемы, выявленные в проде 2026-05-26: прогнозы (daily/monthly) шли в нейтральном голосе без выбора школы; skill-router для `relationships` спрашивал данные партнёра текстом вместо немедленного UI; HistoryStore карусель имён («Сергей» из предыдущего диалога утекал в новый). Полный план: [`~/.claude/plans/1-smooth-adleman.md`](../../../.claude/plans/1-smooth-adleman.md).

- [x] **1.18.70 Выбор школы при покупке прогнозов** — каскад FSM-шагов `fc:bm → fc:mc:<delivery> → fc:ms:<school>` для месячного и `fc:bd → fc:dc:<hour> → fc:ds:<school>` для дневного. Migration `20260526_a1b2c3d4e5f6_add_chosen_school_to_forecast_sub.py` (колонка `chosen_school VARCHAR(16) NOT NULL DEFAULT 'classic'`). `ChartForecastSubscription.chosen_school` в [db/models.py](db/models.py); `chosen_school` kwarg в [forecast_repo.py::create](db/repositories/forecast_repo.py); `school_selector_kb(callback_prefix=...)` параметризован для reuse трёх контекстов (consultation / `fc:ms` / `fc:ds`); 2-шаговые handlers `handle_monthly_school_confirm` + `handle_daily_school_confirm` в [bot/routers/forecast.py](bot/routers/forecast.py) с inline kick первой недели. `_build_system_prompt(school)` + `generate_*_forecast(*, school=None)` в [ai/forecast.py](ai/forecast.py); `_school_from_sub` хелпер с whitelist валидацией в [bot/scheduler/jobs.py](bot/scheduler/jobs.py). 8 unit-тестов переписаны на новый 2-шаговый flow.

- [x] **1.18.71 Relationships — ранний skip clarifying loop** — в [bot/routers/consultation.py::_process_question_after_guards](bot/routers/consultation.py) добавлена **Branch 0** ДО clarifying-loop:
  ```python
  if (effective_skill == "relationships"
      and skill_sel.needs_partner_chart
      and chart.partner_chart_id is None):
      await state.update_data(pending_question=question, ...)
      partner_kb = await _partner_kb_for_user(...)
      await message.answer(_PARTNER_REQUEST_MSG, reply_markup=partner_kb)
      return
  ```
  Применяется ТОЛЬКО к `relationships` — для `work` (бизнес-партнёрство) сохраняется clarifying loop, потому что вопросы типа «на каком этапе переговоры» НЕ дублируют partner card data. Live-verified MCP: `consultation.partner_chart_requested_early_skip_clarifying skill=relationships clarifying_count=0`.

- [x] **1.18.72 Smart history-reset при смене skill** — устранена утечка имён между темами. Новые методы `get_last_skill`/`set_last_skill`/`clear_last_skill` в [ai/context.py::HistoryStore](ai/context.py#L181-L210) поверх Redis key `chat:{user_id}:last_skill` (TTL = `HISTORY_TTL_SECONDS`). В consultation pipeline ПОСЛЕ `select_skill`:
  ```python
  if last_skill and last_skill != effective_skill:
      await history_store.clear(user.telegram_id)
      await history_store.clear_last_skill(user.telegram_id)
      history = []
  ```
  После успешного `append` — `set_last_skill(skill_spec.name)`. Live-verified MCP: `consultation.history_cleared_on_skill_change old_skill=relationships new_skill=health`.

- [x] **1.18.73 Hour pillar TST vs mingli — методологическая заметка** — клиент обнаружил расхождение (наш `癸巳` Змея vs mingli `甲午` Лошадь для 25.07.1988 12:00 Волжский). Это **не баг**: наш расчёт классически корректный (True Solar Time с longitude + Equation of Time), mingli использует упрощённое локальное время. Решение Богдана — TST остаётся как сейчас. Добавлена секция «Известные методологические особенности → Hour pillar — TST vs local clock» в MASTER.md для будущих сессий.

#### Phase 9 — алгоритмы мастера во все школы + default_school + ЮKassa (закрыт 2026-06-02)

- [x] **1.18.80 Алгоритмы мастера → все школы** — ревью мастера ([doc/algorithm_review_prompts.md](doc/algorithm_review_prompts.md)) применено к 5 алгоритмам (opportunity/relationships/career/decision/health; #6 term_unpack пропущен). Нейтральное ядро → `ai/skills/*.md` (видят все школы через [SKILL]), голос/доктрина ЭдоХи → [base_edoha.md](ai/prompts/base_edoha.md). Новый skill `decision` + SkillName + router catalog. Драфты algorithms/*.md = canonical reference. Тесты: 7 skills, decision школо-нейтрален.
- [x] **1.18.14 default_school** (см. выше).
- [x] **1.18.81 ЮKassa оплата** — нативные Telegram-платежи (ЮKassa провайдер), без webhook. Прогнозы 500/900 ₽ + вопросы 290/990/2490 ₽. `payments_live` gate (токен + не bypass), [bot/services/payments.py](bot/services/payments.py) + [bot/routers/payments.py](bot/routers/payments.py) (pre_checkout + successful_payment), `payment_id` в обеих моделях подписок (migration `c3d4e5f6a7b8`). Forecast default-school pre-fill. Тесты: 11 payments + адаптированы 5 forecast. **Что нужно от Богдана:** provider-токен из @BotFather (ЮKassa) в `.env` на VM + `FORECAST_FREE_BYPASS=false`.

#### Что НЕ в Wave 7

- 3D эмодзи в SVG-карте (L-1)
- KuzuDB → Apache AGE migration — **ОТМЕНЕНО** (остаёмся на 0.10, см. 1.9.15)
- bge-m3 embeddings — готовое предложение [doc/proposals/bge_m3_embeddings.md](doc/proposals/bge_m3_embeddings.md), к запуску по решению
- A/B тестирование школ — после стабилизации Phase 5

### 🌊 Wave 1 (closed 2026-05-19, commit `57c8973`, LIVE)

- [x] **W1a Парсинг дат** — `_parse_birth_date` принимает ISO (`1990-05-15`), 2-digit год (cutoff 30: `27.04.88` → 1988; `15.06.15` → 2015), packed ddmmyy и dd-mm-yy слитно. 24 теста.
- [x] **W1b Удаление карт** — `ChartRepository.delete`, кнопка 🗑 «Удалить карту» в `chart_actions_kb`/`chart_actions_kb_post_interpret`, confirm dialog `chart_delete_confirm_kb`. Server-side ownership check. 10 тестов.

### 🌊 Wave 2 (closed 2026-05-19, commit `1e4ee18`, LIVE)

- [x] **W2 Smart-entry** — `ai/text_extract.extract_birth_data` (fast LLM, JSON, graceful fallback), `BirthDataForm.waiting_full_text`, [handle_full_text](bot/routers/birth_data.py) → `_route_to_first_missing_step`. Кнопка «Ввести по шагам» для escape на классический FSM. 19 тестов.

### 🌊 Wave 3 — платные прогнозы (closed 2026-05-26, LIVE; school selection добавлен в Wave 7 Phase 8)

**Архитектурное решение (research 2026-05-19, Dev_Architect/research_tool):** APScheduler `AsyncIOScheduler` + `SQLAlchemyJobStore` на Postgres, отдельный Docker-сервис `scheduler`.

- [x] **W3a DB + repo** — `ChartForecastSubscription` + `ForecastDelivery` модели, migration `776d382ae50d`, `ChartForecastSubscriptionRepository` + `ForecastDeliveryRepository`. Settings: `forecast_free_bypass=True`, `forecast_monthly_price_rub=500`, `forecast_daily_price_rub=900`, `forecast_daily_default_hour_local=4`, `forecast_period_days=30`. Колонка `chosen_school` добавлена в `20260526_a1b2c3d4e5f6` (Wave 7 Phase 8).
- [x] **W3b Forecast generator** — [ai/forecast.py](ai/forecast.py): `generate_monthly_forecast(*, chart, period_start, trace_id, school=None)` / `generate_daily_forecast(*, chart, target_date, trace_id, school=None)`. Блочный LLM-текст (4-6 блоков). Hotfix: размеры блоков уменьшены (daily 50-120, monthly 60-130 слов) из-за Telegram 4096 cap; используется `split_for_telegram` при доставке. Re-use existing content: `_send_*_forecast_inner` берёт `existing.content` если запись есть без `sent_at` (фикс scheduler-loop).
- [x] **W3c Scheduler** — APScheduler с PG jobstore. Отдельный docker-compose сервис `scheduler`. `rebuild_jobs_for_all_subs` каждые 5 мин. Daily: `CronTrigger(hour=daily_send_hour_utc, minute=0, timezone=UTC)`. Monthly weekly: `IntervalTrigger(days=7)` × 4. Monthly bulk: `DateTrigger`. `ForecastDelivery.slot_key` дедупит retry. Inline first-week kick через `asyncio.create_task` (Wave 7 Phase 7).
- [x] **W3d UI** — «📅 Прогноз на месяц 500₽» и «🌅 Прогноз дня + активации 900₽». Месяц → delivery (раз в неделю / сразу всё) → школа → confirm. День → hour (default 4 утра local через `chart.tz_offset`) → школа → confirm. `subscription_view_kb` с активными подписками + «Отменить».
- [x] **W3e Live verify + deploy** — миграция накатана на managed PG (revision `20260526_a1b2c3d4e5f6 head`), docker images bot/worker/scheduler пересобраны, MCP smoke через @Bogman108: `forecast.subscription.created chosen_school=edoha` → `forecast.monthly.generated 23.7s` → `forecast.delivered chunk_count=2` → `forecast.monthly.inline_first_delivery_done week=1` ✓.

> **Hero image в прогнозе** — закрыт отдельно в Wave 7 Phase E (Unsplash + YC AI Studio query gen).

### 🌊 Wave 4 — дневник рефлексии + важные даты (планирование)

Богдан 2026-05-19: «дневник = ежедневные напоминания, время выбирается клиентом, голосовые → транскрибация → утверждение/корректировка, экспорт md».

- [ ] **W4a JournalEntry модель** — chart_id FK, entry_date, energies_summary (текст «энергии дня/месяца/года»), user_reflection (текст), source ENUM(text|voice|auto), created_at. Per chart, per day max 1 запись.
- [ ] **W4b Дневник toggle на карте** — `journal_settings`: enabled bool, reminder_hour_local int (default 21:00). Кнопка «Дневник» в chart_actions_kb_post_interpret. Включение → выбор времени напоминаний.
- [ ] **W4c Daily reminder через scheduler** — переиспользует APScheduler (W3c). Один cron-job per chart с напоминанием на reminder_hour_local. Сообщение «Запишите рефлексию за сегодня — голосовым или текстом».
- [ ] **W4d Голосовой → транскрибация** — Voice message → MCP `mcp__teletranscribe__transcribe_file` → transcript. Подтверждение пользователю кнопками «✅ Добавить запись» / «✏️ Внести корректировки» (последнее → текст «что исправить?» → второй LLM-вызов с edit instruction).
- [ ] **W4e Важные даты** — calculator detector (на основе натальных Шэнь Ша + приходящего такта): за 2 дня + в день активации шлёт уведомление с короткой выжимкой и предложение записать рефлексию. В конце дня — авто-сохраняет prognosis в JournalEntry даже если user не ответил (source=auto).
- [ ] **W4f Экспорт MD** — кнопка «Скачать дневник» → собирает все JournalEntry в `journal_{chart_label}_{date_range}.md` → отправляет файлом.

### 🌊 Wave 5 — встречи с мастером (планирование)

Богдан 2026-05-19: «загрузка с любого URL (GDrive/Yandex Disk/cloud mail/Zoom), отдельная таблица — встреч может быть много».

- [x] **W5a MasterMeeting модель + миграция** — id, user_id FK, chart_id FK, source_url, source_type ENUM(youtube|gdrive|ydisk|zoom|tg_file|other|cloud_mail), title, transcript text, summary text (LLM extractive), uploaded_at, transcribed_at, error nullable, duration_seconds nullable. Migration `c28ca4a32070`.
- [x] **W5b Кнопка «🎓 Загрузить Встречу с Мастером»** на карте → объяснение flow + FSM `waiting_url` → user paste URL.
- [x] **W5c URL downloader** — детектор source_type по hostname в `bot/services/teletranscribe.py::detect_source_type`, потом TT API endpoint `/v1/transcribe-url` (он сам умеет YouTube, Yandex Disk, GDrive).
- [x] **W5d Summary generator** — LLM-вызов из transcript в `tasks/master_meeting.py::_generate_summary` → структурированная выжимка с разделами `## Темы`, `## Рекомендации мастера`, `## Глубинные аспекты карты`. Хранится в `summary`.
- [~] **W5e KuzuDB integration** — **MVP live** (актуализировано 2026-06-10): `_load_master_meeting_summaries` в [consultation.py](bot/routers/consultation.py) инжектит до 3 последних summary в `[PERSONAL_MASTER_NOTES]` (контекст не переполняется — cap 3, старые вытесняются). **Full-версия (KuzuDB per-chart) остаётся backlog'ом**, имеет смысл делать ПОСЛЕ bge-m3 (1.9.16) — semantic retrieval сразу покроет и meeting-ноды. Пересмотр Богдана 2026-05-20: НЕ инжектить транскрипты напрямую в промпт-секцию. Вместо этого:
  - Парсить `summary` встречи на triplets (extract concepts через subagent или fast LLM)
  - Записывать в **KuzuDB** как новый Node-type `MasterMeetingNote` с `level=L8_personal_master` и `source_authority=10` (выше учителей)
  - В `ai/rag/retrieve.py`: при матчинге концептов вопроса — поднимать релевантные MasterMeetingNotes per chart, отдавать через `[KNOWLEDGE]` блок наравне с teacher KB
  - `select_skill` → `concept_hints` boost'ят retrieval как обычно
  - Estimate: 3-4 часа (schema migration + ingest pipeline + retrieve filter by chart_id)
- [x] **W5f Удаление и список встреч** — handlers `mm:show/v/d/dc` с confirm, server-side ownership check.

---

## 🔮 Backlog для следующей сессии (зафиксировано 2026-05-20)

### W4e-scheduler — Важные даты, доставка (актуализировано 2026-06-10)

Calculator-детектор есть ([calculator/important_dates.py](calculator/important_dates.py)). Большая часть W4e уже live — секция ниже была устаревшей:

- [x] **W4e-1 Scheduler job** — `scan_important_dates_job` live (cron 09:00 UTC, warning за 1-2 дня, ≤1/неделю + per-date dedup `d4e5f6a7b8c9`). **2026-06-10 v2:** day-of рефлексия вынесена в почасовой `scan_reflection_prompts_job` — приходит в 18:00 локального времени карты (`reflection_hour_utc`, migration `e5f6a7b8c9d0`, commit `5301613`).
- [x] **W4e-2 toggle** — кнопка «🌟 Важные даты ON/OFF» в меню карты, handler `handle_chart_important_dates_toggle` в [bot/routers/start.py](bot/routers/start.py); подписка на прогнозы авто-включает (forecast.py). Toggle теперь пересчитывает `reflection_hour_utc` из `chart.tz_offset`.
- [x] **W4e-3 Live verify** — работает в проде (баг «дубли важных дат» найден и пофикшен 2026-06-02 `dbaaa1a` — доказательство боевой эксплуатации).
- [ ] **W4e-4 Auto-запись дневника (единственный оставшийся пробел спеки)** — `JournalEntry.upsert(source=auto)` если пользователь не ответил на рефлексию. Enum `JournalEntrySource.auto` и рендер в journal.py уже есть, writer отсутствует. **План (≤1.5ч):** в `scan_reflection_prompts_job` сразу при отправке prompt'а делать `JournalEntryRepository.upsert(chart_id, entry_date=local_today, energies_summary=<выжимка hit.active_stars>, user_reflection=None, source=auto)` — upsert по (chart_id, entry_date) уже перезапишется на text/voice, если клиент потом ответит. Отдельный «конец дня»-джоб не нужен. + 2 unit-теста.

### W5e — KuzuDB integration master meetings

См. выше W5e — большой объём (3-4ч), требует:
- Расширить `knowledge/schema.py` новым Node-level `L8_personal_master`
- `knowledge/ingest/from_master_meeting.py` — subagent extract triplets из summary
- В `ai/rag/retrieve.py::retrieve_for_chart` фильтр по `(level=L8) AND (chart_id=current)`
- Update `compose_messages` чтобы при наличии релевантных MasterMeetingNotes — поднимать их в `[KNOWLEDGE]` блоке с пометкой «личные заметки мастера»

### W6 — задачи отложенные с прошлых сессий

- [ ] **W6-1** Scheduler logs deeper: количество отправленных forecast deliveries, средний latency LLM, error rate за 24h (для /admin dashboard).
- [ ] **W6-2** Webhook вместо polling (1.16.4 из старого backlog) — нужен SSL сертификат + nginx proxy на YC VM.
- [ ] **W6-3** YC Container Registry + GitHub Actions CI/CD (1.16.2) — текущий rsync+build-on-VM работает, но deploy дольше чем pre-built image.

### W7 — монетизация ЮKassa (когда подключим)

Когда ЮKassa подключится, см. checklist в [MASTER.md](MASTER.md) → секция «Wave 3 — free-dev-bypass монетизации».

---

## 🟢 До закрытия MVP

### 1.7 Визуальная карта (отложенное в 1.16)
- [ ] 1.7.3 Загрузка PNG в Yandex Object Storage (aioboto3 + хеш-кэш)
- [ ] 1.7.5 Fallback: Pillow-композиция из 24 PNG-ассетов если CairoSVG недоступен

### 1.9 Knowledge graph RAG (фрактальный) — отдельная итерация
> Богдан хочет **fractal RAG-Graph** методику. План: [~/.claude/plans/badzi-fractal-rag-graph.md](~/.claude/plans/badzi-fractal-rag-graph.md). MVP-ветка («KB lite») закрыта — keyword-индекс + интеграция в compose_messages работает. Полноценный fractal-граф (KuzuDB + ingest pipeline + concept-extractor) идёт фазами 0-3.
- [x] 1.9.1 Исследовать fractal RAG-Graph:
      - Subagent-attempt 2026-05-17 → [fractal_rag_2026-05-17.md](doc/research/fractal_rag_2026-05-17.md) (unverified, оставляю как историю)
      - **Verified research 2026-05-19** через WebSearch + WebFetch → [retrieval_stack_2026-05-19.md](doc/research/retrieval_stack_2026-05-19.md) — содержит:
        1. **KuzuDB archived 2025-10-10** (Apple acquisition) — VERIFIED через github.com/kuzudb/kuzu
        2. Сравнение embedded graph DB alternatives → **рекомендация Apache AGE на Yandex Managed Postgres** (0 new infra, OpenCypher, pgvector для эмбеддингов в той же БД)
        3. Embedding модели — **bge-m3** (unified dense+sparse+ColBERT, 100+ langs, +500MB image)
        4. LLM concept extraction — **Qwen3-3B через YC** (5× дешевле Haiku, тот же провайдер что Анастасия, RU+ZH native)
- [x] 1.9.2 Спроектировать схему графа Бацзы — [knowledge/schema.py](knowledge/schema.py): Node + 6 rel-tables.  
      **Caveat / отклонение от плана:** Element / Stem / Branch / Rule **не** стали отдельными NODE-таблицами — унифицированы как `Node` c `level` (L1-L7). Причина: на 33+ docs неэффективно делать table-per-type; KuzuDB Cypher и так фильтрует через `WHERE n.level = ...`. Если корпус превысит 1000 узлов и появится таб-специфичная индексация, схему перерисуем.
- [x] 1.9.3 Оцифровка [База/ba_zi_prompt_anastasia_v2.md](База/ba_zi_prompt_anastasia_v2.md) → граф:
  - 13 секций вырезаны из 927-строчного промпта по gap-анализу (пропустили дубликаты с PDF — 4 столпа, 10 stems, 12 branches, элементы)
  - Закрыли пробелы в L3 / L5 / L6 / L7:
    - L3: `ten_gods/anastasia_methodology.md`, `twelve_growth_stages.md`
    - L4: `empty_branches_kongwang.md`
    - L5: `anastasia_shen_sha_catalog.md`, `anastasia_nobles_guiren.md`
    - L6: `anastasia_25_classical.md` (структуры 格局)
    - L7: `dm_strength_analysis`, `useful_harmful_god`, `career`, `relationships`, `health`, `talents`, `forecast_methodology`
  - Все с `source: anastasia_system_prompt_v2`, `source_authority: 8`
  - Граф вырос: **33 → 46 real Nodes, 445 → 548 edges**, L3 появился (0→2), L6 появился (0→1), L7 утроился (3→10)
  - Smoke: «что такое 七杀?», «пустые ветви?», «格局 структуры?», «貴人?», «12 стадий?», «таланты?» — все 6 возвращают релевантный `[KNOWLEDGE]` блок
- [x] 1.9.4 RAG-поиск по концептам вопроса — **апгрейд из KB-lite до KuzuDB-Cypher**: [ai/rag/retrieve.py](ai/rag/retrieve.py) делает 2 параллельные запросы (concept-overlap + title-substring CONTAINS), сливает scores, top-k + 1-hop expansion на typed edges
- [x] 1.9.5 Интеграция в `compose_messages` — [ai/temporal_context.py:329-331](ai/temporal_context.py) блок `[KNOWLEDGE]` между `[CALENDAR_SELECTION]` и `[QUESTION]`. Импорт: `from ai.rag import load_knowledge_for_question`.
- [x] 1.9.6 **Phase 0.3** Оцифровка [База/Основы Ба Цзы .pdf](База/Основы Ба Цзы .pdf):
  - Извлечение PyMuPDF → [foundation_course_pdf.md](База/teacher/_audio_transcripts/foundation_course_pdf.md) (200 стр., 36 735 слов)
  - **Разбивка по L1-L7** через subagent-pipeline [knowledge/ingest/from_pdf.py](knowledge/ingest/from_pdf.py) → 31 .md в L1_foundational (9) / L2_atoms/stems (10) / L2_atoms/branches (6) / L4_interactions (3) / L7_predictive_patterns (3). TOC: [foundation_course_pdf.toc.json](База/teacher/_audio_transcripts/foundation_course_pdf.toc.json)
  - 1 chunk (#32 библиография) упал с socket error — пропущен (не predictive content)
  - Fix: title с двоеточием экранируется в frontmatter-шаблоне (`title: "..."`)
- [x] 1.9.7 **Phase 1.1** [knowledge/schema.py](knowledge/schema.py) — DDL для Node + 6 rel-tables (REFERS_TO/GENERATES/CONTROLS/COMBINES_WITH/CLASHES_WITH/EXAMPLE_OF), все `IF NOT EXISTS`.
- [x] 1.9.8 **Phase 1.2** [knowledge/bootstrap.py](knowledge/bootstrap.py) — `python -m knowledge.bootstrap [--db-path P] [--recreate]`, идемпотентно, тесты 13/13.
- [x] 1.9.9 **Phase 2** Ingestion pipeline — [knowledge/ingest/](knowledge/ingest/):
  - [models.py](knowledge/ingest/models.py) `IngestedDoc` / `Triplet` / `IngestState` + `REL_KINDS`
  - [parser.py](knowledge/ingest/parser.py) frontmatter + body → IngestedDoc, sha256 hash от body
  - [extract.py](knowledge/ingest/extract.py) hybrid: sidecar `<file>.triplets.json` (subagent-output) OR heuristic из `related_concepts`
  - [writer.py](knowledge/ingest/writer.py) MERGE Node + replace outgoing edges (идемпотентно), state-файл
  - [cli.py](knowledge/ingest/cli.py) + `__main__.py` — `python -m knowledge.ingest [--source] [--file F] [--incremental] [--dry-run] [--list-pending-extracts]`
  - [from_pdf.py](knowledge/ingest/from_pdf.py) — PDF → L1-L7 chunking helpers (TOC discovery + per-chapter prompt renderers)
  - 47 тестов (parser/extract/writer/cli/from_pdf) — все зелёные, full suite 602/602
  - **Sidecar enrichment пройден для всех 33 .md** (32 subagent + 1 baihu пилот): 32 sidecar JSON-файла рядом с .md
  - **Production ingest с enriched sidecars**: 33 docs → 33 real Nodes + 264 concept stubs + **445 edges** (vs 220 при heuristic-only)
  - **Typed edges распределение**: REFERS_TO 260 / COMBINES_WITH 64 / EXAMPLE_OF 53 / CLASHES_WITH 32 / GENERATES 20 / CONTROLS 15 — **184 typed edges vs 6 при heuristic** (рост ×30)
  - **Hub концепты**: `day_master` (12), `day_master_strength` (12), `earthly_branches` (10), `tian_gan` (9), `liuchong` (5)
  - **Cross-document links**: 12 REFERS_TO + 13 COMBINES_WITH между реальными доками (L1 → L1, L4 → L4, L7 → L7) — граф навигируется
  - **Все 6 классических 沖** из doc 28 типизированы: zi-wu, chou-wei, yin-shen, mao-you, chen-xu, si-hai
  - **Bibliography (#32) ретрай**: успешно (466 строк, 263с, без socket error)
  - **luck_pillars frontmatter**: level исправлен L1 → L7 (subagent ошибся, поправил вручную)
- [x] 1.9.10 **Phase 3** Retrieval pipeline — [ai/rag/](ai/rag/):
  - [store.py](ai/rag/store.py) — KuzuDB read-only singleton + concept vocabulary cache
  - [extract.py](ai/rag/extract.py) — `extract_concepts` (vocab match) + `extract_search_tokens` (Russian-suffix-stemmed tokens, stop-words filtered)
  - [retrieve.py](ai/rag/retrieve.py) — два Cypher-пути (concept-overlap UNWIND + title CONTAINS), score-merge, level/authority tiebreak, optional 1-hop expansion на typed edges (COMBINES_WITH/EXAMPLE_OF/CLASHES_WITH/GENERATES/CONTROLS)
  - [format.py](ai/rag/format.py) — `[KNOWLEDGE]` body renderer с budget (15 000 chars ≈ 5k tokens), paragraph-boundary truncation
  - [public.py](ai/rag/public.py) — `load_knowledge_for_question(question, top_k)` entrypoint
  - **35 тестов** в [tests/unit/test_ai/test_rag/](tests/unit/test_ai/test_rag/) — extract / format / public (e2e против embedded KuzuDB) / retrieve (concept + title + merge + tiebreak)
  - **Удалён** `ai/knowledge_loader.py` + его тест (заменён, no backwards compat)
  - **Production KuzuDB bootstrap**: `./knowledge/kuzu_db` собран из 33 .md (32 PDF + baihu) с 32 sidecar enrichments → 445 edges
  - **Smoke 7/7** реалистичных вопросов: «Белый Тигр», «столпы удачи», «Гэн Металл Ян», «крыса лошадь», «цикл порождения», «баланс пяти стихий», «дракон и змея» — все попадают в правильные L5/L7/L2/L1 ноды
  - **LLM-based concept extraction (Qwen-mini)** — отложен (плановый Phase 3.5): сейчас vocab+stem retrieval даёт recall 7/7 на пилоте, LLM-апгрейд имеет смысл когда корпус расширится до >100 файлов и точность станет узким местом
- [x] 1.9.11 **Phase 4** Deploy:
  - rsync working tree → `yc-user@130.193.51.15:~/BaDzi_bot/` (1 MB sent, исключая .git/.venv/cache/.env)
  - Docker rebuild bot+worker (kuzu 0.10.0 в pyproject — match named-volume dir-format)
  - `docker compose cp knowledge/kuzu_db/. bot:/app/knowledge/kuzu_db/` — KuzuDB-артефакт скопирован в `kuzu_data` named volume
  - **Smoke in container**: kuzu 0.10.0 OK, vocab 206 концептов, 3 вопроса возвращают knowledge-блоки (12 866 / 5 789 / 15 000 chars)
  - Контейнеры `badzi_bot-bot-1` + `badzi_bot-worker-1` healthy, polling started, errors=0
  - **Lessons learned**: docker-compose volume `kuzu_data:/app/knowledge/kuzu_db` всегда монтирует DIR — несовместимо с kuzu 0.11+ file-format. Остаёмся на 0.10 пока volume mount не переделан. Это zafiksirovano в [docker-compose.yml](docker-compose.yml).
- [x] 1.9.12 **Phase 4.3** Real Telegram smoke (2026-05-18):
  - Богдан задал боту `@EdoHa_Badzi_bot`: «что значит Белый Тигр в дне?»
  - Анастасия **дословно цитирует** baihu_white_tiger.md: «Натальное расположение определяет сферу: День → партнёрские разногласия», «Сильный ДМ + 白虎 → конкурентное преимущество, не нужно бояться», «天乙贵人 / 月德贵人 нейтрализуют до 70%», период такта 庚申 «усиливает Тигра — Тигр металлический»
  - Phase 1.9.x end-to-end stack работает в проде с реальными цитатами.
- [x] 1.9.13 Sidecar enrichment для 13 anastasia-секций (2026-05-19):
  - 13 subagent'ов в параллель → 13 sidecar JSON. Anastasia chunks теперь дают типизированные edges (combines_with/clashes_with/generates/controls/example_of) вместо generic REFERS_TO
  - Re-ingest: 46 docs / **617 edges** (было 548, +69 typed)
  - Production VM получил обновлённый kuzu_db через `docker compose cp`, vocab 288 концептов (было 206)
- [x] 1.9.14 **Phase 0.1 verified research** (2026-05-19) → [retrieval_stack_2026-05-19.md](doc/research/retrieval_stack_2026-05-19.md):
  - **KuzuDB archived 2025-10-10** (verified github.com/kuzudb/kuzu) — Apple acquisition.
  - Roadmap migration: Apache AGE на Yandex Managed Postgres (уже есть managed PG) — 0 new infra, OpenCypher, pgvector рядом для эмбеддингов.
  - Embeddings (Phase 2.5) → bge-m3 (unified dense+sparse+ColBERT, +500 MB image).
  - LLM concept extraction (Phase 3.5) → Qwen3-3B через YC (5× cheaper than Haiku, RU+ZH native).
- [~] 1.9.15 **KuzuDB → Apache AGE migration** — **ОТМЕНЕНО (2026-06-02, решение Богдана)**. Остаёмся на **KuzuDB 0.10**; lock-in ADR-004 принят сознательно. Триггер «kuzu перестанет ставиться / CVE» снят как блокер.
- [ ] 1.9.16 **bge-m3 embeddings** — **ОДОБРЕН Богданом 2026-06-10, в работу.** Без зависимости от AGE: KuzuDB 0.10 + косинус в Python над школо-выборкой. Предложение: [doc/proposals/bge_m3_embeddings.md](doc/proposals/bge_m3_embeddings.md). План реализации: [doc/proposals/bge_m3_embeddings_plan.md](doc/proposals/bge_m3_embeddings_plan.md).
  **Решение по движку (обновлено 2026-06-10 после live-probe):** Вариант 1 — **Yandex Cloud Embeddings API** (`text-search-doc`/`text-search-query`, 256-dim, работают с текущим `YC_AI_API_KEY` — проверено живым вызовом). Индексация 7788 узлов = HTTP-вызовы (~15-30 мин), без макбука и без модели в Docker; query-эмбеддинг ~100-300 мс + Redis-кэш; ноль RAM на VM. Quality-gate на эталонных вопросах; провал → Вариант 2: bge-m3 ONNX int8 (~700 MB, по замеру VM 2.3 GB available влезает; fp32 — нет). Fallback при пустых embedding — текущий sparse (как сейчас).
- [ ] 1.9.17 **Phase 3.5 Qwen3-3B concept extraction** — последняя оптимизация retrieval, async-фицирует compose_messages

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

> **2026-06-10 — запрошено Богданом, готов план:** [doc/proposals/admin_analytics_plan.md](doc/proposals/admin_analytics_plan.md). Phase 1 — `/admin` сводка + динамика по дням/неделям/месяцам (миграция `consultations.chosen_school`); Phase 2 — воронка /start→карта→вопрос→лимит→оплата + отток с группировкой по последнему событию и skill последнего вопроса; Phase 3 (опц.) — `bot_events` для точной воронки UI. Реализует 1.15.1-1.15.2 ниже.

- [ ] 1.15.1 [bot/routers/admin.py](bot/routers/admin.py) — `/admin stats`, `/admin export`, `/admin model` → **stats по плану admin_analytics_plan.md (Phase 1-2)**
- [ ] 1.15.2 `/admin stats` — DAU, вопросы/день, выручка, конверсия → **входит в Phase 1-2 плана**
- [ ] 1.15.3 `/admin export` — CSV диалогов в YC Object Storage → ссылка
- [ ] 1.15.4 `/admin model` — смена модели LLM без деплоя (Redis feature flag)
- [ ] 1.15.5 FastAPI admin page (Basic Auth) — дашборд (после TG-версии, если станет тесно)

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
