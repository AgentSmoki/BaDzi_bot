# BaDzi Bot

Telegram-бот по китайской метафизике Ба Цзы (BaZi): строит карту рождения по дате/времени/месту и даёт AI-консультацию с выбором школы интерпретации.

Русскоязычный продукт с платными консультациями (Telegram Payments / ЮKassa). Карта считается детерминированным калькулятором, интерпретацию даёт LLM поверх RAG-базы знаний с несколькими стилями разбора.

## Возможности

- **Калькулятор Ба Цзы** — четыре столпа, элементы, взаимодействия ветвей (детерминированный, покрыт тестами).
- **AI-консультация** через LLM (OpenRouter) с несколькими школами интерпретации (классическая / современная / авторская).
- **RAG** поверх базы знаний (KuzuDB) — извлечение релевантных фрагментов методологии под запрос.
- **Рендер карты** в изображение через Playwright (SVG-шаблон → PNG).
- **Платежи** — Telegram-native payments (ЮKassa), тарифы и подписки.
- **Наблюдаемость** — трейсинг LLM-вызовов (Langfuse), миграции Alembic.

## Стек

Python 3.12 · aiogram · SQLAlchemy (async) + PostgreSQL + Alembic · OpenRouter (LLM) · KuzuDB (RAG) · Playwright · YooKassa · Docker Compose · pytest + pre-commit + GitHub Actions CI.

## Архитектура

```
Telegram (aiogram)
   ├─ calculator/        детерминированный расчёт карты Ба Цзы (+ тесты)
   ├─ ai/                оркестратор LLM: промпты, школы, RAG, temporal context
   ├─ knowledge/         ингестор базы знаний (PDF → чанки → KuzuDB)
   ├─ web/               рендер карты (Playwright, SVG-шаблоны)
   ├─ db/ + migrations/  SQLAlchemy async + Alembic
   └─ bot/routers/       хендлеры: консультация, платежи, прогнозы
```

## База знаний — исключена из публичного репозитория

RAG-корпус (`База/`, KuzuDB-граф) — проприетарный контент и в публичный репозиторий не входит. Код ингестора (`knowledge/ingest/`) и промпты школ (`ai/prompts/`) опубликованы; сам корпус — нет. Бот в этом виде показывает инженерию (расчёт, оркестрация LLM, платежи, CI), но для полноценной работы требует своей базы знаний.

## Быстрый старт

```bash
git clone https://github.com/AgentSmoki/BaDzi_bot.git
cd BaDzi_bot

cp .env.example .env
# заполнить .env (BOT_TOKEN, OPENROUTER_API_KEY, DATABASE_URL, ЮKassa и т.д.)

docker compose up -d       # PostgreSQL + бот
```

Тесты и линт:
```bash
pip install -e ".[dev]"
pytest
pre-commit run --all-files
```

## Лицензия

MIT — см. [LICENSE](LICENSE). Лицензия распространяется на код; проприетарная база знаний в репозиторий не входит.
