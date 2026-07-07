# План миграции BaDzi_bot: Yandex Cloud → Timeweb + OpenRouter

> Статус: план, согласован по ключевым решениям 2026-06-16. Две независимые
> дорожки: **(A) AI-провайдер** (только код, тестируется локально) и
> **(B) хостинг** (compose + данные + cutover). Делаем A полностью локально
> и зелёным, потом B.

## Согласованные решения (2026-06-16)

| Роль | Было (YC) | Стало (OpenRouter) |
|---|---|---|
| **Tier 1 — главные ответы** (консультации, база-интерпретация, прогнозы) | Qwen3.6-35B-A3B | **Claude Sonnet 4.6** (`anthropic/claude-sonnet-4.6` — slug сверить в каталоге) |
| **Fast — роутинг/smart-entry/concept/day-image** | Qwen3.6 | **Gemini Flash latest** (`google/gemini-2.5-flash`) |
| **Tier 2 — emergency fallback** | Claude 3.5 Sonnet | рекоменд. **Gemini 2.x Pro** (другая семья — сбой Claude не убивает обе ступени; настраивается в `.env`) |
| Эмбеддинги 1.9.16 | YC Embeddings API | **отложено** (sparse-retrieval остаётся; миграция их не трогает; при возобновлении — bge-m3 ONNX локально, Вариант 2) |
| web наружу | — | **не публикуем** сейчас (Mini App/admin ещё не готовы) |

## Сервер-приёмник
Timeweb VPS (тот же, что TeleTranscribe): `<SERVER_IP>`, SSH alias `tt-timeweb`,
user `admin108`, Cloudflare Tunnel `teletranscribe`, DNS `neuroimpuls.ru` на Cloudflare.
⛔ Не трогать контейнеры/порты/туннель-ingress TeleTranscribe (api/mcp/pay) и
supervisord-группу `tt`. NO worktrees; деструктив — только по «да».

---

## Phase 0 — Подготовка и проверки
1. ✅ **Источник прод-данных установлен (2026-06-16):** прод НЕ использует
   локальный контейнер `db` (он пустой). `DATABASE_URL` смотрит на **Yandex
   Managed PostgreSQL** `rc1a-9luklto6tg5mlcdl.mdb.yandexcloud.net:6432/badzi`
   (SSL). **Источник дампа в Phase 4 = Managed PG, не volume контейнера.**
2. **OpenRouter**: пополнить баланс (теперь через него идёт **весь** трафик).
   Сверить точные slug'и: `anthropic/claude-sonnet-4.6`, `google/gemini-2.5-flash`,
   `google/gemini-2.5-pro`.
3. **Docker Hub**: на `tt-timeweb` `docker login` (rate-limit для `postgres:16-alpine`
   + `python:3.11-slim-bookworm`; `redis:7-alpine` уже на сервере).

## Phase 1 — AI-провайдер: YC → OpenRouter (локально, код)
Новый **ADR-012** (supersedes ADR-009): OpenRouter — единственный провайдер.
- [ai/orchestrator.py](../../ai/orchestrator.py): `Provider = Literal["openrouter"]`;
  удалить `_YC_BASE_URL`, YC-ветку `_get_client` (`Api-Key`/`x-folder-id`).
  Оставить thinking-guard в `_parse_result` (защитный, безвреден для Claude/Gemini).
- [ai/fallback.py](../../ai/fallback.py): `_resolve_tiers()` → оба тира
  `provider="openrouter"`; удалить `_build_model_id`/`gpt://`-URI, модель = slug as-is.
- [ai/skill_router.py](../../ai/skill_router.py), [ai/day_image.py](../../ai/day_image.py),
  [ai/rag/llm_extract.py](../../ai/rag/llm_extract.py), [ai/text_extract.py](../../ai/text_extract.py):
  убрать `gpt://…/latest`, звать `provider="openrouter", model=settings.fast_model`.
  Опц. включить `response_format={"type":"json_object"}` (Gemini Flash надёжно
  отдаёт JSON; regex-fallback `_extract_json` оставить).
- [ai/router.py](../../ai/router.py), [ai/budget.py](../../ai/budget.py): обновить
  комментарии/контекст-окна (Qwen 262k → Claude 200k / Gemini 1M).
- Тесты `tests/unit/test_ai/*`: перевести моки с `provider="yc"`/URI на OpenRouter-slug'и.

## Phase 2 — Config + секреты
- [bot/config.py](../../bot/config.py): rename `yc_primary_model→primary_model`,
  `yc_fast_model→fast_model`, `yc_qwen36_context→primary_context`,
  `openrouter_emergency_model→emergency_model`, `openrouter_claude_context→emergency_context`;
  удалить `yc_ai_api_key`, `yc_ai_folder_id`. Object Storage `yc_*` (не используются
  в коде — boto3/S3 не реализованы, задача 1.7.3 открыта) → optional/удалить.
  `yandex_geocoder_api_key` → optional/убрать (Google+Nominatim хватает).
- [.env.example](../../.env.example) + прод-`.env`: убрать `YC_AI_*`, `YC_*_STORAGE/ACCESS/SECRET`;
  задать `OPENROUTER_API_KEY`, `PRIMARY_MODEL`, `FAST_MODEL`, `EMERGENCY_MODEL`.

## Phase 3 — docker-compose под Timeweb
[docker-compose.yml](../../docker-compose.yml):
- Убрать `ports:` у **db** (5432) и **redis** (6379) — нужны только во внутренней сети.
- **web**: `8000:8000` → `8092:8000`.
- `POSTGRES_PASSWORD` → `${POSTGRES_PASSWORD}` из `.env` (не хардкод `badzi_dev_password`).
  `DATABASE_URL=postgresql+asyncpg://badzi:<pw>@db:5432/badzi`, `REDIS_URL=redis://redis:6379/0`
  (внутренние имена — теперь свои контейнеры вместо Managed).
- **mem_limit**: bot/web/worker `384m`, scheduler `256m`, db `256m`, redis `128m`.
- Запуск отдельным проектом: `docker compose -p badzi up -d` (namespace `badzi_*`).

## Phase 4 — Перенос данных
- **Postgres**: `pg_dump` из **Yandex Managed PG** (Phase 0) → restore в новый
  контейнер `db`. Внутри: User/Chart/Consultation/Subscription/Forecast/Journal/
  MasterMeeting **+ APScheduler jobstore** (прогнозы переживут переезд).
- **KuzuDB**: после `up -d` → `docker compose -p badzi cp knowledge/kuzu_db/. bot:/app/knowledge/kuzu_db/`
  (паттерн 1.9.11; том `kuzu_data`). Источник — локальный `knowledge/kuzu_db/`.
- **Redis**: не мигрируем (FSM/cache/history TTL 24h — эфемерны).
- `alembic upgrade head` для досхемы.

## Phase 5 — Починка TeleTranscribe endpoint
- [bot/config.py](../../bot/config.py): `tt_api_base_url` `http://93.77.187.33:8000`
  (**мёртв** — YC-сервер TT удалён 2026-06-16) → `https://api.neuroimpuls.ru`
  (стабильное имя Cloudflare-туннеля TT). Проверить голосовой флоу (дневник/
  голос-вопрос/встречи) после деплоя.

## Phase 6 — Деплой + cutover
1. Локально зелёные `ruff + mypy --strict + pytest`.
2. `rsync` (абсолютный путь источника) Mac → `<user>@<SERVER_IP>:~/BaDzi_bot/`,
   исключая `.git/.venv/__pycache__/.env/.coverage/graphify-out/{cache,memory}`.
3. `.env` на сервер вручную (`scp` + правки), `docker compose -p badzi build && up -d`.
4. ⚠️ **КРИТИЧНО (урок переезда TT, грабля b):** перед стартом бота на Timeweb
   **остановить бот на YC VM** — два polling-инстанса `@EdoHa_Badzi_bot`
   конкурируют за апдейты. Порядок: stop YC bot → start Timeweb badzi.
5. `web` без tunnel ingress (не публикуем).

## Phase 7 — Верификация
- `docker compose -p badzi ps` healthy; не задеты контейнеры/порты/туннель TeleTranscribe.
- Live-smoke через MCP `@Bogman108` → `@EdoHa_Badzi_bot`: /start → карта (PNG) →
  вопрос на 3 школах (Claude Sonnet 4.6 отвечает, роутер Gemini Flash) →
  голосовой вопрос (TT через `api.neuroimpuls.ru`) → прогноз (scheduler).
- Логи: `provider=openrouter`, нет `gpt://`/YC-ошибок.

## Phase 8 — Документация + вывод Яндекса
- ADR-012 (OpenRouter-only) + ADR-013 (Timeweb co-location, supersede ADR-005/009)
  в [vision.mdc](../../.cursor/rules/vision.mdc); обновить MASTER.md, CLAUDE.md
  (deploy: host/user/`-p badzi`/порты), tasks.md.
- Пометить в [bge_m3_embeddings_plan.md](bge_m3_embeddings.md): Вариант 1 (YC API)
  мёртв → при возобновлении 1.9.16 идём по Варианту 2 (bge-m3 ONNX локально).
- После недели стабильной работы — снести YC VM `130.193.51.15`, Managed PG,
  folder `badzi-bot`, Object Storage.

## Риски / откат
- **Откат**: YC VM держим живым (но с остановленным ботом) ~неделю → откат =
  stop Timeweb bot, start YC bot.
- **Качество ответа**: Claude Sonnet 4.6 ≠ Qwen3.6 — промпты/метафоры калибровались
  под Qwen; нужен live-смок 3 школ, возможна правка `base_*.md`.
- **Стоимость**: см. раздел ниже — Claude дороже Qwen в разы. Главный драйвер —
  22k input-токенов на ответ. **Обязателен prompt caching** (глобальное правило).

---

## Стоимость: реальные данные с прода (замер 2026-06-16)

Из таблицы `consultations` (Managed PG), 75 ответов за 2026-05-16…06-16, 8 юзеров,
все на Qwen3.6 (YC `cost_usd` не отдаёт — берём токены):

| Метрика | prompt_tokens | completion_tokens |
|---|---|---|
| Среднее | **22 209** | **5 721** |
| Медиана | 20 274 | 5 373 |
| p90 | 33 688 | 7 941 |

Только main-вызов (ответ). Полное сообщение = ещё router + concept-extract (мелкие).

**Per-message на Claude Sonnet 4.6** (прайс $3/1M in, $15/1M out — сверить; 90 ₽/$):
- input 22 209 × $3/1M = $0.0666
- output 5 721 × $15/1M = $0.0858
- router+concept (Gemini Flash) ≈ $0.0015
- **≈ $0.154 / сообщение ≈ ~14 ₽** (без кэша)

Base-интерпретация (9 блоков, бесплатно, ~1 раз на карту) ≈ $0.11 ≈ ~10 ₽.

**Проекция (₽/мес, без prompt-кэша, 90 ₽/$):**

| Профиль (вопросов/юзера/мес) | 100 юзеров | 250 | 500 |
|---|---|---|---|
| Лёгкий (5) | ~8 тыс | ~20 тыс | ~41 тыс |
| Средний (15) | ~22 тыс | ~55 тыс | ~110 тыс |
| Тяжёлый (30) | ~43 тыс | ~107 тыс | ~214 тыс |

**Главный рычаг — prompt caching:** ~10-14k input-токенов статичны
(`base_*.md` + INSTRUCTION_PREFIX + skill body, одинаковы между юзерами).
Кэш Anthropic режет вход до ~10% на повторах → реалистично −30-50% к стоимости
сообщения. Обязателен по глобальному правилу проекта.

Доп. рычаги: урезать `[KNOWLEDGE]` бюджет (сейчас 15k chars), укоротить history,
оставить дешёвую модель (Gemini/DeepSeek) для рутинных вопросов и Claude — только
для сложных.
