"""Phase 2 of EdoHa import: read JSONL from Phase 1 → upsert into BaDzi KuzuDB.

Запускается через BaDzi venv (kuzu 0.10), читает результат
``scripts/edoha_export_json.py`` (запускался через EdoHa venv kuzu 0.11.3).
2-фазный pipeline нужен потому что версии KuzuDB несовместимы (single-file
vs directory storage).

Маппинг (см. ~/.claude/plans/moonlit-doodling-zebra.md):

| EdoHa Node      | BaDzi id prefix         | level | source_auth | topic            |
|-----------------|-------------------------|-------|-------------|------------------|
| Manifesto       | edoha:manifesto:{pk}    | 8     | 10          | edoha_manifesto  |
| Quote           | edoha:quote:{pk}        | 8     | 10          | edoha_quote      |
| Fact            | edoha:fact:{pk}         | 8     | 9           | edoha_fact       |
| MentalModel     | edoha:model:{pk}        | 7     | 9           | edoha_model      |
| CausalBelief    | edoha:belief:{pk}       | 7     | 8           | edoha_belief     |
| Document        | edoha:doc:{pk}          | 7     | 9           | edoha_transcript |
| Relation        | edoha:relation:{pk}     | 6     | 8           | edoha_relation   |
| StyleMarker     | edoha:style:{pk}        | 6     | 7           | edoha_style      |

Все узлы: school='edoha', last_updated=now(), content_hash=sha256(body).

Edges (только DERIVED_FROM реально заполнен в EdoHa — 7850 ребёр):
    DERIVED_FROM → REFERS_TO with kind='derived_from'
    REINFORCES   → COMBINES_WITH (если появятся)
    CONTRADICTS  → CLASHES_WITH (если появятся)
    CITES        → REFERS_TO with kind='cites' (если появятся)

Usage:
    python scripts/import_edoha_kuzu.py [--in-dir /tmp/edoha_export]
                                         [--dry-run] [--limit N]
                                         [--node-type Manifesto]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

try:
    import kuzu
except ImportError:
    sys.exit("ERROR: kuzu not installed. Use BaDzi venv: .venv/bin/python")

# BaDzi internals
from knowledge.bootstrap import bootstrap
from knowledge.ingest.models import IngestedDoc, RelationKind, Triplet
from knowledge.ingest.writer import upsert_doc

DEFAULT_IN = Path("/tmp/edoha_export")
DEFAULT_DB = Path("./knowledge/kuzu_db")

# EdoHa Node type → BaDzi node mapping (см. таблицу в docstring)
TYPE_CONFIG: dict[str, dict[str, Any]] = {
    "Manifesto": {
        "prefix": "edoha:manifesto",
        "pk": "manifesto_id",
        "level": 8,
        "auth": 10,
        "topic": "edoha_manifesto",
    },
    "Quote": {
        "prefix": "edoha:quote",
        "pk": "quote_id",
        "level": 8,
        "auth": 10,
        "topic": "edoha_quote",
    },
    "Fact": {"prefix": "edoha:fact", "pk": "fact_id", "level": 8, "auth": 9, "topic": "edoha_fact"},
    "MentalModel": {
        "prefix": "edoha:model",
        "pk": "model_id",
        "level": 7,
        "auth": 9,
        "topic": "edoha_model",
    },
    "CausalBelief": {
        "prefix": "edoha:belief",
        "pk": "belief_id",
        "level": 7,
        "auth": 8,
        "topic": "edoha_belief",
    },
    "Document": {
        "prefix": "edoha:doc",
        "pk": "document_id",
        "level": 7,
        "auth": 9,
        "topic": "edoha_transcript",
    },
    "Relation": {
        "prefix": "edoha:relation",
        "pk": "relation_id",
        "level": 6,
        "auth": 8,
        "topic": "edoha_relation",
    },
    "StyleMarker": {
        "prefix": "edoha:style",
        "pk": "marker_id",
        "level": 6,
        "auth": 7,
        "topic": "edoha_style",
    },
}

# EdoHa REL → BaDzi REL kind
EDGE_MAPPING: dict[str, tuple[RelationKind, str]] = {
    "DERIVED_FROM": ("refers_to", "derived_from"),
    "CITES": ("refers_to", "cites"),
    "BELONGS_TO_DIGEST": ("refers_to", "belongs_to_digest"),
    "REINFORCES": ("combines_with", "default"),
    "CONTRADICTS": ("clashes_with", "default"),
}

# Regex для CJK иероглифов — фундамент для related_concepts.
# Русские термины (стволы/ветви/божества/звёзды) выдёргиваем через keyword
# вокабуляр потому что regex на русском слишком шумный.
_CJK_RE = re.compile(r"[一-鿿]+")

# Базовый словарь Ба Цзы — попадание в text/statement добавляет concept.
# Намеренно короткий — концепты должны быть «канонические» для retrieve.
_BAZI_KEYWORDS = [
    "бацзы",
    "ба цзы",
    "у-син",
    "усин",
    "столп",
    "ветв",
    "ствол",
    "дневной мастер",
    "юн шэнь",
    "цзи шэнь",
    "такт",
    "крыс",
    "бык",
    "тигр",
    "кролик",
    "дракон",
    "змея",
    "лошад",
    "коза",
    "обезьян",
    "петух",
    "собак",
    "свинь",
    "огонь",
    "земля",
    "металл",
    "вода",
    "дерев",
    "ян",
    "инь",
    "семь убийц",
    "прямой чиновник",
    "печать",
    "богатство",
    "белый тигр",
    "тао хуа",
    "сян ши",
    "羊刃",
    "桃花",
    "白虎",
    "365 дней",
    "год лошади",
    "2026",
    "солнцестояни",
    "цзе ци",
]


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _slug_for_body(text: str | None, default: str) -> str:
    """Body не должен быть пустой — KuzuDB не любит empty STRING на REQUIRED?
    Тут он optional, но writer.py использует hash(body) — пустой body даст
    одинаковый hash для всех empty узлов. Подставляем placeholder."""
    if text and text.strip():
        return text.strip()
    return default


def _make_body(node_type: str, n: dict[str, Any]) -> str:
    """Формирует ``body`` поле IngestedDoc по типу узла. Включает основной
    контент + структурированные metadata (доказательства, частота)."""
    if node_type == "Manifesto":
        text = n.get("text") or ""
        freq = n.get("frequency") or 0
        conf = n.get("confidence") or ""
        return _slug_for_body(text, f"manifesto:{n.get('manifesto_id', '?')}") + (
            f"\n\n_freq={freq}, confidence={conf}_" if freq or conf else ""
        )
    if node_type == "Quote":
        text = n.get("text") or ""
        src = n.get("source_chunk") or ""
        rec = n.get("recurrence_count") or 0
        return _slug_for_body(text, f"quote:{n.get('quote_id', '?')}") + (
            f"\n\n_recurrence={rec}, source_chunk={src}_" if rec or src else ""
        )
    if node_type == "Fact":
        statement = n.get("statement") or ""
        evidence = n.get("verbatim_evidence") or []
        period = n.get("period") or ""
        body = _slug_for_body(statement, f"fact:{n.get('fact_id', '?')}")
        if evidence:
            body += "\n\nДоказательства:\n" + "\n".join(f"- {e}" for e in evidence[:5])
        if period:
            body += f"\n\nПериод: {period}"
        return body
    if node_type == "MentalModel":
        name = n.get("name") or ""
        reasoning = n.get("reasoning") or ""
        evidence = n.get("verbatim_evidence") or []
        locus = n.get("locus_of_control") or ""
        body = (
            f"## {name}\n\n{reasoning}"
            if name
            else _slug_for_body(reasoning, f"model:{n.get('model_id', '?')}")
        )
        if locus:
            body += f"\n\n_locus={locus}_"
        if evidence:
            body += "\n\nДоказательства:\n" + "\n".join(f"- {e}" for e in evidence[:5])
        return body
    if node_type == "CausalBelief":
        cause = n.get("cause") or ""
        effect = n.get("effect") or ""
        polarity = n.get("polarity") or ""
        evidence = n.get("verbatim_evidence") or []
        body = (
            f"**{cause}** → **{effect}** ({polarity})"
            if cause or effect
            else _slug_for_body("", f"belief:{n.get('belief_id', '?')}")
        )
        if evidence:
            body += "\n\nДоказательства:\n" + "\n".join(f"- {e}" for e in evidence[:5])
        return body
    if node_type == "Document":
        content = n.get("content") or ""
        return _slug_for_body(content, f"doc:{n.get('document_id', '?')}")
    if node_type == "Relation":
        target = n.get("target_name") or "?"
        stance = n.get("stance") or "neutral"
        dehum = n.get("dehumanization_type") or "none"
        empathy = n.get("empathy_marker") or ""
        evidence = n.get("verbatim_evidence") or []
        body = f"**Об: {target}**\nПозиция: {stance}\nДегуманизация: {dehum}\nЭмпатия: {empathy}"
        if evidence:
            body += "\n\nДоказательства:\n" + "\n".join(f"- {e}" for e in evidence[:5])
        return body
    if node_type == "StyleMarker":
        mtype = n.get("marker_type") or "?"
        value = n.get("value") or ""
        examples = n.get("examples") or []
        body = f"**{mtype}**: {value}"
        if examples:
            body += "\n\nПримеры:\n" + "\n".join(f"- {e}" for e in examples[:3])
        return body
    return _slug_for_body("", f"{node_type}:unknown")


def _make_title(node_type: str, n: dict[str, Any]) -> str:
    """title — короткое поле для CONTAINS-search в RAG retrieve. Берём
    самое смысловое поле узла + обрезаем до 120 chars (KuzuDB STRING)."""
    if node_type == "Manifesto":
        return (n.get("text") or "Manifesto")[:120]
    if node_type == "Quote":
        return (n.get("text") or "Quote")[:120]
    if node_type == "Fact":
        return (n.get("statement") or "Fact")[:120]
    if node_type == "MentalModel":
        return (n.get("name") or "MentalModel")[:120]
    if node_type == "CausalBelief":
        cause = (n.get("cause") or "")[:50]
        effect = (n.get("effect") or "")[:50]
        return f"{cause} → {effect}"
    if node_type == "Document":
        # source_id для Document — длинный человекочитаемый ID типа s259_Прогноз_Дракона...
        sid = n.get("source_id") or n.get("document_id") or "Document"
        return sid[:120]
    if node_type == "Relation":
        return f"Об {n.get('target_name', '?')}"[:120]
    if node_type == "StyleMarker":
        return f"{n.get('marker_type', '?')}: {(n.get('value') or '')[:80]}"
    return f"{node_type} (unknown)"


def _extract_concepts(body: str) -> tuple[str, ...]:
    """Достаёт CJK иероглифы + русские BaZi-keywords из body.
    Возвращает sorted unique list (как в BaDzi parser.py)."""
    concepts: set[str] = set()
    # CJK runs (любая последовательность 1-4 иероглифов — обычно слово/имя)
    for match in _CJK_RE.finditer(body):
        token = match.group(0)
        if 1 <= len(token) <= 4:
            concepts.add(token)
    # Russian keyword vocabulary
    body_lower = body.lower()
    for kw in _BAZI_KEYWORDS:
        if kw in body_lower:
            concepts.add(kw)
    return tuple(sorted(concepts))


def _node_to_doc(node: dict[str, Any], node_type: str) -> IngestedDoc | None:
    """Конвертирует одну запись JSONL → IngestedDoc. Возвращает None
    если у узла нет primary key (некорректные данные)."""
    cfg = TYPE_CONFIG[node_type]
    pk = node.get(cfg["pk"])
    if not pk:
        return None
    pk = str(pk)
    node_id = f"{cfg['prefix']}:{pk}"
    body = _make_body(node_type, node)
    title = _make_title(node_type, node)
    content_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return IngestedDoc(
        path=Path(f"/edoha/{cfg['prefix']}/{pk}"),  # virtual path
        node_id=node_id,
        level=cfg["level"],
        topic=cfg["topic"],
        title=title,
        body=body,
        summary="",
        source="edoha_digital_twin",
        source_authority=cfg["auth"],
        applicable_when=(),
        related_concepts=_extract_concepts(body),
        last_updated=datetime.now(UTC),
        content_hash=content_hash,
        school="edoha",
    )


def _edge_to_node_id(label: str, pk: str) -> str | None:
    """src_label/dst_label из JSONL → BaDzi node_id (prefix:pk)."""
    cfg = TYPE_CONFIG.get(label)
    if not cfg:
        return None  # Digest / Person пропускаем
    return f"{cfg['prefix']}:{pk}"


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    items: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                items.append(json.loads(line))
    return items


def _build_edge_index(edges: list[dict[str, Any]]) -> dict[str, list[Triplet]]:
    """Один проход по edges → dict[src_node_id → list[Triplet]].
    O(M) вместо O(N×M) при последующих lookup'ах."""
    index: dict[str, list[Triplet]] = {}
    skipped = 0
    for e in edges:
        src_label = e.get("src_label")
        src_pk = e.get("src_pk")
        dst_label = e.get("dst_label")
        dst_pk = e.get("dst_pk")
        rel_type = e.get("rel_type")
        if not (
            isinstance(src_label, str)
            and isinstance(src_pk, str)
            and isinstance(dst_label, str)
            and isinstance(dst_pk, str)
            and isinstance(rel_type, str)
        ):
            skipped += 1
            continue
        src_id = _edge_to_node_id(src_label, src_pk)
        dst_id = _edge_to_node_id(dst_label, dst_pk)
        mapped = EDGE_MAPPING.get(rel_type)
        if not src_id or not dst_id or not mapped:
            skipped += 1
            continue
        relation_kind, _kind_discriminator = mapped
        index.setdefault(src_id, []).append(
            Triplet(
                subject_node_id=src_id,
                relation=relation_kind,
                object_node_id=dst_id,
                source="subagent",
            )
        )
    print(f"  Edge index: {sum(len(v) for v in index.values())} usable edges, {skipped} skipped")
    return index


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--in-dir", type=Path, default=DEFAULT_IN)
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=None, help="Per-type row limit")
    parser.add_argument(
        "--node-type",
        choices=list(TYPE_CONFIG.keys()),
        default=None,
        help="Import only one node type (debug)",
    )
    args = parser.parse_args(argv)

    if not args.in_dir.exists():
        sys.exit(f"ERROR: input dir {args.in_dir} not found. Run edoha_export_json.py first.")

    types = [args.node_type] if args.node_type else list(TYPE_CONFIG.keys())

    # Load edges once into memory (~7850 records = small).
    edges_all = _load_jsonl(args.in_dir / "edges.jsonl")
    print(f"Loaded {len(edges_all)} edges from {args.in_dir / 'edges.jsonl'}")
    edge_index = _build_edge_index(edges_all)

    conn: kuzu.Connection | None = None
    if not args.dry_run:
        print(f"Bootstrapping BaDzi KuzuDB at {args.db_path}...")
        bootstrap(args.db_path)
        # Explicit buffer pool — default 80% RAM падает с OOM при 7742 upserts
        # на 8GB ноутбуке (Telegram MCP + Claude Code + system держат
        # остальное). 1 GB достаточно для нескольких тысяч узлов с
        # промежуточными CHECKPOINT'ами.
        db = kuzu.Database(str(args.db_path), buffer_pool_size=1024 * 1024 * 1024)
        conn = kuzu.Connection(db)

    counts = {"nodes": 0, "edges": 0, "skipped": 0}

    for node_type in types:
        nodes_path = args.in_dir / f"nodes_{node_type}.jsonl"
        items = _load_jsonl(nodes_path)
        if args.limit:
            items = items[: args.limit]
        print(f"\n[{node_type}] {len(items)} nodes from {nodes_path.name}")

        for i, node in enumerate(items):
            doc = _node_to_doc(node, node_type)
            if doc is None:
                counts["skipped"] += 1
                continue
            triplets = edge_index.get(doc.node_id, [])

            if args.dry_run or conn is None:
                if i < 2:  # show first 2 samples per type
                    print(f"  Sample {i}:")
                    print(f"    id={doc.node_id}")
                    print(f"    title={doc.title[:80]}")
                    print(f"    level={doc.level} auth={doc.source_authority} school={doc.school}")
                    print(f"    body[:120]={doc.body[:120]!r}")
                    print(
                        f"    concepts={doc.related_concepts[:5]}{'...' if len(doc.related_concepts) > 5 else ''}"
                    )
                    print(f"    triplets={len(triplets)}")
                continue

            try:
                upsert_doc(conn, doc, triplets)
                counts["nodes"] += 1
                counts["edges"] += len(triplets)
            except RuntimeError as exc:
                print(f"  ⚠ {doc.node_id}: {exc}")
                counts["skipped"] += 1

            # Промежуточный CHECKPOINT каждые 500 upserts — сбрасывает WAL
            # и освобождает buffer pool. Без этого kuzu держит все писанные
            # страницы в RAM до конца сессии → OOM на 3000+ узлах.
            if counts["nodes"] and counts["nodes"] % 500 == 0:
                try:
                    conn.execute("CHECKPOINT")
                    print(f"  CHECKPOINT @ {counts['nodes']} nodes")
                except RuntimeError as exc:
                    print(f"  ⚠ CHECKPOINT failed: {exc}")

        print(f"  Done: {counts['nodes']} cumulative")

    print(
        f"\n✓ Import done: {counts['nodes']} nodes, {counts['edges']} edges, {counts['skipped']} skipped"
    )
    print(f"  ts={_now_iso()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
