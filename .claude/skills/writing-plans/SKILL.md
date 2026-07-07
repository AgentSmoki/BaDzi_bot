---
name: writing-plans
description: Create a detailed plan before coding any new BaDzi_bot feature — handlers, Calculator extensions, AI prompts, subscription tiers, Playwright templates, KuzuDB knowledge base
---

# Writing Plans

## Железное правило

**ЗАПРЕЩЕНО писать бизнес-логику без прочтения 3 .mdc файлов + согласованного плана.**

---

## Когда использовать

- Новый aiogram handler или FSM (команда, callback, inline-меню)
- Расширение Calculator (новый столп, новый тип взаимодействия)
- Изменение AI-промпта / системного промпта Анастасии
- Новый тариф или изменение subscription flow
- Изменение схемы БД (SQLAlchemy модель + Alembic миграция)
- Новый шаблон Playwright карты
- Обновление KuzuDB knowledge base (новые концепты Ба Цзы)
- Любое изменение затрагивающее >2 файлов

---

## Формат плана

```
## Фича: [название]
**Цель:** одно предложение — что должно работать после
**Затронутые файлы:**
  - bot/handlers/...
  - calculator/...
  - ai/...
  - db/models.py + migrations/
**Зависимости:** что нужно сначала

### Задача 1 — [название]
**Файл:** путь/к/файлу.py
**Слой:** calculator (stateless) / ai / bot / db / adapters
**Что:** конкретное изменение
**Тест:** pytest tests/unit/... или tests/integration/...
**Проверка:** конкретная команда или grep

### Задача N — Деплой
**rsync:** да/нет (всегда да если меняли .py файлы)
**docker compose build:** да (если менялись deps или Dockerfile)
**Миграция:** alembic upgrade head (если меняли модели)
**Проверка:** verification-before-completion чеклист
```

---

## Типовой порядок задач BaDzi_bot

```
1. Если нужна БД: SQLAlchemy модель → Alembic миграция
2. Если нужен Calculator: чистая функция (ChartInput → ChartOutput)
   + unit-тест (напрямую, без мока)
3. Если нужен AI: промпт в ai/prompts/ → тест через respx/pytest-httpx
4. Handler (aiogram Router + команды/callbacks)
5. Если нужна карта: Playwright шаблон + integration тест
6. Регистрация в bot/main.py
7. Деплой: rsync → build → up → verify
```

---

## Правила написания задач

1. **Одна задача = один файл** (кроме связанных пар типа model + migration)
2. **Calculator никогда не мокировать** — детерминирован, тестировать напрямую
3. **LLM вызовы** — мокировать через `respx` / `pytest-httpx`
4. **Задача выполнима изолированно** (кроме явных зависимостей)
5. **Деплой — отдельная финальная задача** с явным чеклистом

---

## Анти-паттерны

- ❌ «Это простая правка» без плана — если >2 файлов, нужен
- ❌ Calculator с side effects — он должен быть stateless
- ❌ Хардкодить модель LLM — читать из Redis `llm:active_model`
- ❌ Пропустить Alembic при изменении моделей — таблица не обновится в prod
