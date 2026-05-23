# Схема по слоям при выборе школы (Wave 7 Phase 2+4+5)

> **Цель документа:** explain end-to-end путь от нажатия «Задать вопрос» до текста ответа Анастасии — где какие .md файлы подтягиваются, кто за что отвечает, почему 3 школы дают разные ответы (или не дают — известное ограничение).
>
> **Аудитория:** разработчик (понимать что менять), Богдан (понимать почему ответ выглядит так, а не иначе), сенсей (видеть какие алгоритмы реально доезжают до LLM).

---

## Часть 1. Карта файлов prompts/

```
ai/prompts/
├── base.md                          ← Universal core: персона, стиль, glossary, эмодзи,
│                                       расшифровка иероглифов, этика. ВСЕГДА в system prompt.
├── base_classic.md                  ← School overlay: методика Цзы Пин (Юань Хай Цзы Пин).
├── base_edoha.md                    ← School overlay: методика Мастера ЭдоХа.
├── base_modern.md                   ← School overlay: синтез + язык психологии.
├── anastasia_system.md              ← Legacy 39 KB бэкап. Не используется в Wave 6+ flow,
│                                       подключается только если `skill_router_enabled=False`.
├── skill_router_system.md           ← Шаблон для fast-router LLM (катаlog из 6 skills).
├── birth_extract_system.md          ← Для smart-entry парсера данных рождения.
└── algorithms/                      ← ПОКА drafts для людей, НЕ runtime.
    ├── risk_assessment.md           ← Body уже встроен в ai/skills/risk.md (Phase A).
    ├── opportunity_window.md        ← Phase 4 draft. НЕ интегрирован.
    ├── relationships_match.md       ← Phase 4 draft. НЕ интегрирован.
    ├── career_alignment.md          ← Phase 4 draft. НЕ интегрирован.
    ├── decision_chain.md            ← Phase 4 draft. НЕ интегрирован.
    ├── health_diagnostics.md        ← Phase 4 draft. НЕ интегрирован.
    └── term_unpack.md               ← Phase 4 draft. НЕ интегрирован.

ai/skills/
├── work.md                          ← Skill body для skill=work
├── relationships.md                 ← Skill body для skill=relationships
├── health.md                        ← Skill body для skill=health
├── time.md                          ← Skill body для skill=time
├── risk.md                          ← Skill body для skill=risk (Phase A — 3-vs-1 inside!)
└── default.md                       ← Skill body для skill=default (fallback)
```

**Главное правило:**

- **base.md + base_<school>.md** = system prompt (что Анастасия знает о себе)
- **skills/<name>.md** = `[SKILL]` секция в user prompt (как разбирать конкретный домен)
- **algorithms/*.md** = ДОКУМЕНТЫ для людей. **НЕ доезжают до LLM** напрямую. Исключение: `risk_assessment.md` — его body был перенесён в `ai/skills/risk.md` (Phase A).

---

## Часть 2. Полный путь от клика до ответа

### Шаг 1 — User кликает «Задать вопрос по карте»

`bot/routers/consultation.py::handle_ask_pressed`:
1. Загружает активную карту через `_resolve_active_chart`
2. Ставит FSM → `ConsultationState.choosing_school`
3. Шлёт «Какой подход вам ближе?» + `school_selector_kb()` (3 кнопки)

### Шаг 2 — User кликает кнопку школы

`bot/routers/consultation.py::handle_school_chosen`:
1. Парсит callback `school:classic|edoha|modern` через `_parse_school`
2. Сохраняет в FSM data: `chosen_school = "edoha"` (например)
3. Ставит FSM → `waiting_question`
4. Шлёт «Школа 🌀 Мастер ЭдоХа — отвечу через накопленные силы и метафоры поля. Напишите вопрос:»

### Шаг 3 — User пишет вопрос

`bot/routers/consultation.py::handle_question` → `_process_question_after_guards`:
1. Free-question guard проверка
2. Читает `chosen_school` из FSM data
3. Если `skill_router_enabled` (default True) — вызывает `select_skill(question, chart, history)`

### Шаг 4 — Fast skill-router (LLM #1)

`ai/skill_router.py::select_skill`:
- **System prompt:** `ai/prompts/skill_router_system.md` (~120 строк, шаблон с `{catalog}`)
- **{catalog}** заменяется на список 6 skill descriptions из `ai/skills/<name>.md::frontmatter::description`
- **Модель:** `yc_fast_model = qwen3.6-35b-a3b`, `max_tokens=4000`
- **Output:** JSON `SkillSelection{skill, confidence, clarifying_questions, needs_partner_chart, concept_hints, reason}`

Результат для «Какой опасный месяц 2026?»:
```json
{"skill": "risk", "confidence": 0.95, "concept_hints": ["六冲", "流月地支", "3-vs-1"], ...}
```

### Шаг 5 — Branch на clarifying / partner / straight

- **Если `clarifying_questions != []`** → FSM `collecting_clarifications`, спрашиваем по одному
- **Если `needs_partner_chart` + нет partner_chart_id** → показываем кнопку «Добавить партнёра»
- **Иначе** → straight to main LLM (Шаг 6)

### Шаг 6 — `_continue_consultation_with_skill`

Этот метод собирает финальный prompt и зовёт main LLM. **Ключевые точки:**

```python
# A) System prompt — точка разветвления #1 по школе
if skill_spec is not None:
    system_prompt = load_base_prompt(school=chosen_school)
    # ↑ Возвращает: base.md + "\n\n---\n\n" + base_<chosen_school>.md
else:
    system_prompt = load_system_prompt()  # legacy 39 KB

# B) compose_messages собирает user-body
messages = compose_messages(
    system_prompt=system_prompt,        # ← school overlay уже внутри
    chart=chart_data,
    question=original_question,
    history=history,                    # ← последние 20 messages из Redis
    skill_spec=skill_spec,              # ← ai/skills/<name>.md body
    partner_chart=partner_chart_data,
    clarifications=clarifications,
    concept_hints=concept_hints,        # ← из skill_router
    master_meeting_summaries=...,
    school=chosen_school,               # ← точка разветвления #2 для RAG
)

# C) Main LLM call
answer = await chat_with_fallback(messages, intent=decision.intent)
```

### Шаг 7 — `compose_messages` собирает user-body (порядок секций)

```
1. [BAZI_DATA]               ← chart_block (одинаково для всех школ)
2. [PARTNER_CHART]?          ← если есть
3. [CURRENT_MOMENT]?         ← если временной вопрос (через ai.router.route)
4. [CALENDAR_SELECTION]?     ← если 择日-запрос (через ai.calendar_parse)
5. [SKILL: <name>]           ← body из ai/skills/<name>.md (через skill_spec)
6. [CLARIFICATIONS]?         ← Q→A пары если были
7. [KNOWLEDGE]               ← ★ ТОЧКА РАЗВЕТВЛЕНИЯ #2 по школе ★
8. [PERSONAL_MASTER_NOTES]?  ← W5e summaries master-meetings
9. [INSTRUCTIONS]            ← INSTRUCTION_PREFIX (4-section output rules)
10. [QUESTION]               ← user text
```

### Шаг 8 — Точка #2: RAG с school filter

`compose_messages` вызывает:
```python
load_knowledge_for_question(question, concept_hints=concept_hints, school=chosen_school)
```

Дальше:
1. `extract_concepts(question)` — vocab match (русские/китайские термины из 288 концептов в графе)
2. `extract_search_tokens(question)` — Russian-stem токены (len ≥ 4)
3. Union с `concept_hints` от skill_router
4. `retrieve_nodes(concepts, title_tokens, school="edoha")` →
   ```cypher
   MATCH (n:Node)
   WHERE n.topic <> 'stub'
     AND (n.school IS NULL OR n.school IN ['universal', 'edoha'])
   UNWIND n.related_concepts AS c
   WITH n, c WHERE c IN $concepts
   ...
   ```
5. Возвращает top-5 нод + 1-hop typed-edge expansion
6. `format_knowledge_block(nodes)` → `[KNOWLEDGE]` body (≤15000 chars)

**Текущее распределение KG в проде:** 14 classic + 32 universal + 0 edoha + 0 modern.
- При выборе **classic** → доступны 14 classic + 32 universal = 46 docs
- При выборе **edoha** → доступны 0 edoha + 32 universal = 32 docs
- При выборе **modern** → доступны 0 modern + 32 universal = 32 docs

→ **Edoha и modern сейчас retrieve из одной выборки.** Различия будут после Phase 5.4 (ingest сенсея).

### Шаг 9 — Main LLM (Qwen3.6-35B-A3B / Claude fallback)

`chat_with_fallback` зовёт `chat(provider="yc", model="gpt://<folder>/qwen3.6-35b-a3b/latest", messages, temperature=0.55, max_tokens=dynamic)`. Получает text response.

### Шаг 10 — Post-processing + send

1. `_markdown_to_html` — `**bold**` → `<b>bold</b>`
2. `_split_for_telegram(text, 4000)` — разбивка длинного ответа
3. `bot.send_message` для каждого chunk
4. `history_store.append` + `consultation_repo.create` + `logger.info("consultation.completed", school, skill, ...)`

---

## Часть 3. Что ДЕЙСТВИТЕЛЬНО меняется между школами

| Слой | classic | edoha | modern |
|---|---|---|---|
| **base.md** (universal core) | Одинаково | Одинаково | Одинаково |
| **base_<school>.md** (overlay) | base_classic.md (учебник Цзы Пин) | base_edoha.md (3-vs-1 + шахматы + военные аналогии) | base_modern.md (архетипы + психология) |
| **skill body `risk.md`** (если router выбрал risk) | ⚠️ ОДИНАКОВО — body жёстко школо-привязан к ЭдоХа | ⚠️ ОДИНАКОВО | ⚠️ ОДИНАКОВО |
| **skill body `work/relationships/health/time/default.md`** | Одинаково | Одинаково | Одинаково (skills сейчас школо-нейтральны кроме risk) |
| **[KNOWLEDGE] RAG filter** | universal + 14 classic (46 docs) | universal + 0 edoha = 32 docs | universal + 0 modern = 32 docs |
| **[INSTRUCTIONS]** (output format) | Одинаково | Одинаково | Одинаково (4 раздела) |

**Итог:** реально меняются только **2 слоя** — `base_<school>.md` overlay и `[KNOWLEDGE]` фильтр.

---

## Часть 4. Где находятся 6 драфтов алгоритмов из Phase 4

**ПОКА — НИГДЕ в runtime.** Это документы для людей (тебя, сенсея, разработчика).

Текущее состояние:
- ✅ `ai/prompts/algorithms/risk_assessment.md` → body перенесён в `ai/skills/risk.md` → **доезжает до LLM** через `[SKILL: risk]` секцию когда router выбирает skill=risk.
- 📄 `opportunity_window.md`, `relationships_match.md`, `career_alignment.md`, `decision_chain.md`, `health_diagnostics.md`, `term_unpack.md` — **не интегрированы**. Лежат как reference для ревью.

### Опции интеграции этих 6 драфтов (нужно решение)

**Опция A: каждый алгоритм → свой skill**
- Создаём `ai/skills/opportunity.md`, `decision.md`, `term.md` и т.д.
- Расширяем `SkillName` Literal до 12 значений
- Расширяем few-shot в `skill_router_system.md` чтобы router выбирал точнее
- ➕ Чистая семантика, router сам подбирает алгоритм
- ➖ Каталог раздувается, router сложнее принимает решение между похожими skills

**Опция B: алгоритмы → embedded в `base_edoha.md`**
- Body каждого алгоритма копируется в `base_edoha.md` (~14 KB → 50+ KB)
- Когда юзер выбрал edoha — LLM получает ВСЕ алгоритмы в system prompt и сам выбирает уместный
- ➕ Без раздутия skill router, edoha = «полная edoha-методология сразу»
- ➖ Промпт раздувается, prompt-caching менее эффективен, LLM может смешивать алгоритмы

**Опция C: алгоритмы → conditional injection** (рекомендуется)
- Hard-coded mapping: если `skill=work` и `school=edoha` → инжектим `career_alignment.md` после `[SKILL]`
- `compose_messages` принимает `school + skill_name` и решает какой алгоритм добавить
- ➕ Точечная подача алгоритма, prompt маленький
- ➖ Mapping надо поддерживать, при добавлении нового skill — отдельный mapping update

**Опция D: оставить как документы** (текущее состояние)
- Драфты как reference для людей, в runtime не доезжают
- Когда сенсей утвердит — выберем A/B/C
- ➕ Без обязательств
- ➖ Phase 4 не даёт user-facing value пока не интегрировано

### Связанная проблема: skill `risk.md` body школо-привязан

Сейчас `ai/skills/risk.md` body содержит chain-of-thought 3-vs-1 + военные аналогии — это методология школы ЭдоХа. Когда классическая школа просит про опасный месяц — LLM применяет 3-vs-1 даже под base_classic.md overlay.

**Решения:**

**Опция X: risk.md body → нейтральный дисциплинатор**
- В risk.md остаются: «что анализировать» (приходящие столпы, столкновения, накопленные ветви), «формат ответа» (топ-3, рекомендации, признание школы)
- Конкретный алгоритм (3-vs-1 для edoha vs 六冲+三刑 для classic) переезжает в base_<school>.md
- Это решает оба пункта 3 и 4 архитектурно одним ходом

**Опция Y: per-school risk skills**
- `ai/skills/risk_classic.md` (六冲+三刑 ranking)
- `ai/skills/risk_edoha.md` (3-vs-1 ranking)
- `ai/skills/risk_modern.md` (зоны роста ranking)
- Router возвращает «risk», loader выбирает variant по chosen_school
- Расширение применимо ко всем skill-в-зависимости-от-школы

**Опция Z: оставить как есть**
- risk — это «edoha-specific skill»
- Если хочется классический ответ про опасный месяц — пользователь выбирает classic школу, и **запрещает 3-vs-1 явно** через clarifying_questions или формулировку

---

## Часть 5. Что ещё НЕ работает / не оптимально

1. **LLM concept extraction отсутствует** (Phase 3.5) — sparse retrieval на vocab+stem, может пропускать важные концепты в нестандартных формулировках вопроса. Решение: добавить Qwen3.6 fast extraction → объединить с vocab.

2. **Embeddings отсутствуют** (Phase 2.5) — нет dense vector ranking. Большая часть retrieval опирается на title match + concept overlap. Решение: bge-m3 после миграции на Apache AGE (Q3 2026).

3. **KG для edoha пуст** (Phase 5.4 отложен) — нет личных записей сенсея, поэтому edoha-выборка == universal. Решение: ingest транскрипта сенсея когда у тебя будет файл.

4. **History копится между школами** — если в одном диалоге задать вопрос на classic, потом на edoha — LLM зеркалит свой первый ответ. Workaround: /reset перед сменой школы. Архитектурное: можно добавить auto-clear history при `chosen_school != previous_chosen_school`.

5. **forecast.py не пробрасывает school** — прогнозы (платные и важные даты) идут на чистом base.md без overlay. Решение: добавить параметр school в `generate_daily_forecast` / `generate_monthly_forecast` (но прогноз шлёт scheduler — не знает какая школа у юзера; нужно сохранять default_school в Chart, отложено как 1.18.14).

---

## Часть 6. Диаграмма «один абзац»

```
ВОПРОС ↓
[FSM read chosen_school + chart]
   ↓
[skill_router(Qwen3.6 fast)] → SkillSelection
   ↓
[compose system prompt = base.md ⊕ base_<school>.md]   ← TOUCHPOINT 1 (school overlay)
[compose user prompt:
   chart, partner, current, calendar,
   [SKILL: <name>] body из ai/skills/<name>.md,
   clarifications,
   [KNOWLEDGE] из RAG with school filter,            ← TOUCHPOINT 2 (school filter)
   master meeting notes,
   INSTRUCTIONS, QUESTION
 ]
   ↓
[Qwen3.6-35B-A3B] → text
   ↓
[markdown→HTML, split 4000, send] ↑ ОТВЕТ
```

Из 12-ти слоёв system+user prompt — школа меняет ровно **2**. Всё остальное одинаково. Это и есть причина почему сейчас разница classic vs edoha **есть но слабая**.

---

## Часть 7. Roadmap для усиления различий между школами

1. **Школо-нейтрализация `risk.md`** (Опция X выше) — самый быстрый win
2. **Conditional algorithm injection** (Опция C для 6 драфтов Phase 4) — после X
3. **Ingest сенсея в KG как school=edoha** (Phase 5.4) — даст реально разные [KNOWLEDGE]
4. **LLM concept extraction** (Phase 3.5) — улучшит recall во всех школах
5. **Embeddings bge-m3** (Phase 2.5) — самое долгосрочное

Каждый шаг увеличивает реальное различие между школами на ~15-25%. Сейчас разница ~10-20% (только base overlay) → после всех шагов 70-90% (overlay + школо-точные алгоритмы + школо-специфичный KG).
