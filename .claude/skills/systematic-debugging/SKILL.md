---
name: systematic-debugging
description: Root-cause analysis before any fix in BaDzi_bot stack — aiogram, OpenRouter/Kimi, KuzuDB, Playwright, SQLAlchemy async, Docker Compose, rsync deploy
---

# Systematic Debugging

## Железное правило

**ЗАПРЕЩЕНО трогать код до тех пор, пока не найден root cause.**

---

## Фазы отладки (строго по порядку)

### Фаза 1 — Воспроизведение

Зафиксировать точный сбой:
- Какая команда / хендлер / cron вызвал ошибку?
- Точный traceback из логов Docker?
- Воспроизводится локально или только на VM?

```bash
# Логи контейнеров на VM
ssh -i ~/.ssh/id_ed25519 yc-user@130.193.51.15 \
  'cd ~/BaDzi_bot && sudo docker compose logs bot --tail 50'

ssh -i ~/.ssh/id_ed25519 yc-user@130.193.51.15 \
  'cd ~/BaDzi_bot && sudo docker compose logs worker --tail 50'

# Статус контейнеров
ssh -i ~/.ssh/id_ed25519 yc-user@130.193.51.15 \
  'cd ~/BaDzi_bot && sudo docker compose ps'
```

### Фаза 2 — Изоляция по слоям

```
Telegram → aiogram handler → AI orchestrator → OpenRouter API (Kimi 2.6 / Claude fallback)
                                   ↓
                    Calculator (stateless, ChartInput → ChartOutput)
                                   ↓
                    KuzuDB (embedded RAG — GraphRAG запрос)
                                   ↓
                    Playwright → HTML/CSS шаблон → PNG screenshot
                                   ↓
                    Yandex Object Storage → send_photo
```

**OpenRouter / LLM:**
```bash
# Проверить активную модель (хранится в Redis)
ssh -i ~/.ssh/id_ed25519 yc-user@130.193.51.15 \
  'sudo docker compose exec bot redis-cli GET llm:active_model'

# Проверить что OPENROUTER_API_KEY задан
ssh -i ~/.ssh/id_ed25519 yc-user@130.193.51.15 \
  'sudo docker compose exec bot env | grep OPENROUTER'
```

**Calculator (детерминированный — тестировать напрямую):**
```bash
# Локально — не моковать, тестировать напрямую
cd /Users/admin/Documents/Razarabotka/BaDzi_bot
.venv/bin/python3 -c "
from calculator.pillars import calculate_pillars
from calculator.models import ChartInput
import datetime
inp = ChartInput(birth_dt=datetime.datetime(1990, 5, 15, 10, 0), gender='male')
print(calculate_pillars(inp))
"
```

**KuzuDB (embedded):**
```python
# KuzuDB синхронный — в async контексте всегда через run_in_executor
# Если зависание — проверить что нет прямых вызовов из async без executor
# Проверить целостность БД:
import kuzu
db = kuzu.Database('data/graph/')
conn = kuzu.Connection(db)
print(conn.execute("MATCH (n) RETURN count(n)").get_next())
```

**Playwright:**
```bash
# Проверить что браузер установлен в контейнере
ssh -i ~/.ssh/id_ed25519 yc-user@130.193.51.15 \
  'sudo docker compose exec bot python3 -c "from playwright.sync_api import sync_playwright; p = sync_playwright().start(); b = p.chromium.launch(); print(b.version)"'
```

**Docker / деплой:**
```bash
# Локально — убедиться что образ пересобран после изменений
sudo docker compose build bot worker
sudo docker compose up -d --no-deps bot worker

# Проверить что файлы в контейнере свежие (после rsync)
sudo docker compose exec bot ls -la /app/bot/handlers/
```

### Фаза 3 — Гипотеза

Одна конкретная формулировка: _«X потому что Y, проверю через Z»_

Примеры:
- «OpenRouter вернул 429 потому что Kimi 2.6 rate limit — проверю через `llm:active_model` в Redis и fallback на Claude»
- «Playwright упал потому что шаблон Jinja2 генерирует невалидный HTML — проверю локально с test ChartOutput»
- «Calculator вернул неверный столп потому что граница месяца Цзе Ци не учтена — проверю через unit-тест с граничными датами»

### Фаза 4 — Верификация без изменений

Проверить гипотезу локально (ruff + mypy + pytest) без деплоя.

### Фаза 5 — Фикс + подтверждение

```
local fix → ruff check + mypy + pytest → git commit → rsync → docker compose build → docker compose up → verify
```

---

## Типичные failure modes BaDzi_bot

| Симптом | Вероятная причина | Где смотреть |
|---|---|---|
| LLM не отвечает / таймаут | OpenRouter rate limit или Kimi недоступен | Redis `llm:active_model`, OpenRouter статус |
| Карта не генерируется | Playwright сбой или S3 upload упал | `docker compose logs bot`, S3 credentials |
| Неверный Ба Цзы расчёт | Граница Цзе Ци (месяц) или часовой пояс | Calculator unit tests с граничными датами |
| Subscription не работает | Alembic миграция не применена | `alembic current` на VM |
| Бот не отвечает на сообщения | Контейнер упал тихо | `docker compose ps`, `docker compose logs` |
| `ImportError` после деплоя | `rsync` прошёл но `docker compose build` не запущен | Образ содержит старый код — rebuild! |

---

## Анти-паттерны

- ❌ Менять код напрямую на VM — нарушение Local-first правила
- ❌ Мокировать Calculator в unit-тестах — он детерминирован, тестировать напрямую
- ❌ `docker compose restart` без rebuild — образ содержит старый код
- ❌ Хардкодить secrets — только через Settings (Pydantic)
