"""Triplet extraction for the ingest pipeline (Phase 2.2).

Two modes:

1. **Sidecar mode (canonical):** for each ``foo.md`` we look for
   ``foo.md.triplets.json`` next to it. Sidecar files are produced by
   running a Claude Code subagent over the .md (free under the
   subscription; see :func:`render_subagent_prompt` for the prompt
   template). The CLI command ``--list-pending-extracts`` prints the
   set of .md files missing a sidecar so the operator can pick them
   up one by one.

2. **Heuristic fallback (always available):** every ``related_concepts``
   entry becomes a ``REFERS_TO`` edge from the doc's node to a stub
   node named ``concept:<slug>``. Keeps the graph populated when the
   subagent enrichment hasn't run yet, and provides a deterministic
   baseline for tests.

Heuristic mode is also what runs in production today — sidecar mode
is opt-in and accretive.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Final, get_args

from knowledge.ingest.models import REL_KINDS, IngestedDoc, RelationKind, Triplet

logger = logging.getLogger(__name__)

_SIDECAR_SUFFIX: Final = ".triplets.json"

# Slug normaliser used to make stub-node ids stable: lowercase, replace
# whitespace and non-word chars with underscores, collapse repeats.
# Bazi concepts are mostly ASCII identifiers (``taohua``, ``zheng_guan``)
# but Russian/Chinese names also appear (``белый_тигр``, ``白虎``) — those
# survive the normalisation by virtue of the ``\w`` Unicode flag.
_SLUG_RE: Final = re.compile(r"[\s\W]+", re.UNICODE)


def _slugify(concept: str) -> str:
    s = _SLUG_RE.sub("_", concept.strip().lower()).strip("_")
    return s or "unknown"


def concept_node_id(concept: str) -> str:
    """Stable id for stub concept nodes referenced by heuristic edges."""
    return f"concept:{_slugify(concept)}"


def sidecar_path_for(md_path: Path) -> Path:
    """Where the subagent's extracted-triplets JSON for ``md_path`` lives."""
    return md_path.with_name(md_path.name + _SIDECAR_SUFFIX)


def _load_sidecar(path: Path, doc: IngestedDoc) -> list[Triplet] | None:
    """Read ``<file>.triplets.json``. Returns ``None`` if absent /
    malformed (logged), so the caller falls back to the heuristic."""
    if not path.is_file():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("ingest.sidecar_unreadable", extra={"path": str(path), "error": str(exc)})
        return None
    if not isinstance(raw, list):
        logger.warning("ingest.sidecar_not_list", extra={"path": str(path)})
        return None

    valid_kinds = set(get_args(RelationKind))
    triplets: list[Triplet] = []
    for i, item in enumerate(raw):
        if not isinstance(item, dict):
            continue
        subj = item.get("subject") or doc.node_id
        obj = item.get("object")
        rel = str(item.get("relation", "refers_to")).lower()
        if not obj or rel not in valid_kinds:
            logger.warning(
                "ingest.sidecar_bad_row",
                extra={"path": str(path), "index": i, "row": item},
            )
            continue
        triplets.append(
            Triplet(
                subject_node_id=str(subj),
                relation=rel,  # type: ignore[arg-type]
                object_node_id=str(obj),
                source="subagent",
            )
        )
    return triplets


def _heuristic_triplets(doc: IngestedDoc) -> list[Triplet]:
    """One REFERS_TO edge per related_concepts entry, plus EXAMPLE_OF
    when the doc lives in ``_chart_examples`` (defensive — scan_kb
    skips that folder, but a direct ``--file`` ingest of an example
    file should still produce a sensible edge)."""
    return [
        Triplet(
            subject_node_id=doc.node_id,
            relation="refers_to",
            object_node_id=concept_node_id(concept),
            source="frontmatter",
        )
        for concept in doc.related_concepts
    ]


def extract_triplets(doc: IngestedDoc) -> list[Triplet]:
    """Sidecar first, heuristic fallback. Empty list is a valid output
    (doc has no concepts and no sidecar) — writer treats that as
    'create the Node, no edges'."""
    sidecar = _load_sidecar(sidecar_path_for(doc.path), doc)
    if sidecar is not None:
        logger.info(
            "ingest.sidecar_loaded",
            extra={"path": str(doc.path), "triplets": len(sidecar)},
        )
        return sidecar
    return _heuristic_triplets(doc)


def files_pending_extract(kb_root: Path) -> list[Path]:
    """Returns .md files inside ``kb_root`` that don't yet have a
    sidecar. Used by ``--list-pending-extracts`` to drive the manual
    subagent-enrichment workflow."""
    if not kb_root.is_dir():
        return []
    pending: list[Path] = []
    for md_path in sorted(kb_root.rglob("*.md")):
        if md_path.name in {"README.md", "_template.md"}:
            continue
        if any(part.startswith("_") for part in md_path.relative_to(kb_root).parts):
            continue
        if not sidecar_path_for(md_path).is_file():
            pending.append(md_path)
    return pending


def render_subagent_prompt(doc: IngestedDoc) -> str:
    """The prompt a Claude Code subagent should be given to produce a
    sidecar for ``doc``. Kept as a function (not a constant) so the
    body + node_id can be inlined directly — Claude Code's Agent tool
    treats the prompt as the full task description.

    Output contract: the subagent must write valid JSON to
    ``sidecar_path_for(doc.path)``, a list of objects with keys
    ``subject``, ``relation``, ``object``. Anything else is dropped
    by :func:`_load_sidecar`.
    """
    rels = ", ".join(REL_KINDS)
    return f"""\
Ты извлекаешь концепты и связи из markdown-файла учебной базы по Ба Цзы.

ВХОД: текст ниже (frontmatter + body) — это правило/эвристика учителя
Ба Цзы по которому надо построить knowledge-graph triplets.

ЗАДАЧА: верни JSON-массив объектов (subject, relation, object), где:
- ``subject`` — id текущего документа: ``"{doc.node_id}"``
- ``relation`` — одно из: {rels}
- ``object`` — id или slug целевого концепта (например ``concept:taohua``,
  ``concept:day_master_strength``, ``L5_stars/baihu_white_tiger``).
  Если объект — другой документ КБ, используй его относительный путь
  без .md. Если общий концепт — префикс ``concept:``.

ВЫХОД: сохрани результат в файл:
  {sidecar_path_for(doc.path)}

Формат — валидный JSON, например:
[
  {{"subject": "{doc.node_id}", "relation": "refers_to", "object": "concept:taohua"}},
  {{"subject": "{doc.node_id}", "relation": "clashes_with", "object": "concept:liuchong"}}
]

ПРАВИЛА:
- 5-15 triplets на документ — больше = шум.
- НЕ выдумывай концепты, которых нет в тексте.
- Если в тексте есть пример карты с конкретным ДМ — используй
  ``example_of`` со ссылкой на узел ``concept:<ДМ>``.

---
ТЕКСТ ДОКУМЕНТА:

{doc.body}
"""
