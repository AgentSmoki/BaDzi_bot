# План реализации: админ-аналитика (1.15)

> Статус: запрошен Богданом 2026-06-10, к реализации.
> Закрывает и расширяет бэклог 1.15.1–1.15.2 (tasks.md → «1.15 Админ-панель»).
> Оценка: Phase 1 ≈ 1 день, Phase 2 ≈ 1 день, Phase 3 (опционально) ≈ 1 день.

## Запрос Богдана (дословно по смыслу)

1. Смотреть количество пользователей.
2. Смотреть статистику пользования и её динамику по дням / неделям / месяцам.
3. Сколько людей задают вопросы.
4. На каких вопросах / моментах люди прекращают пользование и активность (воронка, отток).

## Что уже есть в данных (анализ 2026-06-10)

| Источник | Что даёт аналитике |
|---|---|
| `users` | `created_at` (регистрации), `free_questions_used` (стадия лимита) |
| `charts` | `created_at` (дошёл до расчёта карты), partner-карты, `default_school` |
| `consultations` | `user_id`, `created_at`, **`topic` = имя skill** (work/relationships/health/time/risk/decision/default), `model_used`, токены, `cost_usd`, `latency_ms` — основа метрик активности и «на каких вопросах» |
| `chart_forecast_subscriptions` | `kind`, `price_rub`, `payment_provider` (yookassa / free_dev_bypass), `started_at`/`expires_at`, `chosen_school` |
| `forecast_deliveries` | `sent_at`/`error` — здоровье доставки |
| `journal_entries`, `master_meetings` | engagement-фичи второго порядка |
| `Settings.admin_telegram_id` | гейт доступа — уже в конфиге |

**Чего в данных НЕТ (пробелы):**
- Школа консультации не сохраняется (в `consultations` нет колонки) — аналитика по школам недоступна.
- UI-события не логируются: показ pricing-экрана, клик «Купить», брошенный FSM ввода даты, выбор школы. «Момент прекращения» сейчас восстановим только с точностью до последней записи в БД.
- `users.last_seen` нет — последняя активность выводится через `max(created_at)` по consultations/charts/journal.

## Архитектура

UI — **Telegram `/admin` в боте** (быстро, привычно, ноль новой инфраструктуры). FastAPI-дашборд (1.15.5) — отдельная итерация, если в TG станет тесно. Доступ: фильтр `message.from_user.id == settings.admin_telegram_id` на роутере целиком.

Слои по конвенциям проекта:
- `db/repositories/stats_repo.py` — все агрегаты чистым SQL (`date_trunc`, `count distinct`, оконные ф-ции). Никакой логики в роутере.
- `bot/routers/admin.py` — `/admin` + inline-меню + рендер ответов.
- Графики динамики: текстовая таблица в `<code>`-блоке + **PNG-спарклайн через уже существующий SVG→PNG pipeline** (Jinja2 → CairoSVG → render-pool — стек готов, шаблон `web/templates/stats.svg.j2` ~50 строк).

## Phase 1 — `/admin`: сводка + динамика (≈1 день)

**1.1 Миграция (15 мин):** `consultations.chosen_school VARCHAR(16) NULL` — записывать школу в `ConsultationRepository.create` (consultation.py уже держит `chosen_school` в руках). Без backfill — историю не восстановить, пишем с момента деплоя.

**1.2 `stats_repo.py`:**
- `summary()` → всего юзеров; новых за 1/7/30 дней; юзеров с ≥1 картой; юзеров с ≥1 вопросом; DAU/WAU/MAU (уникальные `user_id` в consultations за период); всего консультаций; активных подписок по kind; выручка `sum(price_rub) where payment_provider='yookassa'` за 30 дней + за всё время; средний latency/cost консультации за 7 дней.
- `timeseries(metric, granularity, periods)` → `date_trunc('day'|'week'|'month', created_at)` для метрик: новые юзеры / новые карты / вопросы / уникальные активные / платежи. Последние N точек (день=14, неделя=12, месяц=12).

**1.3 `bot/routers/admin.py`:**
- `/admin` → сводка + inline-меню: `📈 Динамика` / `🔀 Воронка` / `❓ Вопросы` / `💰 Деньги`.
- `Динамика` → выбор метрики → выбор гранулярности (День/Неделя/Месяц, callback `adm:ts:<metric>:<gran>`) → таблица + PNG-спарклайн.
- `Вопросы` → распределение `topic` (skill) и `chosen_school` за 7/30 дней, топ-период по нагрузке.

**1.4 Тесты:** stats_repo на фейковой сессии (как остальные repo-тесты), handlers через MagicMock; guard «не-админ получает отказ».

## Phase 2 — воронка и отток из существующих таблиц (≈1 день)

**2.1 Воронка стадий** (`funnel(period)` в stats_repo) — конверсия по когорте регистрации:

```
/start (users) → карта построена (charts) → 1-й вопрос (cons ≥1)
  → 2+ вопроса (cons ≥2) → исчерпал 3 бесплатных (free_questions_used ≥ 3)
  → оплатил (подписка yookassa / payment_id) → повторная активность после оплаты
```

Вывод: абсолют + % перехода на каждом шаге, для когорт «эта неделя / прошлая / месяц». Главный ответ на «на каких моментах прекращают»: самый большой провал между стадиями виден сразу.

**2.2 Отток (churn):** юзер «ушёл», если нет активности (consultations/charts/journal) > 7 дней. Группировка ушедших по **последнему событию**:
- ушёл после `/start` без карты;
- построил карту, не задал вопрос (увидел бесплатную интерпретацию и всё);
- задал 1-2 вопроса и ушёл → **распределение `topic`+`chosen_school` последнего вопроса** — «на каких вопросах уходят»;
- упёрся в лимит 3 бесплатных и не оплатил (free_questions_used ≥ 3, платежей нет) — главная точка монетизационной утечки;
- оплатил и ушёл (подписка истекла без продления).

**2.3 «Сколько людей задают вопросы»:** уникальные авторы вопросов за период / все активные за период + среднее вопросов на спрашивающего.

## Phase 3 (опционально, после прогона Phase 1-2) — event-лог для точной воронки (≈1 день)

Существующие таблицы не видят: брошенный ввод даты рождения, показ pricing без покупки, клик «Купить» без оплаты, выбор школы без вопроса. Если Phase 2 покажет большой провал «между таблицами» — добавить:
- Таблица `bot_events (id, user_id, event_type VARCHAR(64), payload JSONB, created_at)` + индекс (event_type, created_at).
- Хелпер `log_event(session, user_id, type, **payload)` — вызовы в ~10 ключевых точках: `start`, `calc_started`, `calc_confirmed`, `interpretation_shown`, `school_selected`, `question_asked`, `pricing_shown`, `pay_clicked`, `payment_success`, `journal_written`. Дёшево: один INSERT в уже открытую сессию хендлера.
- Retention-отчёт D1/D7/D30 по когортам + точная воронка по событиям.
- TTL-очистка: events старше 180 дней — периодический DELETE в scheduler (раз в сутки).

## Verification

- ruff + mypy strict + pytest (Phase 1: ~15 тестов, Phase 2: ~10).
- Live: `/admin` от Богдана (admin_telegram_id) — сводка с реальными цифрами прода; от второго аккаунта — отказ.
- Цифры сводки сверить руками с 2-3 прямыми SQL-запросами на проде.

## Деплой

Стандартный поток: local → tests → commit → rsync → `docker compose build bot` → `up -d --no-deps bot` → `alembic upgrade head` (миграция `chosen_school` в consultations; Phase 3 — вторая миграция `bot_events`). Scheduler пересобирать только в Phase 3 (TTL-очистка).
