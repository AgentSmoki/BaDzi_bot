# База знаний учителя

Сюда складываются учебные материалы по БаЦзы от твоего учителя.
Каждый файл — `.md` с YAML-frontmatter; loader парсит frontmatter,
строит keyword-индекс и подмешивает релевантные файлы в LLM payload
как `[KNOWLEDGE]...[/KNOWLEDGE]` блок.

## Структура папок

```
База/teacher/
├── L1_foundational/        — основы (стихии, инь-ян)
├── L2_atoms/               — стволы + ветви
│   ├── stems/              — 10 небесных стволов (по файлу на ствол)
│   └── branches/           — 12 земных ветвей (по файлу на ветвь)
├── L3_combinations/        — скрытые стволы + 10 Богов
│   ├── hidden_stems/
│   └── ten_gods/
├── L4_interactions/        — взаимодействия 合沖刑害破
├── L5_stars/               — Шэнь Ша (60+ звёзд)
├── L6_structures/          — 25 классических 格局
├── L7_predictive_patterns/ — эвристики мастера (САМОЕ ВАЖНОЕ)
│   ├── relationships/
│   ├── career/
│   ├── health/
│   ├── wealth/
│   ├── life_path/
│   └── timing/
├── _audio_transcripts/     — текстовые транскрипты аудиоуроков
└── _chart_examples/        — разборы конкретных карт от учителя
```

## Frontmatter каждого .md

Обязателен YAML-frontmatter (между `---`):

```markdown
---
level: L7                                # L1..L7
topic: relationships                     # категория (см. подпапки L7)
title: Сигналы брака через Цветок Персика
related_concepts:                        # keywords для retrieval
  - taohua
  - day_master_strength
  - zheng_cai
applicable_when:                         # когда правило применимо
  - dm_yin_water
  - taohua_in_day_or_year
source: lesson_2024_03_15                # откуда (provenance)
source_authority: 9                      # 1-10, 10 = прямая цитата учителя
last_updated: 2026-05-17
---

# Сигналы брака через Цветок Персика

## Принцип
…текст урока…

## Эвристика
Если в карте Y/D пилларах присутствует 桃花-ветвь …

## Примеры
1. Карта Дин-Огонь Инь, 1985 …
```

## Workflow для добавления материала

1. Конспектируешь урок учителя (или просишь его написать прямо в репо).
2. Создаёшь `.md` в правильной подпапке.
3. Заполняешь frontmatter — особенно `related_concepts` (это что включает
   retrieval).
4. `git add` + `git commit` + `git push`.
5. На проде через `rsync` файл попадёт автоматически — loader пересчитает
   индекс при следующем запросе.

## Retrieval (как сейчас работает)

1. Пользователь задаёт вопрос → `ai/knowledge_loader.py` извлекает
   ключевые слова (regex по словарю Бацзы-терминов).
2. Lookup в keyword-индексе → топ-N файлов (приоритет по
   `source_authority`).
3. Файлы вставляются в `[KNOWLEDGE]...[/KNOWLEDGE]` блок user-message.
4. LLM получает релевантные эвристики учителя как опору для ответа.

**Это упрощённая версия (без KuzuDB).** Когда корпус разрастётся
до >30 файлов — апгрейдим до полного fractal RAG-Graph по
[~/.claude/plans/badzi-fractal-rag-graph.md](../../.claude/plans/badzi-fractal-rag-graph.md).

## Ограничения версии MVP

- Keyword retrieval (не семантический) — пропустит концепт если он
  не упомянут в `related_concepts` дословно.
- Топ-3 файла по релевантности — может быть слишком мало для сложных
  вопросов.
- Полный текст файла подгружается без чанкинга — большие файлы (>5KB)
  лучше разбивать на несколько меньших с пересекающимися
  `related_concepts`.

## Приватность

`База/teacher/` в git. Если материалы конфиденциальны (NDA с учителем,
платный курс) — обсудить с Богданом перевод в git LFS + private remote
ИЛИ исключение из rsync на прод (тогда индекс не работает в проде).
