"""Опциональный Phase 3 of EdoHa import: top-N узлов → .md для git visibility.

После основного импорта (scripts/import_edoha_kuzu.py) все 7742 узла
лежат в KuzuDB (не в git). Этот скрипт дублирует **высокоавторитетную
квинтэссенцию** в `База/edoha/highlights/*.md` чтобы:

1. Богдан мог визуально просмотреть ключевые цитаты/манифесты/факты
   мастера прямо в репо (без kuzu).
2. Если основной import-script упадёт — можно прогнать обычный
   `python -m knowledge.ingest --source База/edoha/highlights/` как fallback.
3. Git diff покажет когда EdoHa обновляется.

Берём:
- ВСЕ Manifesto (212 — это самое ядро, манифесты повторяющиеся).
- ВСЕ Quote (112 — короткие, ценные).
- Top-N Fact по confidence='high' (~200-300).
- НЕ берём StyleMarker / CausalBelief / Relation — они менее
  ценны для git review.
- НЕ берём Document — это сырые транскрипты, гитнуть 537 файлов
  по 3000 токенов = шум.

Usage:
    /Users/admin/Documents/Razarabotka/EdoHa/.venv/bin/python \\
        scripts/export_edoha_to_md.py [--in-dir /tmp/edoha_export]
                                       [--out-dir База/edoha/highlights]
                                       [--fact-limit 300]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_IN = Path("/tmp/edoha_export")
DEFAULT_OUT = Path("База/edoha/highlights")


_SLUG_RE = re.compile(r"[^\w\-_]+", re.UNICODE)


def _slug(text: str, max_len: int = 60) -> str:
    """Безопасное имя файла из произвольной строки (CJK/русский OK)."""
    s = _SLUG_RE.sub("_", text.strip())[:max_len].strip("_")
    return s or "untitled"


def _make_frontmatter(
    *,
    title: str,
    level: str,
    source_authority: int,
    topic: str,
    related: list[str],
    source_id: str,
) -> str:
    """YAML frontmatter под BaDzi knowledge.ingest.parser требования."""
    lines = [
        "---",
        f"level: {level}",
        f"topic: {topic}",
        f'title: "{title.replace(chr(34), chr(39))[:100]}"',
        "school: edoha",
        f"source_authority: {source_authority}",
        f"source: {source_id}",
        f"last_updated: {datetime.now(UTC).date().isoformat()}",
    ]
    if related:
        lines.append("related_concepts:")
        for c in related[:10]:
            lines.append(f"  - {c}")
    else:
        lines.append("related_concepts: []")
    lines.append("applicable_when: []")
    lines.append("---")
    return "\n".join(lines)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def export_manifestos(items: list[dict[str, Any]], out_dir: Path) -> int:
    folder = out_dir / "manifesto"
    folder.mkdir(parents=True, exist_ok=True)
    for item in items:
        mid = item.get("manifesto_id") or "unknown"
        text = (item.get("text") or "").strip()
        if not text:
            continue
        freq = item.get("frequency") or 0
        conf = item.get("confidence") or ""
        slug = _slug(text, 50)
        path = folder / f"{mid}_{slug}.md"
        fm = _make_frontmatter(
            title=text[:80],
            level="L8",
            source_authority=10,
            topic="edoha_manifesto",
            related=[],
            source_id="edoha_digital_twin",
        )
        body = f"# Manifesto\n\n> {text}\n\n_Частота: {freq}, уверенность: {conf}_\n"
        path.write_text(f"{fm}\n\n{body}", encoding="utf-8")
    return len(items)


def export_quotes(items: list[dict[str, Any]], out_dir: Path) -> int:
    folder = out_dir / "quote"
    folder.mkdir(parents=True, exist_ok=True)
    for item in items:
        qid = item.get("quote_id") or "unknown"
        text = (item.get("text") or "").strip()
        if not text:
            continue
        src = item.get("source_chunk") or ""
        rec = item.get("recurrence_count") or 0
        slug = _slug(text, 50)
        path = folder / f"{qid}_{slug}.md"
        fm = _make_frontmatter(
            title=text[:80],
            level="L8",
            source_authority=10,
            topic="edoha_quote",
            related=[],
            source_id=src or "edoha_digital_twin",
        )
        body = f"# Quote\n\n> {text}\n\n_Повторов: {rec}_\n"
        path.write_text(f"{fm}\n\n{body}", encoding="utf-8")
    return len(items)


def export_top_facts(items: list[dict[str, Any]], out_dir: Path, limit: int) -> int:
    folder = out_dir / "fact"
    folder.mkdir(parents=True, exist_ok=True)

    # Sort by confidence='high' first, длинней evidence — выше.
    def _score(f: dict[str, Any]) -> int:
        conf = f.get("confidence") or "low"
        conf_score = {"high": 100, "medium": 50}.get(conf, 0)
        ev = f.get("verbatim_evidence") or []
        return conf_score + len(ev) * 5

    items_sorted = sorted(items, key=_score, reverse=True)[:limit]
    for item in items_sorted:
        fid = item.get("fact_id") or "unknown"
        statement = (item.get("statement") or "").strip()
        if not statement:
            continue
        evidence = item.get("verbatim_evidence") or []
        slug = _slug(statement, 50)
        path = folder / f"{fid}_{slug}.md"
        fm = _make_frontmatter(
            title=statement[:80],
            level="L8",
            source_authority=9,
            topic="edoha_fact",
            related=[],
            source_id="edoha_digital_twin",
        )
        body = f"# Fact\n\n{statement}\n"
        if evidence:
            body += "\n\n## Доказательства\n\n" + "\n".join(f"- {e}" for e in evidence[:5])
        path.write_text(f"{fm}\n\n{body}", encoding="utf-8")
    return len(items_sorted)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in-dir", type=Path, default=DEFAULT_IN)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--fact-limit", type=int, default=200)
    args = parser.parse_args(argv)

    if not args.in_dir.exists():
        sys.exit(f"ERROR: {args.in_dir} not found. Run edoha_export_json.py first.")

    args.out_dir.mkdir(parents=True, exist_ok=True)

    print(f"Exporting EdoHa highlights → {args.out_dir}/")
    n_manifest = export_manifestos(_load_jsonl(args.in_dir / "nodes_Manifesto.jsonl"), args.out_dir)
    n_quote = export_quotes(_load_jsonl(args.in_dir / "nodes_Quote.jsonl"), args.out_dir)
    n_fact = export_top_facts(
        _load_jsonl(args.in_dir / "nodes_Fact.jsonl"), args.out_dir, args.fact_limit
    )
    total = n_manifest + n_quote + n_fact
    print(f"  {n_manifest} manifestos")
    print(f"  {n_quote} quotes")
    print(f"  {n_fact} top-facts")
    print(f"\n✓ {total} highlight files written to {args.out_dir}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
