---
name: verification-before-completion
description: Mandatory evidence checklist before declaring any BaDzi_bot task done — local tests pass, rsync done, Docker rebuilt, containers running
---

# Verification Before Completion

## Железное правило

**ЗАПРЕЩЕНО говорить «готово», «задеплоено», «исправлено» без доказательств.**

Канонический флоу — **local edit → tests → commit → rsync → rebuild → restart → verify**.
Нарушение любого шага = незавершённое «готово».

---

## Полный деплой-чеклист

```
[ ] 1. Локальные изменения сделаны через Edit/Write (не на VM)
[ ] 2. ruff check . — нет ошибок
[ ] 3. mypy . — нет type errors
[ ] 4. pytest — все тесты зелёные
[ ] 5. git commit сделан (git log --oneline -1)
[ ] 6. rsync выполнен (команда ниже)
[ ] 7. docker compose build bot worker — образ пересобран
[ ] 8. docker compose up -d --no-deps bot worker
[ ] 9. docker compose ps — оба контейнера Up
[ ] 10. docker compose logs bot --tail 20 — нет crash/traceback
[ ] 11. Функциональный тест (если критично)
```

---

## Команды верификации

### Шаг 6 — rsync

```bash
rsync -avz \
  --exclude='.git/' --exclude='.venv/' --exclude='__pycache__/' \
  --exclude='.coverage' --exclude='.DS_Store' --exclude='/.env' \
  --exclude='graphify-out/cache/' --exclude='graphify-out/memory/' \
  -e "ssh -i $HOME/.ssh/id_ed25519 -o IdentitiesOnly=yes" \
  ./ yc-user@130.193.51.15:~/BaDzi_bot/
```

### Шаг 9 — контейнеры живы

```bash
ssh -i ~/.ssh/id_ed25519 yc-user@130.193.51.15 \
  'cd ~/BaDzi_bot && sudo docker compose ps'
```

**Ожидаемый результат:** `bot` и `worker` в статусе `Up`.

### Шаг 10 — нет crash

```bash
ssh -i ~/.ssh/id_ed25519 yc-user@130.193.51.15 \
  'cd ~/BaDzi_bot && sudo docker compose logs bot --tail 20'
```

**Красные флаги:** `Traceback`, `ImportError`, `SyntaxError`, `Error`, `crashed`.

### Миграции (если были изменения в моделях)

```bash
ssh -i ~/.ssh/id_ed25519 yc-user@130.193.51.15 \
  'cd ~/BaDzi_bot && sudo docker compose run --rm --no-deps bot alembic upgrade head'

# Проверить что миграция применена
ssh -i ~/.ssh/id_ed25519 yc-user@130.193.51.15 \
  'cd ~/BaDzi_bot && sudo docker compose run --rm --no-deps bot alembic current'
```

---

## Специфичные проверки по типу изменения

### Изменение Calculator

```bash
# Локально — тест детерминированных вычислений
pytest tests/unit/test_calculator/ -v
# Граничные случаи: дата смены Цзе Ци, полночь, 1984-01-01 (базовый год)
```

### Изменение AI / OpenRouter

```bash
# Проверить что активная модель в Redis корректна
ssh -i ~/.ssh/id_ed25519 yc-user@130.193.51.15 \
  'cd ~/BaDzi_bot && sudo docker compose exec bot redis-cli GET llm:active_model'
```

### Изменение Playwright / карты

```bash
# Локальный smoke-test генерации карты
pytest tests/integration/test_card_generation.py -v
```

### Новый handler

```bash
# Проверить что router зарегистрирован
grep -n "router\|include_router" /Users/admin/Documents/Razarabotka/BaDzi_bot/bot/main.py
```

---

## Server-side hotfix фиксация (исключение из Local-first)

Если hotfix сделан прямо на VM — **обязательно** записать в `MASTER.md → CHANGELOG (server-side hotfixes)`:
- Дата/время UTC
- Какой файл/команда
- Причина + exact diff

И при первой возможности повторить локально, закоммитить, накатить через rsync.

---

## Анти-паттерны

- ❌ `docker compose restart` вместо `build + up` — образ не обновится
- ❌ «rsync прошёл» без rebuild — контейнер запекает образ при build
- ❌ «тесты не нужны для мелкой правки» — Calculator детерминирован, тест покажет regression
- ❌ Проверять логи только после жалобы пользователя — проверять сразу после деплоя
