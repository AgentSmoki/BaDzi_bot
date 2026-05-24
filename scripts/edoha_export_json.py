"""Phase 1 of EdoHa import: read EdoHa KuzuDB (v0.11) → write JSONL files.

Запускать через EdoHa venv (kuzu 0.11.3) — НЕ через BaDzi venv (kuzu 0.10).

EdoHa и BaDzi используют разные мажорные версии KuzuDB:
- EdoHa: kuzu==0.11.3 (single-file storage format)
- BaDzi: kuzu==0.10.0 (directory storage, lock-in из-за docker named volume)

Прямое чтение EdoHa db из BaDzi venv падает с `IO exception: Cannot open file .lock`.
Поэтому делаем 2-фазный pipeline:
- Phase 1 (этот скрипт, EdoHa venv): экспорт всех 7743 nodes + edges в JSONL
- Phase 2 (scripts/import_edoha_kuzu.py, BaDzi venv): чтение JSONL → IngestedDoc → upsert

JSONL формат — по файлу на тип узла + один файл для edges:
    /tmp/edoha_export/nodes_Manifesto.jsonl
    /tmp/edoha_export/nodes_Quote.jsonl
    /tmp/edoha_export/nodes_Fact.jsonl
    /tmp/edoha_export/nodes_MentalModel.jsonl
    /tmp/edoha_export/nodes_CausalBelief.jsonl
    /tmp/edoha_export/nodes_Document.jsonl
    /tmp/edoha_export/nodes_Relation.jsonl
    /tmp/edoha_export/nodes_StyleMarker.jsonl
    /tmp/edoha_export/edges.jsonl  (все 5 типов rel — BELONGS_TO_DIGEST/DERIVED_FROM/CITES/REINFORCES/CONTRADICTS)

Usage:
    /Users/admin/Documents/Razarabotka/EdoHa/.venv/bin/python \\
        scripts/edoha_export_json.py [--out-dir /tmp/edoha_export] [--limit N]
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

try:
    import kuzu
except ImportError:
    sys.exit(
        "ERROR: kuzu not installed in this venv. Use EdoHa venv: /Users/admin/Documents/Razarabotka/EdoHa/.venv/bin/python"
    )


EDOHA_DB = Path("/Users/admin/Documents/Razarabotka/EdoHa/kuzu/db")
DEFAULT_OUT = Path("/tmp/edoha_export")

# Имена node-таблиц в EdoHa kuzu. Person/Digest пропускаем (identity-anchor
# и фрактальная иерархия — в BaDzi не нужны как отдельные узлы; их title
# попадают в related_concepts edoha-узлов через BELONGS_TO_DIGEST).
NODE_TABLES = [
    "Manifesto",
    "Quote",
    "Fact",
    "MentalModel",
    "CausalBelief",
    "Document",
    "Relation",
    "StyleMarker",
]

# Rel-таблицы. PARENT_OF (Digest→Digest) пропускаем (Digest не импортируем).
REL_TABLES = [
    "BELONGS_TO_DIGEST",
    "DERIVED_FROM",
    "CITES",
    "REINFORCES",
    "CONTRADICTS",
]


def _json_default(obj: Any) -> Any:
    """JSON encoder для datetime/date/list — Kuzu возвращает datetime
    для TIMESTAMP колонок, json.dumps этого не умеет."""
    if isinstance(obj, datetime | date):
        return obj.isoformat()
    if isinstance(obj, bytes):
        return obj.decode("utf-8", errors="replace")
    raise TypeError(f"Not serializable: {type(obj).__name__}")


def _row_to_dict(row: Any) -> dict[str, Any]:
    """Kuzu Python client возвращает list[...] для каждой колонки. Когда
    запрашиваем `RETURN n`, элемент — dict-like с ключами колонок Node."""
    if isinstance(row, dict):
        # Drop kuzu internal columns
        return {k: v for k, v in row.items() if not k.startswith("_")}
    return {"value": row}


def export_nodes(
    conn: kuzu.Connection,
    out_dir: Path,
    *,
    limit: int | None = None,
) -> dict[str, int]:
    """Один JSONL на тип. Возвращает {table_name: count}."""
    counts: dict[str, int] = {}
    for table in NODE_TABLES:
        out_path = out_dir / f"nodes_{table}.jsonl"
        query = f"MATCH (n:{table}) RETURN n"
        if limit:
            query += f" LIMIT {limit}"
        result = conn.execute(query)
        assert not isinstance(result, list), "single-statement query"
        n = 0
        with out_path.open("w", encoding="utf-8") as f:
            while result.has_next():
                row = result.get_next()
                # row[0] = the Node value (dict-like)
                node_dict = _row_to_dict(row[0])
                f.write(json.dumps(node_dict, ensure_ascii=False, default=_json_default))
                f.write("\n")
                n += 1
        counts[table] = n
        print(f"  {table}: {n} nodes → {out_path}")
    return counts


_PK_BY_LABEL = {
    "Manifesto": "manifesto_id",
    "Quote": "quote_id",
    "Fact": "fact_id",
    "MentalModel": "model_id",
    "CausalBelief": "belief_id",
    "Document": "document_id",
    "Relation": "relation_id",
    "StyleMarker": "marker_id",
    "Digest": "digest_id",
    "Person": "person_id",
}


def _node_pk(node: dict[str, Any]) -> str | None:
    """Достать primary key из dict-like node, используя _label → PK map."""
    label = node.get("_label")
    if not label:
        return None
    pk_field = _PK_BY_LABEL.get(label)
    if not pk_field:
        return None
    val = node.get(pk_field)
    return str(val) if val is not None else None


def export_edges(
    conn: kuzu.Connection,
    out_dir: Path,
    *,
    limit: int | None = None,
) -> int:
    """Все edges в один JSONL. Формат:
        {src_label, src_pk, dst_label, dst_pk, rel_type}

    `_label` достаётся из node dict (возвращается когда RETURN n как целое).
    PK выбирается по `_label` из таблицы _PK_BY_LABEL.
    """
    out_path = out_dir / "edges.jsonl"
    total = 0
    with out_path.open("w", encoding="utf-8") as f:
        for rel in REL_TABLES:
            query = f"MATCH (a)-[r:{rel}]->(b) RETURN a, b"
            if limit:
                query += f" LIMIT {limit}"
            try:
                result = conn.execute(query)
            except RuntimeError as exc:
                print(f"  ⚠ {rel}: skipped ({exc})")
                continue
            assert not isinstance(result, list), "single-statement query"
            n_rel = 0
            n_dropped = 0
            while result.has_next():
                row = result.get_next()
                # _row_to_dict стрипает _-prefixed; используем raw row[*]
                # с _label/_id ключами для edge metadata.
                src_full = row[0] if isinstance(row[0], dict) else {}
                dst_full = row[1] if isinstance(row[1], dict) else {}
                src_label = src_full.get("_label")
                dst_label = dst_full.get("_label")
                src_pk = _node_pk(src_full)
                dst_pk = _node_pk(dst_full)
                if not src_label or not dst_label or not src_pk or not dst_pk:
                    n_dropped += 1
                    continue
                edge = {
                    "src_label": src_label,
                    "src_pk": src_pk,
                    "dst_label": dst_label,
                    "dst_pk": dst_pk,
                    "rel_type": rel,
                }
                f.write(json.dumps(edge, ensure_ascii=False))
                f.write("\n")
                n_rel += 1
            total += n_rel
            print(f"  {rel}: {n_rel} edges (dropped {n_dropped})")
    print(f"  TOTAL edges → {out_path}: {total}")
    return total


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--out-dir", type=Path, default=DEFAULT_OUT, help="Output dir for JSONL files"
    )
    parser.add_argument("--limit", type=int, default=None, help="Per-table row limit (debug)")
    parser.add_argument("--nodes-only", action="store_true", help="Skip edges export")
    args = parser.parse_args(argv)

    if not EDOHA_DB.exists():
        sys.exit(f"ERROR: EdoHa db not found at {EDOHA_DB}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    print(f"Reading EdoHa db: {EDOHA_DB} (kuzu {kuzu.__version__})")
    print(f"Writing JSONL to: {args.out_dir}")

    db = kuzu.Database(str(EDOHA_DB), read_only=True)
    conn = kuzu.Connection(db)

    print("\n=== Nodes ===")
    node_counts = export_nodes(conn, args.out_dir, limit=args.limit)

    if not args.nodes_only:
        print("\n=== Edges ===")
        edge_count = export_edges(conn, args.out_dir, limit=args.limit)
    else:
        edge_count = 0

    total_nodes = sum(node_counts.values())
    print(f"\n✓ Export done: {total_nodes} nodes ({len(node_counts)} types) + {edge_count} edges")
    print(f"  Next: BaDzi_bot venv → python scripts/import_edoha_kuzu.py --in-dir {args.out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
