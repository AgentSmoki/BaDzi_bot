# `knowledge/ingest/` — Ingestion pipeline (Phase 2)

Превращает markdown-файлы из `База/teacher/` в граф KuzuDB:

```
.md файл → parser → IngestedDoc → extract → triplets → writer → KuzuDB
```

## Запуск

```bash
# Полный ingest всей КБ:
python -m knowledge.ingest

# Только новое/изменённое:
python -m knowledge.ingest --incremental

# Один файл:
python -m knowledge.ingest --file База/teacher/L5_stars/baihu_white_tiger.md

# Парсинг и extract без записи в БД (dry-run):
python -m knowledge.ingest --dry-run

# Список .md без sidecar — кандидаты на subagent-обогащение:
python -m knowledge.ingest --list-pending-extracts
```

Output — JSON-summary в stdout: сколько docs обработано / skipped / edges записано.

## Architecture

| Модуль | Что делает |
|---|---|
| [models.py](models.py) | `IngestedDoc`, `Triplet`, `IngestState`, `REL_KINDS` |
| [parser.py](parser.py) | YAML-frontmatter + body → `IngestedDoc`, sha256 от body для идемпотентности |
| [extract.py](extract.py) | **Hybrid:** sidecar `<file>.triplets.json` (от subagent), иначе heuristic из `related_concepts` |
| [writer.py](writer.py) | MERGE Node + replace outgoing edges в KuzuDB, JSON state-файл |
| [cli.py](cli.py) | argparse + orchestration |

### Идемпотентность

Каждый запуск upsert — это `MERGE Node ... SET ...` плюс `DELETE` всех исходящих edges с последующей вставкой свежих. Дважды-три раза подряд = граф не меняется.

`_ingest_state.json` (рядом с KuzuDB) хранит `path → content_hash`. С `--incremental` skip'ает файлы, у которых body-hash совпадает.

### content_hash от body, не frontmatter

Изменения метаданных (typo в title, bump `last_updated`, перепарковка `related_concepts`) **не триггерят re-extract** через `--incremental`. Только правка тела. Если хочется насильно — `python -m knowledge.ingest` без `--incremental`.

## Subagent-enrichment workflow (опционально)

Heuristic-extract (1 REFERS_TO edge на каждое `related_concepts`) — это baseline. Полноценный набор связей с типизированными relations (`combines_with`, `clashes_with`, `example_of` и т.д.) достаётся через Claude Code subagent.

### Шаги:

1. **Найти кандидатов:**
   ```bash
   python -m knowledge.ingest --list-pending-extracts
   ```
   Выведет список .md без sidecar.

2. **Для каждого файла — спросить Claude Code:**
   - в Claude Code сессии открыть нужный .md
   - дать команду: «извлеки triplets для этого файла»
   - Claude вызовет subagent (`Agent` tool) с промптом из `extract.render_subagent_prompt(doc)`
   - subagent читает body и пишет JSON-список triplets в `<file>.triplets.json`

3. **Re-ingest:**
   ```bash
   python -m knowledge.ingest --incremental
   ```
   Файлы с sidecar теперь дают свежие triplets вместо heuristic'и (parser детектирует body-hash без изменений, но граф перезапишется при следующем ingest без `--incremental` — потому что edges DELETE-CREATE каждый раз).

### Sidecar format

```json
[
  {"subject": "L7_predictive_patterns/relationships/01", "relation": "refers_to", "object": "concept:taohua"},
  {"subject": "L7_predictive_patterns/relationships/01", "relation": "clashes_with", "object": "concept:liuchong"},
  {"subject": "L7_predictive_patterns/relationships/01", "relation": "example_of", "object": "L7_predictive_patterns/relationships/02"}
]
```

Допустимые `relation`: `refers_to`, `generates`, `controls`, `combines_with`, `clashes_with`, `example_of`.

Object — id целевого Node:
- `concept:<slug>` — общий концепт (создаётся как stub Node, level=0)
- `<L?_folder>/<file_stem>` — другой документ КБ (без `.md`)

Невалидные строки молча пропускаются (см. `_load_sidecar` в [extract.py](extract.py)).

## Deploy

Локально → KuzuDB-файл создаётся в `./knowledge/kuzu_db` (или `settings.kuzu_db_path`). На прод:

```bash
# 1. Локально: ingest + commit
python -m knowledge.ingest
git add knowledge/kuzu_db* knowledge/_ingest_state.json
git commit -m "feat(knowledge): rebuild kuzu graph"

# 2. rsync на VM (граф + state)
rsync ... yc-user@130.193.51.15:~/BaDzi_bot/

# 3. На VM bot контейнер сам подхватит KuzuDB через kuzu_db_path
```

Альтернативно — если КБ слишком большая для git: ingest на VM:
```bash
ssh ... 'cd ~/BaDzi_bot && python -m knowledge.ingest --verbose'
```

## Тесты

```bash
pytest tests/unit/test_knowledge/ -v
```

36 тестов в `tests/unit/test_knowledge/test_{parser,extract,writer,ingest_cli}.py` — все против реальной embedded KuzuDB в `tmp_path`.

## PDF → L1-L7 chunking workflow

Для конвертации большого PDF в множество правильно классифицированных .md (вместо одного гигантского):

```python
# 1. Положить PDF как .md в _audio_transcripts/ (PyMuPDF / pdfplumber)
from pathlib import Path
import fitz
doc = fitz.open("path/to/course.pdf")
pages = []
for i, page in enumerate(doc, 1):
    pages.append(f"\n\n<!-- page {i} -->\n\n{page.get_text('text').strip()}")
Path("База/teacher/_audio_transcripts/course.md").write_text(
    "---\nlevel: L0\ntopic: foundation_course\n---\n" + "".join(pages),
    encoding="utf-8",
)

# 2. Сгенерировать промпт для discovery-subagent
from knowledge.ingest.from_pdf import render_toc_prompt
prompt = render_toc_prompt(Path("База/teacher/_audio_transcripts/course.md"))
# → передать в Claude Code Agent tool, он напишет course.toc.json

# 3. Для каждой главы из TOC сгенерировать prompt + спавнить subagent
from knowledge.ingest.from_pdf import load_toc, render_chunk_prompt, slice_body_by_pages
toc = load_toc(Path("База/teacher/_audio_transcripts/course.toc.json"))
text = Path("База/teacher/_audio_transcripts/course.md").read_text()
for entry in toc:
    body_slice = slice_body_by_pages(text, entry.page_start, entry.page_end)
    chunk_prompt = render_chunk_prompt(entry, body_slice, pdf_path)
    # → Agent tool с этим промптом, он напишет .md в нужную L?_*/ папку

# 4. Стандартный ingest подхватит новые .md
# python -m knowledge.ingest --incremental
```

**Размер ограничения:** discovery-subagent читает до 250k chars (≈63k tokens) — ок для 200-страничного PDF. Для PDF >300 страниц нужна постраничная discovery.

**Проблема с двоеточиями в title:** YAML-frontmatter ломается если в `title:` есть `:` без кавычек (напр. `10 типов личности: Дерево`). Шаблон в `render_chunk_prompt` оборачивает title в `"..."` — но subagent должен это сохранить. Если 14+ файлов с `bad_frontmatter` warning — это симптом, fix через быстрый sed-скрипт.

**Известные ограничения:**
- Subagent может неправильно классифицировать level (видели один случай: timing-глава попала в L1 frontmatter хотя в TOC L7). Файл всё равно ingest'ится, граф корректен по path, но `level` в frontmatter может расходиться с папкой.
- Очень большие chunks (>25k chars text) могут падать с `socket connection closed` — пропустить или разбить дополнительно.
