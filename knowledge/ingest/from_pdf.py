"""PDF → L1-L7 markdown chunking pipeline (Phase 0.3 v2).

The :mod:`knowledge.ingest` core takes pre-classified .md files as input.
For PDFs from the teacher we still need to (a) decide the chapter
boundaries and (b) assign each chapter to one of L1-L7. This module
provides the two prompt builders + the file writer used by a Claude
Code subagent workflow:

```
1. discover_toc(pdf_md_path) → prompt 1 → subagent → save TOC JSON
2. for each TOC entry:
     render_chunk_prompt(entry, body_slice) → subagent → save .md
3. python -m knowledge.ingest --incremental    # picks up new files
```

We can't invoke subagents from inside Python (Agent tool is Claude Code
session-bound), so the orchestration lives outside this module — see
:func:`render_toc_prompt` and :func:`render_chunk_prompt` for the prompt
templates the operator (or Claude Code) feeds to ``Agent``.
"""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Final

logger = logging.getLogger(__name__)

# Page markers were inserted by the PyMuPDF extraction in Phase 0.3 as
# ``<!-- page N -->``. This regex lets the chunker slice the body by
# page range without re-running OCR.
_PAGE_MARKER_RE: Final = re.compile(r"<!--\s*page\s+(\d+)\s*-->", re.IGNORECASE)

# Valid L-levels matching the schema in :mod:`knowledge.schema`.
_VALID_LEVELS: Final = frozenset({1, 2, 3, 4, 5, 6, 7})


@dataclass(frozen=True, slots=True)
class TocEntry:
    """One row in the TOC the discovery subagent produces. Names align
    with the frontmatter schema so a chunk subagent can emit them
    verbatim into each .md."""

    chapter_no: int
    title: str
    page_start: int
    page_end: int
    level: int  # 1..7
    # topic: one of relationships / career / health / wealth / life_path /
    # timing / stars / structures / atoms / interactions / hidden_stems /
    # ten_gods / foundations
    topic: str
    related_concepts: tuple[str, ...]
    summary: str  # 100-200 chars
    target_folder: str  # e.g. "L1_foundational" / "L3_combinations/ten_gods"
    target_filename: str  # e.g. "01_five_elements.md"

    @classmethod
    def from_dict(cls, data: dict[str, object]) -> TocEntry:
        def _int(key: str) -> int:
            v = data.get(key, 0)
            if isinstance(v, bool):  # bool is a subclass of int — exclude explicitly
                return int(v)
            if isinstance(v, int | float | str):
                return int(v)
            raise TypeError(f"{key}: expected int-compatible, got {type(v).__name__}")

        level = _int("level")
        if level not in _VALID_LEVELS:
            raise ValueError(f"invalid level: {level}")

        rc_raw = data.get("related_concepts") or []
        if not isinstance(rc_raw, list | tuple):
            rc_raw = []
        related = tuple(str(c) for c in rc_raw)

        return cls(
            chapter_no=_int("chapter_no"),
            title=str(data.get("title", "")),
            page_start=_int("page_start"),
            page_end=_int("page_end"),
            level=level,
            topic=str(data.get("topic", "")),
            related_concepts=related,
            summary=str(data.get("summary", "")),
            target_folder=str(data.get("target_folder", "")),
            target_filename=str(data.get("target_filename", "")),
        )


def slice_body_by_pages(pdf_md_text: str, page_start: int, page_end: int) -> str:
    """Return the text between ``<!-- page N -->`` markers for pages
    ``[page_start, page_end]`` inclusive. Returns "" if the markers
    aren't found (subagent will have to work from neighbors)."""
    parts: list[str] = []
    current_page: int | None = None
    last_end = 0
    for m in _PAGE_MARKER_RE.finditer(pdf_md_text):
        # Flush text we just walked past
        if current_page is not None and page_start <= current_page <= page_end:
            parts.append(pdf_md_text[last_end : m.start()])
        current_page = int(m.group(1))
        last_end = m.end()
    # Tail after the last marker
    if current_page is not None and page_start <= current_page <= page_end:
        parts.append(pdf_md_text[last_end:])
    return "\n".join(p.strip() for p in parts if p.strip()).strip()


def render_toc_prompt(pdf_md_path: Path, *, max_chapters: int = 40) -> str:
    """Prompt for the discovery subagent. The subagent reads the whole
    PDF.md and emits a TOC JSON describing each chapter + its L-level
    assignment + suggested filename."""
    text = pdf_md_path.read_text(encoding="utf-8")
    # 253k chars ≈ 63k tokens fits comfortably in 200k-context subagent.
    # If the PDF outgrows that we'd want pagewise discovery; for the
    # current foundation course (200 pages) one pass is enough.
    truncated = text[:250_000]
    out_path = toc_path_for(pdf_md_path)
    return f"""\
Ты разбираешь учебный PDF по китайской метафизике Ба Цзы для построения
структурированной базы знаний (L1-L7 fractal RAG-Graph).

ВХОД: ниже — извлечённый текст PDF с маркерами страниц `<!-- page N -->`.
Объём — до {len(truncated):,} символов из {len(text):,} полного.

ЗАДАЧА: верни JSON-массив TocEntry — table of contents с разбивкой на
{max_chapters} или меньше логических глав. Каждая запись:

{{
  "chapter_no": 1,                       // порядковый номер
  "title": "Пять стихий: введение",      // короткое имя главы
  "page_start": 5,                       // первая страница главы
  "page_end": 12,                        // последняя
  "level": 1,                            // L1..L7 (см. ниже)
  "topic": "foundations",                // см. список ниже
  "related_concepts": ["five_elements", "wu_xing", "stihii"],
  "summary": "100-200 символов о чём глава",
  "target_folder": "L1_foundational",    // куда положить .md
  "target_filename": "01_five_elements_intro.md"
}}

ШКАЛА УРОВНЕЙ:
- L1 (foundations): стихии, инь-ян, ци, базовые принципы, история, школы
- L2 (atoms): 10 небесных стволов + 12 земных ветвей (по отдельности или группой)
- L3 (combinations): скрытые стволы (藏干), 10 Богов (十神)
- L4 (interactions): 合沖刑害破 — взаимодействия ветвей и стволов
- L5 (stars): Шэнь Ша — 60+ символических звёзд
- L6 (structures): 25 классических 格局
- L7 (predictive_patterns): прикладные правила, эвристики, тематические разборы
  (relationships/career/health/wealth/life_path/timing)

TOPIC значения (выбирай ближайший):
foundations | atoms | hidden_stems | ten_gods | interactions | stars |
structures | relationships | career | health | wealth | life_path | timing

ПРАВИЛА:
- 15-40 глав, не больше. Если PDF короткий — меньше.
- page_start/page_end должны соответствовать реальным `<!-- page N -->`
  маркерам в тексте.
- target_filename: lowercase, разделители `_`, расширение `.md`,
  префикс с порядковым номером (`01_`, `02_`...).
- target_folder: точно один из L1_foundational, L2_atoms, L2_atoms/stems,
  L2_atoms/branches, L3_combinations, L3_combinations/hidden_stems,
  L3_combinations/ten_gods, L4_interactions, L5_stars, L6_structures,
  L7_predictive_patterns, L7_predictive_patterns/relationships,
  L7_predictive_patterns/career, L7_predictive_patterns/health,
  L7_predictive_patterns/wealth, L7_predictive_patterns/life_path,
  L7_predictive_patterns/timing.
- 5-10 related_concepts на главу, ASCII slug в lowercase.
- summary — 1-2 предложения на русском.

ВЫХОД: вызови инструмент Write для создания файла:
  {out_path}

Контент — валидный JSON-массив. После Write вызови Bash:
  ls -la {out_path}
  python3 -c "import json; print(len(json.load(open('{out_path}'))))"

В финальном ответе укажи: путь к файлу + количество глав в TOC + краткий
обзор разбивки (1-2 предложения).

---
ТЕКСТ PDF (первые {len(truncated):,} символов):

{truncated}
"""


def render_chunk_prompt(entry: TocEntry, body_slice: str, pdf_md_path: Path) -> str:
    """Prompt for the per-chapter subagent: convert a slice of PDF text
    into a proper KB .md file with frontmatter, suitable for ingest."""
    target = target_path_for(entry, pdf_md_path)
    return f"""\
Ты конвертируешь главу учебника по Ба Цзы в правильный markdown-файл
для базы знаний (формат :mod:`knowledge.ingest.parser`).

ВХОД: текст главы из PDF (страницы {entry.page_start}-{entry.page_end},
{len(body_slice):,} символов). Метаданные главы:
- title: {entry.title}
- level: L{entry.level}
- topic: {entry.topic}
- related_concepts: {list(entry.related_concepts)}
- summary: {entry.summary}

ЗАДАЧА: переписать текст в виде структурированного markdown:
- YAML-frontmatter с полями level/topic/title/related_concepts/
  applicable_when/source/source_authority/last_updated
- Тело — секции `## Принцип`, `## Эвристика` (если применимо), `## Примеры`,
  `## Ограничения` где уместно.
- Удалить артефакты PDF-extract: разорванные слова, лишние пробелы,
  висящие маркеры страниц, повторы.
- Сохранить китайские термины 五行 / 阴阳 / 甲乙丙丁戊己庚辛壬癸 / 子丑寅卯辰巳午未申酉戌亥
  как есть.
- НЕ выдумывай факты которых нет в тексте. Если что-то непонятно —
  опусти, не интерпретируй.

ВЫХОД: вызови Write для создания файла:
  {target}

Frontmatter шаблон (title ОБЯЗАТЕЛЬНО в двойных кавычках — может содержать `:`):
```yaml
---
level: L{entry.level}
topic: {entry.topic}
title: "{entry.title.replace('"', "'")}"
related_concepts: {list(entry.related_concepts)}
applicable_when: []
source: teacher_pdf_foundation_course
source_authority: 9
last_updated: 2026-05-17
---
```

После Write вызови Bash:
  wc -l {target}
  head -20 {target}

В финальном ответе: путь + сколько строк + краткий заголовок секций.

---
ТЕКСТ ГЛАВЫ:

{body_slice}
"""


def toc_path_for(pdf_md_path: Path) -> Path:
    """Where the TOC JSON lives — sidecar next to the PDF.md."""
    return pdf_md_path.with_name(pdf_md_path.stem + ".toc.json")


def target_path_for(entry: TocEntry, pdf_md_path: Path) -> Path:
    """Where the chunk .md should land. Resolves to a path inside the
    teacher KB root (``<pdf_md_path>../../.``), so an .md in
    ``_audio_transcripts/`` produces files under ``L?_*/``."""
    # pdf is at <kb_root>/_audio_transcripts/foundation_course_pdf.md
    # We want <kb_root>/<target_folder>/<filename>
    kb_root = pdf_md_path.resolve().parents[1]
    return kb_root / entry.target_folder / entry.target_filename


def load_toc(toc_path: Path) -> list[TocEntry]:
    """Parse the TOC JSON the discovery subagent produced."""
    raw = json.loads(toc_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("TOC must be a JSON array")
    entries: list[TocEntry] = []
    for i, row in enumerate(raw):
        if not isinstance(row, dict):
            logger.warning("from_pdf.toc_row_not_dict", extra={"index": i})
            continue
        try:
            entries.append(TocEntry.from_dict(row))
        except (ValueError, TypeError) as exc:
            logger.warning("from_pdf.toc_row_invalid", extra={"index": i, "error": str(exc)})
    return entries
