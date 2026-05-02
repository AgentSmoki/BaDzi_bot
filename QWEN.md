# BaDzi Bot — Project Context

## Project Overview

**BaDzi Bot** is a Telegram AI-consultant for BaZi (四柱命理, Four Pillars of Destiny) — a traditional Chinese metaphysical system that analyzes personality, life cycles, and destiny based on birth data. The bot combines high-precision astronomical calculations with multi-model AI orchestration to provide personalized consultations.

**Developer:** Богдан
**Status:** Development phase (documentation complete, code not yet started)
**Version:** 3.0

### What the Bot Does

1. **Collects birth data** (date, time, city, gender) via Telegram FSM dialog
2. **Calculates a full BaZi chart** using a high-precision Python calculator (Swiss Ephemeris, JPL DE431, True Solar Time)
3. **Generates interactive HTML visualization** (FastAPI + Jinja2 + HTMX + Chart.js)
4. **Provides AI consultations** through a multi-model AI ensemble (Claude Sonnet + Qwen 3.6 + Kimi) via LiteLLM
5. **Monetizes** through a Pro subscription (Free: 3 questions/day, Pro: unlimited)

### Key Architectural Principles

- **Domain-Driven Design (DDD):** strict separation of business logic (BaZi calculation) from transport layers (Telegram, HTTP API)
- **Calculator is stateless:** takes `datetime + coordinates + tz`, returns a standardized JSON with the full chart
- **AI only interprets, never calculates:** chart calculation is deterministic Python code; AI receives structured data and provides analysis
- **Multi-model AI:** Claude Sonnet (primary, Russian language), Qwen 3.6 (Chinese metaphysics), Kimi (verification of classical school nuances)

---

## Tech Stack

| Category | Technology |
|----------|-----------|
| **Language** | Python 3.11+ |
| **Bot** | aiogram 3.x (async) |
| **Web** | FastAPI + Jinja2 + HTMX |
| **ORM** | SQLAlchemy 2.0 (async) |
| **Migrations** | Alembic |
| **Database** | PostgreSQL (production), UUID primary keys |
| **Cache** | Redis (FSM, sessions, rate limiting, feature flags) |
| **AI Aggregator** | LiteLLM |
| **AI Models** | Claude 3.5 Sonnet, Qwen 3.6 (DashScope), Kimi (Moonshot) |
| **Astronomy** | pyswisseph (JPL DE431) |
| **Geo** | geopy + GeoNames, timezonefinder, pytz + TZ Database |
| **Task Queue** | TaskIQ (background AI generation) |
| **LLM Monitoring** | Langfuse (self-hosted) |
| **Hosting** | Railway |
| **Containerization** | Docker + docker-compose |
| **CI/CD** | GitHub Actions |
| **Linting** | ruff + mypy + pre-commit |
| **Testing** | pytest + pytest-asyncio (target: 80%+ coverage for calculator/) |
| **Logging** | structlog + trace_id middleware |

---

## Project Structure (Planned)

```
BaDzi_bot/
├── bot/                          # Telegram bot layer (aiogram)
│   ├── main.py                   # Entry point
│   ├── config.py                 # Pydantic Settings
│   ├── routers/                  # start, consultation, chart, profile, ...
│   ├── middlewares/              # db_session, user, tracing
│   ├── keyboards/                # Inline keyboards
│   ├── states.py                 # FSM states
│   └── filters.py                # Magic filters
│
├── calculator/                   # Pure BaZi core (stateless, DDD)
│   ├── models.py                 # Pydantic models (ChartInput, ChartOutput)
│   ├── swiss.py                  # pyswisseph integration
│   ├── solar_terms.py            # 24 solar terms (Цзе Ци)
│   ├── true_solar_time.py        # TST: LMT + EoT + DST
│   ├── pillars.py                # 4 pillars generation (年月日時)
│   ├── hidden_stems.py           # Hidden stems (3 schools)
│   ├── ten_gods.py               # 10 Gods mapping
│   ├── interactions.py           # 合沖刑害破 (combinations, clashes, punishments, harms, destructions)
│   ├── luck_pillars.py           # Luck pillars (Да Юнь) to the minute
│   ├── symbolic_stars.py         # 50-90 Shen Sha (symbolic stars)
│   ├── auxiliary.py              # Ming Gong (Life Palace), Tai Yuan (Conception Pillar)
│   └── day_master.py             # Day Master strength, useful/harmful deity
│
├── ai/                           # AI Orchestrator
│   ├── orchestrator.py           # LiteLLM service
│   ├── router.py                 # Semantic intent router
│   ├── fallback.py               # Fallback between models
│   ├── synthesis.py              # Response synthesis
│   ├── context.py                # Context management (history, memory)
│   └── prompts/                  # System prompts
│
├── web/                          # FastAPI — visualization
│   ├── main.py                   # Entry point
│   ├── routes/                   # chart, api, telegram_webapp
│   ├── templates/                # Jinja2 + HTMX
│   └── static/                   # CSS, JS (Chart.js)
│
├── db/                           # Database
│   ├── models.py                 # SQLAlchemy (User, Chart, Consultation, Subscription, Event)
│   ├── engine.py                 # Async engine
│   └── repositories/             # User, Chart, Consultation, Subscription
│
├── tasks/                        # TaskIQ background tasks
├── monitoring/                   # Langfuse integration
├── migrations/                   # Alembic migrations
├── tests/                        # pytest (unit, integration, e2e)
├── docs/                         # MkDocs (BaZi algorithms documentation)
├── .github/workflows/ci.yml      # CI/CD
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
├── .env.example
└── MASTER.md
```

---

## Key Entities (Database)

| Entity | Description | Key Fields |
|--------|-------------|------------|
| **User** | Telegram user | `id` (UUID), `telegram_id`, `locale`, `created_at` |
| **Chart** | BaZi chart | `id` (UUID), `user_id`, `birth_datetime_utc`, `lat/lon`, `chart_data` (JSONB), `early_rat`, `has_birth_time` |
| **Consultation** | AI consultation log | `id` (UUID), `user_id`, `chart_id`, `model_used`, `prompt_tokens`, `completion_tokens`, `cost_usd`, `latency_ms`, `trace_id` |
| **Subscription** | User subscription | `id` (UUID), `user_id`, `plan`, `status`, `daily_questions_used`, `expires_at` |
| **Event** | Life event (for rectification) | `id` (UUID), `chart_id`, `event_date`, `event_type` |

---

## Building and Running (Planned)

### Local Development

```bash
# Clone and install
git clone <repo>
cd BaDzi_bot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# Copy and configure env
cp .env.example .env
# Edit .env with your API keys

# Start with docker-compose
docker-compose up -d

# Or run services individually
# Database + Redis are in docker-compose
python -m bot.main          # Telegram bot
uvicorn web.main:app --reload  # FastAPI web server
taskiq worker start         # Background worker
```

### Code Quality

```bash
# Lint + format
ruff check .
ruff format .

# Type checking
mypy .

# Tests
pytest --cov=calculator --cov=ai
```

### Git Workflow

```bash
# Standard flow (GitHub Flow)
git checkout -b feature/my-feature
# ... work, commit ...
ruff check . && ruff format . && mypy . && pytest
git add . && git commit -m "feat: description"
git push origin feature/my-feature
# Open PR → code review → merge to main
```

**Important:** Always follow this order for syncing code:
1. `git add .`
2. `git commit -m "description"`
3. `git pull` (to not lose others' work)
4. `git push`

---

## Development Conventions

- **Strict typing:** all functions with type hints, `mypy --strict`
- **Docstrings:** Google style for all modules, classes, public functions
- **Commit messages:** Conventional Commits (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`)
- **Pre-commit hooks:** ruff check + ruff format + mypy
- **Test coverage:** 80%+ for `calculator/`, 60%+ for `bot/`
- **No `!` in Anastasia's responses:** enforced in validation code
- **PII masking in logs:** real names, usernames, exact coordinates are never logged
- **Trace ID:** every Telegram update gets a UUID trace_id propagated through all layers

---

## Key Documentation Files

| File | Description |
|------|-------------|
| `MASTER.md` | Master project document — overview, stack, architecture, roadmap |
| `doc/vision.md` | **Technical Vision v3.0** — full technical specification (12 sections) |
| `doc/Создание высокоточного калькулятора БаЦзы.md` | BaZi calculator architectural standards (Swiss Ephemeris, TST, Shen Sha, Da Yun) |
| `product_idea.md` | Business idea — problem, solution, target audience, monetization, risks |
| `База/ba_zi_prompt_anastasia_v2.md` | System prompt for Anastasia (68 KB) — full Zi Ping methodology |
| `База/Основы Ба Цзы .pdf` | BaZi fundamentals (PDF) |

---

## Roadmap

| Phase | Timeline | Focus |
|-------|----------|-------|
| **Phase 1 — MVP** | Mar-Apr 2026 | Project structure, DB models, FSM, pyswisseph, TST, calculator (4 pillars, DM, 10 Gods), LiteLLM (Claude), consultation handler, limits, subscription, Docker, CI/CD, Railway deploy |
| **Phase 2 — Expansion** | May-Jun 2026 | 24 solar terms, Luck pillars, all interactions, 3 hidden stem schools, 50-90 stars, Ming Gong/Tai Yuan, Qwen + Kimi, AI router, synthesis, fallback, Langfuse, TaskIQ |
| **Phase 3 — Visualization** | Q3 2026 | FastAPI, Jinja2 + HTMX, Chart.js, color coding, interactive tooltips, unique tokens, Telegram Mini App, embedded chat |
| **Phase 4 — Growth** | Q4 2026 | Daily forecasts, referral program, multi-language, interpretation cache, A/B tests, vector memory (pgvector), birth time rectification |
