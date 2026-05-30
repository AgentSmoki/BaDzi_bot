# БаЦзы-Бот — Мастер-документ проекта

## Известные методологические особенности

### Hour pillar — True Solar Time vs local clock

Часовой столп (時柱) рассчитывается по **True Solar Time** с поправками
на долготу и Equation of Time (`calculator/true_solar_time.py` →
`calculator/pillars.py::_hour_branch_idx`). Это **классически
корректно**: китайская метафизика синхронизирует часовые ветви с
истинным положением Солнца, а не с гражданскими часами.

**Из этого следует расхождение** с популярными онлайн-калькуляторами
вроде mingli.com, которые игнорируют longitude correction и берут
ветвь часа напрямую из local clock time. Пример (25.07.1988 12:00
Волжский, lon=44.7°E, MSK летнее UTC+4):

| Метод | UTC | LMT | TST | Hour branch |
|---|---|---|---|---|
| Mingli (без TST) | — | — | local 12:00 | 午 Лошадь |
| Наш бот (TST) | 08:00 | 10:58 | ≈11:00 | 巳 Змея |

Разница — это **методологическая разница**, не баг. Если клиент
спрашивает «почему у вас Змея, а на mingli Лошадь» — отвечаем что
мы считаем по солнечному времени для точности, как делают
классические школы Цзы Пин и Раймонд Ло.

---



> Telegram-бот для персональных AI-консультаций по системе Ба Цзы (四柱命理)
> с консультантом Анастасией. Высокоточный расчёт + мульти-модельный AI.

**Разработчик:** Богдан
**Дата старта:** март 2026
**Статус:** 🚧 Разделы 1.5, 1.6 и большая часть 1.7 закрыты (2026-05-07). End-to-end FSM собирает данные → Calculator → БД → SVG/CairoSVG-карта (PNG) → Telegram. ⚠️ **Открытые баги визуала после последнего деплоя** — см. секцию «Известные проблемы» ниже. 871/871 тестов ✓ покрытие 97.85%.
**Версия документа:** 3.5

---

## Сессия 2026-05-25 — graphify update + актуализация

**Что закрыто за эту и предыдущие сессии (между 2026-05-21 и 2026-05-25):**

| Wave 7 фаза | Статус | Commit | Что |
|---|---|---|---|
| Phase 1 (формат ответа) | ✅ | `0ad9d29` + `09c02e8` | нарратив + inline-расшифровка иероглифов + HTML-bold + 4-5 эмодзи |
| Phase 2 (3 школы) | ✅ | `aa3a4d6` + hotfix `dfb857e` | `base_classic/edoha/modern.md` + `school_selector_kb` + FSM `choosing_school` + `_safe_load_skill` через `get_args(SkillName)` |
| Phase 4 (6 драфтов) | ✅ as docs | `aa3a4d6` | 6 алгоритмов в `ai/prompts/algorithms/*.md` — ждут ревью сенсея (см. [doc/algorithm_review_prompts.md](doc/algorithm_review_prompts.md)) |
| Phase 5 (KB + RAG school-filter) | ✅ | `3034bc3` | `school` колонка в Node, 46 teacher-docs размечены, `_school_clause` в `retrieve.py` |
| Phase 5 live-verify | ✅ | — | edoha vs classic выдают разные `[KNOWLEDGE]` блоки; подтверждено MCP @Bogman108 |
| Phase 5.4 → EdoHa import | ✅ | `5b273d1` | 7742 узла Digital Twin Мастера импортированы (см. Сессия 2026-05-24 ниже) |
| Phase E (Unsplash hero) | ✅ | `a3abadc` | `ai/day_image.py` + YC URI hotfix + force-recreate деплой |
| Phase 3.5 (LLM concept extract) | ✅ | — | `ai/rag/llm_extract.py` + Redis `ConceptCache` + 15 тестов |
| Option X (school-neutral risk) | ✅ | `03502bc` | `risk.md` → дисциплинатор, 3-vs-1 переехал в `base_edoha.md` |
| UX 3 free questions | ✅ | `85269d1` | `free_questions_used: int` миграция + `_remaining_footer` + auto-resume + неактивные кнопки оплаты |
| Phase 6 (docs) | ✅ | — | [doc/school_layered_flow.md](doc/school_layered_flow.md) + [doc/algorithm_review_prompts.md](doc/algorithm_review_prompts.md) |

**graphify-out обновлён** (this session): 810 файлов изменено, 213 удалено,
3558 nodes / 6210 edges / 249 communities в графе. Топ-30 communities
человекоразмеченые. См. [graphify-out/GRAPH_REPORT.md](graphify-out/GRAPH_REPORT.md).

**God nodes** (топ узлы по связности): `ChartInput` (116 edges),
`ChatMessage` (106), `ChartOutput` (97), `OrchestratorError` (96),
`User` (81), `ChartRepository` (80), `HistoryStore` (72) — это
архитектурное ядро бота.

**Surprising connections** в новом графе — `risk.md` skill ↔
`algorithms/risk_assessment.md` draft помечены `semantically_similar_to`
с confidence 0.85+ (правильное наблюдение: один runtime + один draft
покрывают одну доменную область двумя слоями).

**Что осталось в backlog'е (приоритизированный список):**

1. **`1.18.8` Sensei review 6 драфтов** — отдать [doc/algorithm_review_prompts.md](doc/algorithm_review_prompts.md) Мастеру; после апрува выбрать integration option (A/B/C/D из [doc/school_layered_flow.md](doc/school_layered_flow.md)).
2. **`1.18.14` «Запомнить выбор школы»** — `Chart.default_school` NULLABLE → если установлен, не спрашивать каждый раз.
3. **`1.18.23` Self-improvement loop** — 👍/👎/✏️ под ответами → накопление feedback'ов в KB с `school` тегом.
4. **Embeddings bge-m3** (Phase 2.5) — research-промпт уже написан; впервые ставит вопрос semantic vs keyword retrieve для 7742 edoha-узлов.
5. **W5e-MVP master meetings per-chart binding** — открыто с Wave 5.
6. **ЮKassa real integration** (1.12.3 backlog) — пока mock pricing.
7. **Apache AGE migration from kuzu 0.10** (1.9.15 backlog) — снимает lock-in ADR-004.
8. **Cleanup: 525 EdoHa highlights в `База/edoha/highlights/`** — дублируют KuzuDB, ценность только в git-visibility. Решение об удалении после стабилизации edoha-консультаций.

**Архитектурные правила, закреплённые в memory (для будущих сессий):**

- `rsync` — только абсолютный путь источника (не `./`), иначе залетают файлы Primary working directory другого проекта.
- `.env` ключи на VM — вручную (`scp` + `cat >>`) + `docker compose up -d --force-recreate` (`restart` НЕ перечитывает `env_file`).
- Не урезать функционал ради MVP — features (overlays / B-roll / multi-format) это product, а не оптимизация.
- Каждый автор методологии — отдельный скилл, не агрегировать.
- В голосе Мастера ЭдоХа НЕТ англицизмов (`pipeline`, `case`, `evidence`) и латиницы в опечатках — только русский + китайские иероглифы как часть жаргона.

---

## Сессия 2026-05-24 — EdoHa Digital Twin импорт (1.18.22 закрыт)

**Контекст.** Phase 5.4 backlog'а («Edoha sensei ingest») реализован — все
**7742 узла Digital Twin Мастера ЭдоХа** из `/Users/admin/Documents/Razarabotka/EdoHa/kuzu/db`
импортированы в BaDzi `knowledge/kuzu_db` с `school='edoha'`. До этого
импорта при выборе школы 🌀 Мастер ЭдоХа RAG возвращал только 32 universal
ноды (edoha-фильтр в Phase 5 был, но edoha-нодов = 0); теперь возвращает
universal + 7742 edoha с приоритизацией L8 квинтэссенции (Manifesto/
Quote/Fact) над L7 (MentalModel/CausalBelief/Document) и L6 (Relation/
StyleMarker).

**2-фазный pipeline** (kuzu version conflict — EdoHa на 0.11.3 file-format,
BaDzi на 0.10 dir-format):

| Phase | Скрипт | Venv | Что |
|---|---|---|---|
| 1 | `scripts/edoha_export_json.py` | EdoHa | Читает EdoHa kuzu (0.11) → JSONL в `/tmp/edoha_export/` (8 nodes_*.jsonl + edges.jsonl) |
| 2 | `scripts/import_edoha_kuzu.py` | BaDzi | JSONL → `IngestedDoc` через адаптер → `knowledge.ingest.writer.upsert_doc` в BaDzi kuzu |
| 3 (опц.) | `scripts/export_edoha_to_md.py` | любой | 524 highlight .md в `База/edoha/highlights/` для git-видимости |

**Маппинг типов** (id-префикс `edoha:<type>:<original_pk>`):
- Manifesto (212) → L8 / auth 10
- Quote (112) → L8 / auth 10
- Fact (788) → L8 / auth 9
- MentalModel (808) → L7 / auth 9
- CausalBelief (1595) → L7 / auth 8
- Document (537) → L7 / auth 9
- Relation (539) → L6 / auth 8
- StyleMarker (3151) → L6 / auth 7

**Edges**: 7850 (только DERIVED_FROM реально заполнен в EdoHa — остальные
REL pустые: BELONGS_TO_DIGEST=0, CITES=0, REINFORCES=0, CONTRADICTS=0).
Маппинг: DERIVED_FROM → REFERS_TO с `kind='derived_from'` (через стандартный
writer.py, kind дискриминатор пока не используется в Cypher retrieve).

**Технические находки сессии:**

1. **EdoHa schema несовместима с BaDzi напрямую** — EdoHa использует
   фрактальную иерархию Person/Digest/Document + 7 L4 entity tables;
   BaDzi — одна плоская Node table. Решено через JSONL intermediate,
   не пытаемся реплицировать EdoHa schema в BaDzi.

2. **Kuzu version mismatch** (EdoHa 0.11.3 single-file vs BaDzi 0.10
   directory) сделал прямое чтение из BaDzi venv невозможным
   (`IO exception: Cannot open file .lock: Not a directory`). 2-фазный
   pipeline через JSONL обходит это без upgrade'а BaDzi (lock-in на
   0.10 из-за docker named volume, см. ADR-004).

3. **Buffer pool OOM на 5000+ upserts** — kuzu 0.10 по умолчанию
   аллоцирует 80% RAM, на 8 GB ноутбуке с MCP+IDE упирался в OOM на
   3000-м StyleMarker. Решение: `kuzu.Database(buffer_pool_size=1*1024**3)`
   + `CHECKPOINT` каждые 500 upserts → 7742 nodes импортируются за ~7
   минут без сбоев.

4. **Edges export query** — в kuzu 0.11 нельзя `RETURN a._label, b._label`
   (`_label` не свойство node alias). Решение: `RETURN a, b` целиком
   как dict, потом `dict["_label"]` уже есть в Python-стороне.

**Распределение в BaDzi kuzu после импорта:**

```
classic    14
edoha    7742
universal  32
```

**RAG retrieve smoke** (вопрос «опасный месяц 2026?» с `school='edoha'`):
возвращает ~11 KB [KNOWLEDGE] блока с цитатами s248 «Прогноз октября
2024» из транскриптов мастера про конфликт энергий Дракона и Собаки —
впервые edoha-выборка даёт качественно отличный контекст от classic/
modern.

**Что НЕ работает / отложено:**

- W5e-MVP master meetings: интеграция Богдановских master-meeting
  summaries как L8_personal_master c filter по `chart_id` (нужен схема
  extension для chart_id-binding на Node). Сейчас EdoHa импорт даёт
  global personal master content (не per-chart) — это OK, но
  индивидуальные сессии Богдана с мастером пока не добавляются автоматом.
- bge-m3 embeddings (Phase 2.5) — стало особенно важным теперь когда
  7800+ узлов в графе; без векторного ranking sparse retrieval может
  пропускать релевантное.

---

## CHANGELOG (server-side hotfixes)

> Журнал правок, сделанных **на самом сервере** (vim-on-VM, hotfix-команды),
> в обход стандартного `local edit → commit → rsync` pipeline. Каждая запись
> должна быть переигрыванием в git как только появится возможность —
> после этого её можно пометить **«merged in git@<sha>»** или удалить.
>
> Формат: `YYYY-MM-DD HH:MM UTC | файл/команда | причина | git-status`

- `2026-05-20 19:23 UTC | .env: YC_FAST_MAX_TOKENS=3000 → 4000 (sed на VM) | thinking model съедала 2000-token бюджет на reasoning_content → router falled back; промежуточный 3000 поднят до 4000 для запаса | merged в default (bot/config.py + .env.example = 4000)`

---

## Wave 3 — free-dev-bypass монетизации (2026-05-19)

> **`settings.forecast_free_bypass=True`** — все клиенты могут активировать
> платные подписки на прогнозы (500 ₽ / месяц, 900 ₽ / день+активации) **БЕЗ ОПЛАТЫ**
> пока ЮKassa не подключена в задаче **1.12.3 ЮKassa интеграция** (см. tasks.md).
> При покупке записывается `payment_provider="free_dev_bypass"` для аудита.
>
> **Что сделать когда ЮKassa подключится** (одна сессия, ~3-4ч):
> 1. `settings.forecast_free_bypass=False` — переключить флаг в проде.
> 2. В W3d UI handler «Купить» → создать ЮKassa-платёж + redirect URL вместо прямого `create`.
> 3. ЮKassa webhook → активирует подписку с `payment_provider="yookassa"`.
> 4. История платежей: добавить `payment_id` в `ChartForecastSubscription`.
> 5. Старые `free_dev_bypass` подписки оставить активными до их `expires_at` — не отзывать ретроактивно.
> 6. Логи: dashboard в /admin показывает «N free-bypass / N yookassa» подписки.

---

## Сессия 2026-05-22 — Wave 7 kickoff: Анастасия 2.0 (3 школы + алгоритмы мышления)

**Контекст.** Сенсей Богдана разобрал ответ Анастасии на тестовом вопросе про опасные периоды (транскрипт 2026-05-21, 1783 sec, ≈10k слов). Ключевая критика: модель видит **одно** столкновение (六冲 натальной 亥 ↔ приходящей 巳) и навешивает на него весь риск — назвала май самым опасным месяцем 2026. По факту главная катастрофа в марте: 2 кролика (卯) в натале + 3-й приходящий → паттерн **3-vs-1** против петуха (酉), военная аналогия «3 нападающих против 1 защитника = победа атаки». Анастасия этот паттерн пропустила.

**Архитектурное решение Богдана (ADR-011 ниже):** не одна Анастасия с алгоритмами «поверх», а **три параллельных версии** — Классическая / Мастер ЭдоХа / Современная — с inline-выбором в начале каждой консультации. Алгоритмы мышления (chain-of-thought) — суть школы ЭдоХа, не common feature.

**Phase 1 закрыт в эту сессию** (commits `0ad9d29` + `09c02e8`, всё live):
- HTML-конверсия `**X**` → `<b>X</b>` в [bot/routers/consultation.py::_markdown_to_html](bot/routers/consultation.py) — звёздочки больше не видны в Telegram (parse_mode=HTML глобально, но LLM шлёт Markdown)
- Запрет на bullet-dump аналитики в [INSTRUCTION_PREFIX](ai/prompts/__init__.py): «Анализ карты — 3-7 пунктов с цитатами [BAZI_DATA]» → «Что я вижу в вашей карте — 2-3 абзаца нарративом, БЕЗ списка 10 Богов / скрытых стволов / звёзд»
- Правило inline-расшифровки иероглифов в [base.md](ai/prompts/base.md): формат `<b>иероглиф</b> (русский перевод)`. Угловые скобки 「」 отвергнуты после первого прогона
- Эмодзи бюджет 1-2 → 4-5 indicating (🌿🔥⛰⚔️💧 для стихий, ✨⏳💡☯️ для семантики)
- Live-verified через MCP: вопрос «какая моя главная сильная сторона?» → нарратив, все иероглифы расшифрованы (`<b>丁</b> (Дин — Огонь Инь)`, `<b>七杀</b> (Семь Убийств)`...), 5 эмодзи, заголовки plain без `*`

**Phase 4 (pre-проект) начат:** [ai/prompts/algorithms/risk_assessment.md](ai/prompts/algorithms/risk_assessment.md) — первый алгоритм-драфт (3-vs-1 паттерн). Полный разбор на эталонной карте Богдана: март 2026 — реальная катастрофа (3-vs-1 vs 1 петух), май — обычное 六冲. Доказывает что алгоритм работает. Ждёт ревью Богдана + сенсея перед интеграцией в `base_edoha.md`.

**Backlog Wave 7** (полный список в [tasks.md](tasks.md) → 🌊 Wave 7):
- 1.18.0 Phase 1 — ✅ закрыт
- 1.18.1 risk_assessment.md — ✅ драфт готов
- 1.18.2-7 — 6 драфтов алгоритмов (opportunity / relationships / career / decision / health / term_unpack)
- 1.18.10-15 — Phase 2: три base_*.md + UX выбор школы (FSM `choosing_school` + `school_selector_kb`)
- 1.18.20-24 — Phase 5: KB разметка по школам + ingest транскрипта сенсея в KuzuDB как L8_personal_master / school=edoha
- Полный план: `~/.claude/plans/misty-enchanting-parnas.md` (часть 2)

**Что читать первым в новой сессии:** [tasks.md](tasks.md) → Wave 7 + `~/.claude/plans/misty-enchanting-parnas.md` часть 2. Следующий шаг — 1.18.2 (opportunity_window.md) или Phase 2 (если Богдан утвердит риск-алгоритм первым).

---

## ADR-011: Three-school architecture (Анастасия 2.0)

**Status:** Active (kickoff 2026-05-22). Implementation в Wave 7.

**Context:** Wave 6 ADR-010 ввёл skill-router (work/relationships/health/time/default) поверх одной Анастасии. Это снизило галлюцинации (узкая инструкция per домен), но не закрыло **методологическую** разноголосицу: классическая школа (Yuan Hai Zi Ping, Раймонд Ло) и подход твоего сенсея ЭдоХа дают **разные ответы** на один и тот же вопрос. Сейчас модель цитирует обе как абсолютную истину — клиент получает противоречивый ответ.

Разбор сенсея 2026-05-21 показал что Анастасия:
1. Применяет только классические правила (одно 六冲 = опасно), пропускает edoha-специфику (3-vs-1)
2. Не признаёт субъективность интерпретации — выдаёт «правду» вместо «версии правды»
3. Не даёт клиенту выбор между подходами

**Decision:** Три параллельных prompt-документа `base_classic.md` / `base_edoha.md` / `base_modern.md`, каждый — самостоятельная «версия Анастасии». При нажатии «Задать вопрос по карте» юзер выбирает школу через `school_selector_kb` (3 inline-кнопки), FSM сохраняет `chosen_school` в state, `compose_messages` грузит соответствующий `base_*.md` как system prompt. Skill-router (ADR-010) остаётся для определения domain — он работает поверх любой школы.

**Алгоритмы мышления (chain-of-thought) — суть школы ЭдоХа**, не common feature. В `base_edoha.md` встраиваются 6-7 алгоритмов из `ai/prompts/algorithms/*.md` (3-vs-1 для рисков, шахматные паттерны для решений, военные аналогии). `base_classic.md` использует чисто учебниковые правила; `base_modern.md` — синтез + язык психологии.

**Knowledge base разметка:** все 33 teacher-docs в `База/teacher/` получают frontmatter `school: classic | edoha | modern | universal`. `ai/rag/retrieve.py` фильтрует по школе: если выбрана `edoha` → только `universal + edoha` ноды в [KNOWLEDGE]. Транскрипт сенсея → ingest в KuzuDB как `school: edoha, source_authority: 10, level: L8_personal_master`.

**Consequences:**
- ✅ Клиент сам выбирает методологию — отпадает претензия на единственную истину
- ✅ Школа ЭдоХа — отдельный продукт с эксклюзивными алгоритмами, маркетинговая дифференциация
- ✅ Расширяемо: четвёртая школа (например, «китайская медицинская») добавляется новым `base_<name>.md` без правки code
- ⚠️ DB-разметка KB занимает 3-4ч руками + ingest sensei material 2-3ч
- ⚠️ UX добавляет лишний шаг перед вопросом. Mitigation: опция `Chart.default_school` (отложить на 1.18.14) — при установленном дефолте экран выбора пропускается
- ⚠️ Знание Анастасии становится школо-зависимым. Если юзер задал вопрос на классике, потом захотел edoha — нужно начинать новую consultation. История диалога не переключается между школами (это правильно — два разных Голоса)

**Implementation:** Wave 7 → 1.18.10-15 в [tasks.md](tasks.md). Phase 1 (формат ответа) уже закрыта в 1.18.0.

---

## Сессия 2026-05-20 (вечер) — Wave 6 Phase 7 closure через Telegram MCP userbot

**Контекст.** Phase 7 (live verify) висела открытой с 2026-05-19. Закрыта в эту сессию через MCP-сервер `telegram` — мой userbot-логин под акк `@Bogman108` шлёт сообщения @EdoHa_Badzi_bot, читает логи на VM, фиксирует router-decisions.

**Pre-deploy diagnostic.** Все .py + .md файлы на VM и в bot-образе (`af8fc1af9aeb`) **уже совпадают** с локальным деревом по MD5 — Wave 6 был задеплоен в прошлых сессиях. Local pytest 820/820 ✓. Деплой не требовался.

**3 регрессии skill-router'а найдены в проде и пофикшены в процессе:**

| # | Файл | Что было | Что стало |
|---|------|----------|-----------|
| 1 | [ai/skill_router.py](ai/skill_router.py) | Передавал `model=settings.yc_fast_model` (короткое имя `qwen3.6-35b-a3b`) | Строит полный `gpt://{folder}/{model}/latest` URI inline (без circular import на fallback.py). YC `/v1/chat/completions` требует URI-форму — short name → HTTP 400 «Failed to parse model URI» |
| 2 | [ai/skill_router.py](ai/skill_router.py) | `chat(..., response_format={"type":"json_object"})` | Убрано. YC отвергает поле; JSON enforce через system prompt + `_extract_json` regex (orchestrator.chat сам по себе принимает `response_format`, но для YC оно бесполезно) |
| 3 | [bot/config.py](bot/config.py) + [.env.example](.env.example) | `yc_fast_max_tokens: int = 2_000` | `= 4_000` (с запасом — unused budget не биллится). Qwen3.6 thinking-class модели тратили весь 2000-бюджет на `reasoning_content` (логи: ~1949 reasoning + 0 content → `finish_reason=length`) — router падал на ровном месте. 4000 = ~3000 reasoning headroom + 1000 на JSON |

**Tests:** [tests/unit/test_ai/test_skill_router.py](tests/unit/test_ai/test_skill_router.py) — `test_select_skill_passes_response_format_json` переделан в `test_select_skill_omits_response_format` (теперь утверждает обратное правило). pytest 820/820 ✓ после правок.

**6 кейсов Phase 7 — результаты:**

| # | Вопрос | Ожидалось | Router решил | Result |
|---|---|---|---|---|
| 1 | «Когда мне лучше всего сменить работу?» | skill=work | `skill=work, conf=0.92, concept_hints=6` | ✅ ответ через 七杀+偏财 методологию, такт 庚午, 卯酉冲 |
| 2 | «Расскажи про мою совместимость с моим партнёром» | skill=relationships + partner-chart UI | `skill=relationships, conf=0.95, needs_partner_chart=true, clarifying=3` | ⚠️ skill ✓, clarifying loop ✓ (Дворец Супруга 卯, 偏印), но **`partner:add` inline-кнопка не показана** — см. **1.17.9 regression** в tasks.md |
| 3 | «Какие у меня уязвимые системы по здоровью?» | skill=health | `skill=health, conf=0.9, concept_hints=6` | ✅ ТКМ-методология: Огонь→сердечно-сосуд, Земля→ЖКТ, 白虎+飞刃 здоровье |
| 4 | «Что ждёт меня в этом году?» | skill=time + temporal context | `skill=time, conf=0.95, clarifying=2` | ✅ годовой столп 丙午 2026, такт 庚午, резонанс натальной 亥 ↔ текущей 巳 (六冲) |
| 5 | Clarifying flow | FSM `collecting_clarifications` | События `clarifications_requested` + `clarifications.collected` в логах | ✅ покрыт через Кейсы 2,4,6 |
| 6 | «В чём смысл судьбы?» (off-topic) | low-confidence downgrade | `skill=default, conf=0.9` — router сам уверенно выбрал default | ✅ downgrade-механизм не активирован потому что не нужен; router корректно маршрутизирует философию в default |

**Latency:** router 5-8s (Qwen3.6 thinking, ~1800-2300 completion_tokens), main LLM 12-17s. Total per turn ≈ 20-25s.

**1 регрессия для следующей сессии:** **1.17.9 partner:add кнопка не показывается** (см. tasks.md → Wave 6 backlog). После сбора clarifications `_continue_consultation_with_skill` теряет `needs_partner_chart` флаг и идёт сразу в main LLM. Workaround: Анастасия в тексте сама просит данные партнёра. Estimate fix: ~1ч.

**MCP `telegram` рабочий инструмент для будущих Phase 7-ов** — позволяет L2-кодеру тестировать прод-флоу через личный аккаунт Богдана без отдельного test-окружения.

---

## Сессия 2026-05-20 — Wave 1-5 + hotfixes (зафиксировано в конце дня)

**Состояние прода:** все три контейнера (bot/scheduler/worker) healthy в `@EdoHa_Badzi_bot`. 820 unit tests passing.

**Что задеплоено за день:**

| Wave | Что | Status |
|---|---|---|
| W1a/1b | Парсинг дат `88`/ISO + удаление карт | ✅ LIVE |
| W2 | Smart-entry («27.04.88 Севастополь 07:03...») | ✅ LIVE |
| W3a-3e | Платные прогнозы — модели + repo + generator + APScheduler + UI + deploy | ✅ LIVE |
| W4a-d | Дневник + voice + export + reminders | ✅ LIVE |
| W4e detector | `calculator/important_dates.py` + миграция `fd6512684d2f` | ✅ LIVE (только detector, scheduler job — backlog) |
| W5a-d,f | Master-meetings: модель + repo + URL transcribe + summary + UI | ✅ LIVE |
| Hotfixes | BUTTON_DATA_INVALID (callbacks укорочены fc:* mm:*) + SSLContext pickle (Bot/sessions внутри jobs) + ssl→sslmode для psycopg2 + rename + переформулировки от 1-го лица | ✅ LIVE |

**Pending для следующей сессии (см. tasks.md → «🔮 Backlog для следующей сессии»):**

- **W4e-scheduler** — cron-job `scan_important_dates_job` (за 2 дня + в день, rate-limit ≤1/неделю) + `/start` toggle «🌟 Важные даты: ON/OFF» + авто-запись `JournalEntry(source=auto)` если user не ответил в конце важного дня. **Estimate: 2-3 часа.**
- **W5e KuzuDB integration** — master-meeting summaries НЕ в `[MASTER_MEETING_NOTES]` промпт-секцию, а в KuzuDB как Node-level `L8_personal_master`. Retrieve через RAG-pipeline вместе с teacher KB. **Estimate: 3-4 часа.**
- **W6-1** scheduler dashboard метрики; **W6-2** webhook вместо polling; **W6-3** YC Container Registry + GitHub Actions CI/CD.
- **W7 ЮKassa** — checklist уже зафиксирован в этом файле выше.

---

## Сессия 2026-05-19 — Wave 6: AI Skill-Router (ADR-010) — Phase 0-6

**Что сделано:** двухэтапная AI-маршрутизация в `consultation` handler. 7 фаз закрыты, тесты 691 passing, mypy strict clean, deploy ожидает.

| Фаза | Коммит | Артефакты |
|---|---|---|
| 0 — prompt surgery | `25f16c9` | `ai/prompts/base.md` (12 KB), 5 × `ai/skills/*.md`, расширенная база-интерпретация 6→9 блоков с follow-up (пункты 8+9 Богдана), Qwen3-3B probe (недоступен) |
| 1 — skill catalog | `25f16c9` | `ai/skills/{models,loader}.py` — Pydantic SkillSpec/SkillSelection, frontmatter parser, 25 тестов |
| 2 — fast router | `25f16c9` | `ai/skill_router.py::select_skill` — Qwen3.6 max_tokens=2000, JSON output, graceful fallback, 11 тестов. `ai/orchestrator.py::chat` опц. `response_format`. `ai/prompts/skill_router_system.md` + 6 few-shot |
| 3 — partner_chart_id | `e95f200` | Alembic `5c7804a9c2c3`, `Chart.partner_chart_id` UUID NULL FK self, `ChartRepository.set_partner`, `birth_data.handle_add_partner_chart`, `mode="partner"` flow, 9 тестов |
| 4 — clarifying FSM | `fe5c0e7` | `ConsultationState.collecting_clarifications`, `handle_clarification_answer` (Phase 4 — scaffold), 6 тестов |
| 5 — compose_messages | `d987e76` | `[PARTNER_CHART]`, `[SKILL: <name>]`, `[CLARIFICATIONS]` секции; `concept_hints` в `load_knowledge_for_question`. Backward-compat. 11 тестов |
| 6 — wire-up | `76819cd` | `_continue_consultation_with_skill` extracted; `handle_question` 3 ветки (clarifying/partner/straight); `handle_partner_skip`; low-confidence downgrade; logs `skill/had_clarifications/had_partner_chart`; +5 skill-router тестов |

**Ключевые архитектурные решения (ADR-010 в vision.mdc):**

1. **Skill каталог как файлы**, не код — каждый skill — markdown с YAML frontmatter (`work`, `relationships`, `health`, `time`, `default`). Расширение = новый файл + Literal `SkillName`.
2. **Fast router как отдельный LLM-вызов**, не rule-based. `ai/router.py` (rule-based intent/temperature) остаётся параллельно — он определяет `temperature` и `needs_temporal_context` поверх skill-router'а.
3. **Backward-compat в `compose_messages`** — все Wave 6 параметры опциональны. Legacy callers (base_interpretation, calendar) не тронуты.
4. **`base.md` (12 KB) вместо `anastasia_system.md` (39 KB)** только когда skill_spec инжектится. Legacy промпт бэкап остаётся на диске для rollback через feature flag.
5. **Partner chart — обычный Chart того же user_id**, не отдельная сущность. Это даёт reuse `BirthDataForm`/`ChartRepository`/UI без копи-паста.
6. **Low-confidence guard 0.4** — router'у разрешено сомневаться, но не отдавать «специализированный неправильный» ответ.

**Caveats (записаны в коде и vision.mdc ADR-010):**

- **Qwen3-3B недоступен в YC каталоге** на 2026-05-19 (probe HTTP 400 `Failed to get model`). Router работает на Qwen3.6-35B-A3B с `max_tokens=2000` (минимум для thinking-модели — она тратит большую часть на `reasoning_content`; orchestrator.py raises `UpstreamError` при `finish_reason=length` если max_tokens мал). Router latency ~1.5-2s вместо ожидаемых 0.5s. Задача 1.9.17 — миграция на Qwen3-3B остаётся в backlog'е.
- **Router cost** на Qwen3.6 ~0.3 ₽/вопрос → общий cost-per-answer +5-10%.
- `_continue_consultation_with_skill` возвращает без сообщения когда `message.bot is None` — защита от тестовых MagicMock без bot.

**Pending (Phase 7):**

- [ ] **Local docker smoke** — `docker compose build bot worker` + `docker compose up` + проверка что бот стартует без import-ошибок
- [ ] **rsync → YC VM** + `alembic upgrade head` + `docker compose build bot worker && up -d --no-deps bot worker`
- [ ] **Live Telegram smoke** — 4 кейса по skill'ам + проверка clarifying flow + partner-chart flow в реальном `@EdoHa_Badzi_bot`
- [ ] **Update tasks.md** — закрыть `[x] 1.12.0` (уже сделано в коде до Wave 6), добавить `[x] 1.17.1-7` под Wave 6, обновить «текущая итерация»
- [ ] **Optional: /graphify . --update** — пересобрать семантический граф после 7 prose-файлов и нового AI flow

---

## Сессия 2026-05-18 / 2026-05-19 — Fractal RAG follow-up: tech debt cleanup — 1.9.12–1.9.17

**Что сделано:**

| # | Артефакт | Содержание |
|---|---|---|
| 1.9.12 / Phase 4.3 | TG-чат `@EdoHa_Badzi_bot` | Богдан задал боту «что значит Белый Тигр в дне?» — Анастасия **дословно процитировала** baihu_white_tiger.md: «День → партнёрские разногласия», «Сильный ДМ + 白虎 → конкурентное преимущество», «天乙贵人/月德贵人 нейтрализуют до 70%», период такта 庚申 «усиливает Тигра». **End-to-end RAG-stack работает в проде с реальными цитатами учителя.** |
| 1.9.13 / Sidecar enrichment | 13 subagent-вызовов в параллель | Anastasia-секции получили типизированные edges (combines_with/clashes_with/generates/controls/example_of) вместо generic REFERS_TO. Граф: **46 docs / 617 edges** (было 548, +69 typed). Vocab в проде: **288 концептов** (было 206). |
| 1.9.14 / Verified research | [doc/research/retrieval_stack_2026-05-19.md](doc/research/retrieval_stack_2026-05-19.md) | WebSearch + WebFetch (не subagent — никаких галлюцинаций). Подтверждено: **KuzuDB archived 2025-10-10 (Apple).** Рекомендации: миграция на Apache AGE (Yandex Managed PG), эмбеддинги — bge-m3, LLM-extract — Qwen3-3B через YC. |
| 1.9.15 / Migration roadmap | tasks.md backlog | KuzuDB → Apache AGE: ~6-8 часов работы, 0 нового infra (используем уже-managed PG). Триггер: pip перестанет ставить kuzu 0.10 ИЛИ CVE без патча. |

**Ключевые решения:**

1. **Phase 7 «upgrade KuzuDB 0.11+» **закрыт без действия**.** Проект archived — апгрейд не имеет долгосрочного смысла. Вместо него — миграционный план на Apache AGE.
2. **Phase 0.1 теперь verified.** Subagent-research 2026-05-17 (`doc/research/fractal_rag_2026-05-17.md`) оставлен как история. Свежий research через прямые WebSearch/WebFetch без LLM-посредников.
3. **Phase 4.3 закрыт реальным TG-смок.** Цитата из тела `baihu_white_tiger.md` в ответе Анастасии — доказательство что весь stack 1.9.x работает: parser → ingest → KuzuDB → retrieve → format → [KNOWLEDGE] → LLM → пользователь.

**Pending (отложено по приоритету и триггерам):**
- 1.9.15 KuzuDB → Apache AGE migration (Q3 2026 или при наступлении триггера)
- 1.9.16 Phase 2.5 bge-m3 embeddings (после миграции на AGE — pgvector рядом)
- 1.9.17 Phase 3.5 Qwen3-3B concept extraction (последний slot, async-фицирует compose_messages)

---

## Сессия 2026-05-17 — Fractal RAG-Graph closure (Phase 0-4) — 1.9.4–1.9.11

**Что сделано:** план [~/.claude/plans/badzi-fractal-rag-graph.md](~/.claude/plans/badzi-fractal-rag-graph.md) закрыт фазами 0-4, runtime-граф знаний учителя интегрирован в `compose_messages`.

| # | Файл / артефакт | Содержание |
|---|---|---|
| 1.9.7 / Phase 1.1 | [knowledge/schema.py](knowledge/schema.py) (new) | KuzuDB DDL — `Node` table (id/level/topic/title/body/summary/source/source_authority/applicable_when/related_concepts/embedding/content_hash/last_updated) + 6 REL tables (REFERS_TO с `kind`, GENERATES, CONTROLS, COMBINES_WITH, CLASHES_WITH, EXAMPLE_OF). Все `IF NOT EXISTS`. 5 тестов |
| 1.9.8 / Phase 1.2 | [knowledge/bootstrap.py](knowledge/bootstrap.py) (new) | `python -m knowledge.bootstrap [--db-path P] [--recreate]` — идемпотентный bootstrap. 8 тестов (end-to-end Node + REFERS_TO insert) |
| 1.9.9 / Phase 2 | [knowledge/ingest/](knowledge/ingest/) (new) | Pipeline `.md → IngestedDoc → triplets → KuzuDB`: `models.py` (`IngestedDoc/Triplet/IngestState`), `parser.py` (YAML frontmatter + sha256 hash от body), `extract.py` (hybrid: sidecar `<file>.triplets.json` ИЛИ heuristic из `related_concepts`), `writer.py` (MERGE Node + replace edges, идемпотентно), `cli.py` + `__main__.py`. 28 тестов |
| 1.9.6 / Phase 0.3 | [knowledge/ingest/from_pdf.py](knowledge/ingest/from_pdf.py) + [foundation_course_pdf.toc.json](База/teacher/_audio_transcripts/foundation_course_pdf.toc.json) | PDF → L1-L7 chunking pipeline (TOC discovery subagent + per-chapter subagents). [Основы Ба Цзы.pdf](База/Основы Ба Цзы .pdf) (200 стр., 36 735 слов) → 31 .md в L1/L2/L4/L7. 11 тестов |
| 1.9.10 / Phase 3 | [ai/rag/](ai/rag/) (new) | KuzuDB-backed retrieval — `store.py` (read-only singleton + concept vocabulary), `extract.py` (concept matching + Russian-stem tokens), `retrieve.py` (2 Cypher-пути: related_concepts overlap + title CONTAINS, score merge, 1-hop typed-edge expansion), `format.py` (15K char budget), `public.py` (load_knowledge_for_question). 35 тестов |
| 1.9.5 / wire-up | [ai/temporal_context.py:28](ai/temporal_context.py#L28) | `from ai.rag import load_knowledge_for_question` — заменил удалённый `ai/knowledge_loader.py` без изменения сигнатуры |
| Cleanup | — | Удалены `ai/knowledge_loader.py` + `tests/unit/test_ai/test_knowledge_loader.py` (заменены `ai/rag/`, no backwards compat) |
| Content | `База/teacher/` | 33 .md (32 PDF chunks + baihu seed) + 32 sidecar JSON. 64 enrichment-subagent-вызова (32 chunk-creation + 32 triplet-extraction) — суммарно в KuzuDB 33 real Nodes + 264 concept stubs + 445 edges (184 typed: COMBINES_WITH 64, EXAMPLE_OF 53, CLASHES_WITH 32, GENERATES 20, CONTROLS 15; плюс 260 REFERS_TO) |
| 1.9.11 / Phase 4 | rsync + Docker rebuild + smoke | Working tree → VM (`yc-user@130.193.51.15`). Kuzu **0.10.0** в pyproject (см. ADR-004 gotcha ниже). `docker compose cp knowledge/kuzu_db/. bot:/app/knowledge/kuzu_db/` для named volume. Smoke в контейнере: vocab 206 концептов, 3 русских вопроса → [KNOWLEDGE]-блоки 12866/5789/15000 chars. `badzi_bot-bot-1` + `badzi_bot-worker-1` healthy |
| Tests | `tests/unit/test_knowledge/` (12 файлов) + `tests/unit/test_ai/test_rag/` (4 файла) | +87 новых тестов (47 knowledge + 35 rag, удалено 14 knowledge_loader). Финал: **623 passed**, ruff + mypy strict clean |
| Tooling | `~/.claude/skills/graphify` | `/graphify . --update` — обновил seman-граф проекта: 2274 → 2735 nodes / 3712 → 4426 edges / 164 communities |

**Ключевые архитектурные решения:**

1. **Hybrid extract** (Phase 2.2) — extract.py берёт sidecar `<file>.triplets.json` (subagent-output) если есть, иначе heuristic из `related_concepts`. Decoupling runtime от Claude Code subagent: ingest работает всегда, sidecar-enrichment — отдельный workflow. См. [knowledge/ingest/README.md](knowledge/ingest/README.md).
2. **Vocab + Russian-stem retrieval** (Phase 3.1) — LLM concept extraction отложен (план рекомендовал Qwen-mini). Vocab матчится против KuzuDB `related_concepts`, доп. сигналом — токены вопроса (len≥3 после Russian suffix-strip) против `lower(n.title) CONTAINS`. 7/7 русских вопросов попадают в правильные L5/L7/L2/L1 узлы. LLM-апгрейд оставлен как Phase 3.5 slot.
3. **Sync retrieval** — `compose_messages` остался синхронным, чтобы не менять сигнатуру callers (`ai/base_interpretation.py`, `bot/routers/consultation.py`). KuzuDB Python client тоже sync; асинхронность нужна была бы только при добавлении LLM extraction (Phase 3.5).
4. **Kuzu 0.10 lock-in** — docker-compose named volume `kuzu_data:/app/knowledge/kuzu_db` всегда монтирует **директорию**, kuzu 0.11+ ждёт файл. Остаёмся на 0.10 до рефакторинга volume mount (см. обновлённый ADR-004 ниже).

**Pending tech debt:**
- Phase 0.1 — research-документ через `Dev_Architect/research_tool` (subagent-результат имеется в `doc/research/fractal_rag_2026-05-17.md` но не верифицирован)
- Phase 2.5 — bge-m3 embeddings (опционально)
- Phase 3.5 — Qwen-mini concept extraction для увеличения recall на >100 docs
- Phase 4.3 — реальный Telegram-чат-smoke (in-container Python smoke ✓, TG-диалог не проверяли)
- Content — L3 (ten_gods), L5 (stars), L6 (structures) папки почти пустые; рост через workflow в knowledge/ingest/README.md
- Кода в working tree (137 modified + Phase 1-3 untracked) **не закоммичено** — на VM есть, в git нет

---

## Сессия 2026-05-16 — AI migration: OpenRouter → Yandex AI Studio (Qwen3.6) — 1.8.7

**Что сделано:**

| # | Файл | Содержание |
|---|------|-----------|
| Plan | `~/.claude/plans/badzi-yc-ai-migration.md` v3 | 2-tier план: Qwen3.6-35B-A3B @ YC → Claude 3.5 Sonnet @ OpenRouter. Dynamic max_tokens per-tier через ctx-window |
| Infra | YC SA `badzi-ai-sa` (ajenqtfnjgtdnn3iruo8) | Роль `ai.languageModels.user` на folder `b1gtu3ebh1mbqbmkqm9t`. API-key выпущен, записан в .env |
| 1.8.7-1 | [ai/budget.py](ai/budget.py) (new) | `compute_max_tokens(messages, ctx_window, intent, floor, ceiling)`. Char-based token estimate (3.2 chars/tok). DEFAULT_RATIO: simple=0.05, normal=0.15, complex=0.30, interpretation=0.40. 12 unit-тестов |
| 1.8.7-2 | [ai/orchestrator.py](ai/orchestrator.py) | Provider-agnostic refactor. `Provider = Literal["yc", "openrouter"]`. Per-provider httpx singleton clients в `_clients: dict[Provider, AsyncClient]`. `close_clients()` plural. `ChatResult.provider` поле добавлено. `_parse_result` ловит и YC `reasoning_content`, и OR `reasoning` для thinking-truncation guard |
| 1.8.7-3 | [bot/config.py](bot/config.py) + [.env.example](.env.example) | `yc_ai_api_key`, `yc_ai_folder_id`, `yc_primary_model="qwen3.6-35b-a3b"`, `yc_qwen36_context=262_144`. OpenRouter секция переименована — `openrouter_emergency_model`, `openrouter_claude_context=200_000`. `max_output_tokens_ceiling=32_000` |
| 1.8.7-4 | [ai/fallback.py](ai/fallback.py) | 2-tier chain: Tier 1 = YC Qwen3.6, Tier 2 = OR Claude. `FallbackResult` теперь несёт `tier` (1/2) + `provider` (yc/openrouter). Per-tier dynamic `max_tokens` через `compute_max_tokens(ctx_window=cfg.context_window, ...)`. 4xx-other = raise без fallback. 7 unit-тестов |
| 1.8.7-5 | [ai/router.py](ai/router.py) | `RouteDecision` упрощён — `model` и `max_tokens` убраны (sizing переехал в budget). Остались `intent` + `temperature` + `needs_temporal_context` + `reason` |
| 1.8.7-6 | [ai/base_interpretation.py](ai/base_interpretation.py) | `chat_with_fallback(intent="interpretation")` вместо `max_tokens=settings.max_output_tokens` |
| 1.8.7-7 | [bot/routers/consultation.py](bot/routers/consultation.py) | `chat_with_fallback(intent=decision.intent)`. Лог `consultation.completed` теперь содержит `tier` + `provider` |
| 1.8.7-8 | [bot/main.py](bot/main.py) | `close_openrouter_client` → `close_llm_clients` (plural) |
| 1.8.7-9 | [.cursor/rules/vision.mdc](.cursor/rules/vision.mdc) | ADR-002 помечен Superseded by ADR-009. Новый ADR-009 описывает 2-tier цепочку, провайдеры, динамический budget |
| Tests | tests/unit/test_ai/test_budget.py (new), test_orchestrator.py, test_fallback.py, test_router.py, test_base_interpretation.py, tests/unit/test_bot/test_consultation.py | 484/484 ✓ (старые 460 + новые 24 для budget/2-tier/provider) |

**Probe results (live YC API, 2026-05-16):**
- Model `qwen3.6-35b-a3b` отвечает HTTP 200 на `gpt://b1gtu3ebh1mbqbmkqm9t/qwen3.6-35b-a3b/latest`
- Thinking-модель: возвращает `reasoning_content` + `content` (как K2.6 — `_parse_result` уже умеет)
- Smoke (system+user, max_tokens=2000): 55 prompt + 1486 completion, finish_reason=stop, тёплый русский ответ без `!`
- Style guide подтверждается без `_strip_exclaim` поверх

**Чего ещё нет (Phase 8 миграции, осталось):**
- [ ] ruff + mypy --strict проверка после ребрендинга
- [ ] Локальный e2e smoke в Docker (с реальными YC + OR ключами в .env)
- [ ] rsync + rebuild на YC VM
- [ ] Telegram live (закрывает L-2)
- [ ] Tier 2 «огневая» проверка (временно сломать YC key → убедиться что Claude отвечает)

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
| AI провайдер Tier 1 | Yandex AI Studio Foundation Models | Российский биллинг + инфраструктура (ADR-009)     |
| AI основная    | Qwen3.6-35B-A3B (Alibaba, MoE 35B/3B active) | 262k native context, CJK-нативная             |
| AI Tier 2 emergency | Claude 3.5 Sonnet via OpenRouter | Независимый cloud — резерв при YC outage             |
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
| Основная модель  | Kimi K2.6 (moonshotai/kimi-k2.6)      |
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

**Последний коммит:** `47af9f9` (2026-05-07; HEAD на момент старта сессии)
**Незакоммиченные изменения:** ⚠️ да — вся работа сессии 2026-05-07 (третья половина) + завершение 1.7 (1.7.9–1.7.11 + фикс стрелок У-син) ниже не закоммичена; если откроете новый диалог, **первым делом посмотрите `git status` и `git diff` чтобы не потерять контекст**.
**Тесты:** 374/374 ✓ покрытие 98%
**Линтеры:** ruff ✓, ruff-format ✓, mypy strict ✓ (53 файла)

### ✅ Сессия 2026-05-07 (шестая половина) — разделы 1.10 + 1.13 (базовая интерпретация + диалог)

**Что сделано:**

| # | Файл | Содержание |
|---|------|-----------|
| 1.10 | [ai/base_interpretation.py](ai/base_interpretation.py) | Генератор 6 блоков одним вызовом `chat_with_fallback`. Pydantic `BaseInterpretation`, парсер `parse_blocks` (regex tolerant к регистру/порядку), `format_for_telegram` с `<b>` заголовками + `_strip_exclaim` (защита от `!` если LLM прорвал style guide). 11 unit-тестов. |
| 1.13 | [bot/routers/consultation.py](bot/routers/consultation.py) | `handle_ask_pressed` → загрузка Chart + FSM → ввод вопроса. `handle_question` → router (1.8.3) → compose_messages (1.8.6) → chat_with_fallback (1.8.5) с `ChatAction.TYPING` индикатором каждые 4 сек → save Consultation (1.5 модель). `handle_reset` (`/reset` → clear history). 7 тестов handler'а через MagicMock + fakeredis. |
| middleware | [bot/middlewares/history.py](bot/middlewares/history.py) | `HistoryMiddleware(store)` — инжектит singleton `HistoryStore` через `data["history_store"]`. Создаётся при старте бота, aclose при shutdown. |
| main | [bot/main.py](bot/main.py) | Подключён `consultation_router`, добавлен `HistoryMiddleware`, `_shutdown` теперь закрывает OpenRouter client + history store. |

**Поток консультации (после нажатия "Задать вопрос"):**

```
menu:ask → handle_ask_pressed
  ├─ resolve active chart (FSM chart_id или latest)
  ├─ если карты нет → "сначала постройте"
  └─ FSM → ConsultationState.waiting_question, ждёт текст

[user пишет вопрос]

ConsultationState.waiting_question + F.text → handle_question
  ├─ chart = ChartOutput.model_validate(chart.chart_data)
  ├─ decision = route(question)  (intent / temperature / max_tokens / temporal?)
  ├─ history = await history_store.get(telegram_id)  (last 20 msgs, TTL 24h)
  ├─ now_chart = get_current_bazi() if temporal else None
  ├─ messages = compose_messages(system + history + chart + temporal? + question)
  ├─ asyncio.create_task(_keep_typing(message))  ← каждые 4 сек ChatAction.TYPING
  ├─ result = await chat_with_fallback(...)  ← Kimi K2.6 → Claude on 429/5xx
  ├─ message.answer(result.text, reply_markup=after_answer_kb)
  ├─ history_store.append(user msg + assistant msg)
  └─ ConsultationRepository.create(model, tokens, cost_usd, latency_ms, trace_id)
```

**Стек:** ruff ✓, mypy strict ✓ (62 файла), pytest **460/460** ✓ покрытие 98.21%.

**Не сделано в 1.10/1.13 (ожидает других разделов):**
- KuzuDB RAG в context (1.9 — отдельный блок)
- TaskIQ для долгих запросов (1.11 — добавим если LLM-latency станет проблемой)
- Rate limiting / монетизация / 1 free question (1.12)
- Live-проверка в Telegram под пользователем — кнопка `Задать вопрос` теперь рабочая, требует ручного теста в боте

### ✅ Сессия 2026-05-07 (пятая половина) — 2.1.6 закрыт + раздел 1.8 (AI Оркестратор) полностью

**2.1.6 — детерминированность калькулятора:** калькулятор сам по себе детерминирован (1000/1000 одинаковых результатов в одном процессе и между процессами). Все три «плавающих» комбинации в MASTER объяснены парой `(tz_offset, early_rat)` — DST-aware tz_offset для 1999 = 4.0, не 3.0; код через `bot/services/birth_datetime.resolve()` использует pytz, что корректно. Зафиксировано в [tests/unit/test_calculator/test_determinism.py](tests/unit/test_calculator/test_determinism.py) и [tests/unit/test_bot/test_birth_datetime.py](tests/unit/test_bot/test_birth_datetime.py).

**Раздел 1.8 (AI Оркестратор) — все 6 подзадач закрыты:**

| Подзадача | Файл | Содержание | Тестов |
|-----------|------|-----------|--------|
| 1.8.1 | [ai/orchestrator.py](ai/orchestrator.py) | httpx async, ChatMessage/Result, RateLimit/Upstream/Orchestrator errors, lazy singleton, structlog telemetry | 15 |
| 1.8.2 | [ai/prompts/](ai/prompts/) | 39k anastasia_system.md + lru_cache loader | 4 |
| 1.8.3 | [ai/router.py](ai/router.py) | simple/normal/complex с cyrillic word-boundary матчингом | 17 |
| 1.8.4 | [ai/context.py](ai/context.py) | Redis history, TTL 24h, max 20 msgs, bounded | 8 |
| 1.8.5 | [ai/fallback.py](ai/fallback.py) | Kimi → Claude на 429/5xx | 6 |
| 1.8.6 | [ai/temporal_context.py](ai/temporal_context.py) | chart_block + current bazi + compose_messages | 9 |

**Live-валидация на reference карте** (12.09.1999 23:55 Волжский):
- latency 55s · cost $0.028 · completion 2870 tokens (включая reasoning)
- Опознан 丁 Дин-огонь, Косая Печать в дне+часе, такт 乙亥 (2018-2028)
- Стиль выдержан (тёплый, без !), тексту хватает 8192 max_tokens

**Конфиг изменён:** `DEFAULT_LLM_MODEL=moonshotai/kimi-k2.6` (thinking), `LLM_TIMEOUT=420`, `MAX_OUTPUT_TOKENS=8192`. Дубли в `.env` починены. Per-file ignores RUF001/002/003 для `ai/` и `tests/test_ai|test_bot/` (русские keywords/промты — намеренно).

**Стек:** ruff ✓, mypy strict ✓ (59 файлов), pytest **442/442** ✓ покрытие 98.21%.

### ✅ Сессия 2026-05-07 (четвёртая половина) — закрытие раздела 1.7 (Wave A → done)

**Что сделано в этом блоке:**

| # | Задача | Файлы | Содержание |
|---|--------|-------|------------|
| 1 | **Fix arrows У-син** | [ai/svg_renderer.py](ai/svg_renderer.py), [web/templates/chart.svg.j2](web/templates/chart.svg.j2) | DM имеет halo radius 54 (а не 36) — стрелки начинаются/заканчиваются с pad от halo, не от disc. Маркеры укрупнены (gen 14×11, ctrl 12×10) — направление читается. Bulge_ctrl 14→8 — звезда из контрольных дуг чище. |
| 2 | **1.7.9 ProcessPoolExecutor** | [ai/_render_pool.py](ai/_render_pool.py) (new), [ai/svg_renderer.py](ai/svg_renderer.py), [ai/card_renderer.py](ai/card_renderer.py) | Lazy pool, размер `RENDER_POOL_SIZE` env или `cpu_count() // 2`. Async-фасад `render_chart_png_async()`. `card_renderer.render_chart_png` теперь идёт через pool. `close_browser()` шатдаунит pool. |
| 3 | **1.7.11 Benchmark** | [scripts/bench_render.py](scripts/bench_render.py) (new), [doc/benchmarks/render.md](doc/benchmarks/render.md) (new) | Sequential vs pool на эталонной карте, N=50/200. На 4-core хосте pool=4 даёт 2× rps на N=200 (5.1 vs 2.5). |
| 4 | **1.7.10 Drop Playwright** | [pyproject.toml](pyproject.toml), [Dockerfile](Dockerfile), [ai/card_renderer.py](ai/card_renderer.py), [bot/config.py](bot/config.py), [.cursor/rules/vision.mdc](.cursor/rules/vision.mdc), `web/templates/chart.html` (deleted) | `playwright==1.52.0` снят. Chromium-libs (libnss3, libatk*, libxkb…) убраны из Dockerfile (-150 MB образа). `card_renderer.py` сжат до wrapper'а вокруг `render_chart_png_async`. ADR-003 помечен superseded, ADR-007 → status: реализовано полностью. |

**Линтеры/тесты после блока:** ruff ✓ (53 файла), mypy strict ✓, pytest 374/374 ✓ покрытие 98.21%.

**Итог по разделу 1.7:** все пункты `[x]` (1.7.1, 1.7.2, 1.7.4, 1.7.6, 1.7.7, 1.7.8, 1.7.9, 1.7.10, 1.7.11). Открыты только 1.7.3 (PNG → Yandex S3) и 1.7.5 (Pillow fallback) — корректно отложены в 1.16 production deploy.

### ✅ Сессия 2026-05-07 (третья половина) — фикс визуальных регрессий + overhaul раскладки

**Бот сейчас:** запущен локально (PID 88772, см. `ps aux | grep bot.main`) с `BAZI_DEBUG_DUMP_SVG=1` — каждый рендер пишет SVG в `/tmp/last_chart.svg` для отладки. Старые карты пользователя удалены из БД для чистого ре-теста.

#### Закрытые баги

| # | Что починили | Файл | Решение |
|---|--------------|------|---------|
| 1 | **Эмодзи 🌳🔥⛰⚙💧 в У-син не отображаются у пользователя** (хотя на macOS прямой `cairosvg.svg2png()` рендерил ОК) | [web/templates/chart.svg.j2](web/templates/chart.svg.j2) | Overlay-стратегия: под каждым эмодзи всегда лежит цветной диск (`circle.el-bg-{el}`) + белая SVG-иконка `<use xlink:href="#ic-{el}">`. Если эмодзи-шрифт сработал — закроет иконку; если нет (⛰/⚙ text-presentation, или Pango в `asyncio.to_thread` не нашёл колор-fallback) — иконка видна. |
| 2 | **Hidden stems во всех 4 столпах пустые** | то же | Та же шрифтовая проблема. После overlay-фикса + регрессионного теста подтверждено что SVG содержит 6 hidden-stem `<text>` для эталонной карты. |
| 3 | **Стрелки порождения/контроля не отображаются** | [web/templates/chart.svg.j2](web/templates/chart.svg.j2), [ai/svg_renderer.py](ai/svg_renderer.py) | Прямые `<line>` заменены на `<path d="M ... Q cx,cy ...">` (квадратичные дуги Безье); порождение бовает наружу, контроль вовнутрь. Inline `<linearGradient>` per arrow красит штрих от цвета source-элемента к target. Каллиграфические teardrop-marker'ы (`gen-arrow`, `ctrl-arrow`). Эталон в `/tmp/v15-arrows.png`. |
| 4 | **Race condition в `UserMiddleware.get_or_create`** — два параллельных `/start` валились с `UniqueViolationError: users_telegram_id_key` | [db/repositories/user_repo.py](db/repositories/user_repo.py) | Переписано на Postgres-specific upsert: `INSERT ... ON CONFLICT (telegram_id) DO NOTHING RETURNING id`. Если строка существовала — fallback SELECT. Старый `SELECT FOR UPDATE SKIP LOCKED + INSERT` снят как небезопасный (skip_locked позволял second handler пропустить лок и снова INSERT). |
| 5 | **Сообщения пользователя остаются в чате** (хотел: ввёл `12091999` → исчезло, остался только bot anchor с следующим шагом) | [bot/routers/birth_data.py](bot/routers/birth_data.py) | Добавлен helper `_swallow_user_message(message)`, вызывается в `handle_date`/`handle_time`/`handle_city`/`handle_naming_input` сразу после извлечения текста. Telegram silently rejects deletes старше 48h или без permission — обрабатывается через `try/except` с debug-логом. |
| 6 | **Раскладка перекомпонована**: «Господин дня» был широкой полоской на всю ширину (1120px), пользователь хотел узкий слева + У-син шире | [web/templates/chart.svg.j2](web/templates/chart.svg.j2) | ГД-карточка 300×440 слева, У-СИН-карточка 800×440 справа (увеличены отступы между элементами: radius 100→130, label_dist 145→180), Balance 1120×220 ниже с воздухом между строк. Канвас 1200×1400 без изменений. |
| 7 | **Top role-label «Личность, друзья» наезает на DM-эмодзи** | [ai/svg_renderer.py](ai/svg_renderer.py) `_wuxing_wheel` | `label_cy -= 22` (было `-= 8`) — top label получает дополнительный 14-px зазор. Pentagon center в карточке at y=255 (внутри 440-tall card), геометрия проверена: top label visual top at y=43 (под header «ЦИКЛ У-СИН» на y=32), bottom labels visual bottom at y=403 (margin 37px от bottom card border). |
| 8 | **Текст «С возвращением, Богдан…» сразу после naming** | [bot/services/menu.py](bot/services/menu.py), [bot/routers/birth_data.py](bot/routers/birth_data.py) | Добавлена константа `GREETING_AFTER_NAMING = "Что планируете дальше?"`. `send_main_menu(..., greeting=...)` теперь принимает override. `handle_naming_input`/`handle_naming_skip` передают этот override. |
| 9 | **Регрессионных тестов рендерера не было** | [tests/unit/test_ai/test_svg_renderer.py](tests/unit/test_ai/test_svg_renderer.py) | 5 snapshot-тестов на эталонной карте Анастасии: hidden_stems непустые, 5 SVG-иконок + 5 gen-gradients + 5 ctrl-gradients + 6+6 marker-end (5 в пентагоне + 1 в легенде), xlink-namespace объявлен, `render_chart_png` возвращает валидный PNG-header, элементы получают цветовой класс. |

#### Диагностический инструмент

**`BAZI_DEBUG_DUMP_SVG=1`** в [ai/svg_renderer.py:144-147](ai/svg_renderer.py#L144) — env-flag, при котором каждый рендер пишет последний SVG в `/tmp/last_chart.svg`. Без переменной — поведение не меняется. Использовался в этой сессии чтобы доказать что бот генерирует структурно-корректный SVG (и проблема была именно в шрифтовом рендере).

#### Backlog (новое)

**🔥 [tasks.md](tasks.md) пункт 2.1.6 — недетерминированность калькулятора.** При прогоне `calculate_chart()` на одинаковом `ChartInput` (12.09.1999 23:55 Волжский UTC+3, female) выдаёт **разные пиллары**: `辛亥/丁卯/癸酉/己卯`, `壬子/戊辰/癸酉/己卯`, или канонические `庚子/丁亥/癸酉/己卯` (MASTER.md эталон). Описаны 6 гипотез причин (глобальное состояние pyswisseph, Цзе Ци border, early_rat, DST в Волжский 1999, кэш timezonefinder, конкурентный геокодер) и план отладки. **Когда возьмёмся:** сразу после Wave A полностью закроется (live-проверка раскладки + стрелок), но **до 1.8 AI оркестратора** — без воспроизводимого расчёта запускать AI-консультации бессмысленно (карта может между двумя вопросами поменяться).

#### Остаются на следующую сессию

1. **Live-проверка свежей раскладки и стрелок** в Telegram. Бот уже перезапущен с фиксами (PID 88772). Сделать /start от @Bogman108, добавить новую карту, подтвердить что:
   - Введённые сообщения пользователя `12091999`/`2355`/`Волжский` исчезают (фикс 5);
   - В пентагоне видны изогнутые стрелки с градиентом по элементам (фикс 3);
   - После имени бот пишет «Что планируете дальше?» вместо «С возвращением» (фикс 8);
   - Двойной /start не падает (фикс 4).
2. **Закоммитить эту сессию.** Логические группы: (a) рендер + раскладка + тесты; (b) FSM swallow + race-fix; (c) docs (MASTER + tasks). Можно одним коммитом или тремя — на ваш вкус.
3. **Калькулятор 2.1.6** — фикс недетерминированности (см. backlog выше).
4. После — **раздел 1.8 «AI Оркестратор» (Wave B)**: orchestrator/router/context/fallback/temporal-context. Подробнее в [tasks.md](tasks.md#1.8) и в секции «🔜 Следующая сессия».

**Точки входа для отладки и продолжения:**
- [ai/svg_renderer.py](ai/svg_renderer.py) — `_build_context`, `_wuxing_wheel` (radius 130, label_dist 180, bezier arcs); `BAZI_DEBUG_DUMP_SVG=1` для дампа.
- [web/templates/chart.svg.j2](web/templates/chart.svg.j2) — раскладка ГД-узкий-слева + У-СИН-широкий-справа + Balance-расширенный; inline `<linearGradient>` per arrow.
- [bot/routers/birth_data.py](bot/routers/birth_data.py) — FSM с `_swallow_user_message` и `GREETING_AFTER_NAMING`.
- [bot/services/menu.py](bot/services/menu.py) — `send_main_menu(greeting=...)`.
- [db/repositories/user_repo.py](db/repositories/user_repo.py) — `get_or_create` через `pg_insert(...).on_conflict_do_nothing(...)`.
- [tests/unit/test_ai/test_svg_renderer.py](tests/unit/test_ai/test_svg_renderer.py) — snapshot-тесты эталонной карты.
- `/tmp/last_chart.svg` — последний рендер из бота (если был запуск с `BAZI_DEBUG_DUMP_SVG=1`).
- `/tmp/v15-arrows.png` — последний эталонный рендер прямой генерации.

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

**0. Подобрать незакоммиченную работу.** Сессия 2026-05-07 (третья половина) НЕ закоммичена — `git status` покажет правки в `ai/svg_renderer.py`, `web/templates/chart.svg.j2`, `bot/routers/birth_data.py`, `bot/services/menu.py`, `db/repositories/user_repo.py`, `tests/unit/test_ai/test_svg_renderer.py`, `MASTER.md`, `tasks.md`. Прочитать секцию «Сессия 2026-05-07 (третья половина)» выше — там вся карта правок.

**1. Live-проверка фиксов в Telegram.** Бот запущен (PID 88772 на момент закрытия сессии) с `BAZI_DEBUG_DUMP_SVG=1`. Старые карты юзера 545371253 удалены из БД. Сделать /start, проверить пункты из чек-листа в «Остаются на следующую сессию».

**2. Закоммитить сессию** (если live-тест ОК). Логические группы перечислены выше.

**3. Калькулятор 2.1.6 — недетерминированность.** **Это блокер для AI-оркестратора:** запускать LLM-консультации поверх нестабильного calculate_chart() бессмысленно. См. tasks.md → 2.1.6.

**После 2.1.6 — раздел 1.8 «AI Оркестратор» (Wave B):**
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

1. **`git status` + `git diff --stat`** — увидеть незакоммиченные правки сессии 2026-05-07 (третья половина). HEAD = `47af9f9`, но рабочее дерево содержит фиксы из последней сессии.
2. **MASTER.md** (этот файл) — общий статус, прогресс, секция «Сессия 2026-05-07 (третья половина)» с разбором каждой правки.
3. **[tasks.md](tasks.md)** — backlog с `[x]` отметками + новый пункт **2.1.6 КРИТИЧНО** про недетерминированность калькулятора.
4. **`/tmp/last_chart.svg` и `/tmp/v15-arrows.png`** — последний рендер из бота (если бот всё ещё запущен) и последний эталон прямой генерации.
5. **[.cursor/rules/vision.mdc](.cursor/rules/vision.mdc)** + **[conventions.mdc](.cursor/rules/conventions.mdc)** + **[workflow.mdc](.cursor/rules/workflow.mdc)** — обязательное чтение перед бизнес-кодом.
6. **doc/research/** — справочники по Бацзы для дальнейших задач калькулятора.
7. `git log --oneline -10` — последние коммиты для быстрой ориентации.

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
