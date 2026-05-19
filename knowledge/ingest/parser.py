"""Markdown + YAML-frontmatter parser for teacher KB files (Phase 2.1).

Returns a fully-typed :class:`IngestedDoc` (frontmatter + body + hash
+ ISO-parsed timestamp + computed ``node_id``) suitable for graph
upsert. This is the only frontmatter parser in the codebase — the
runtime retrieval pipeline (:mod:`ai.rag`) queries the graph directly
instead of re-parsing markdown.
"""

from __future__ import annotations

import hashlib
import logging
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

import yaml

from knowledge.ingest.models import IngestedDoc

logger = logging.getLogger(__name__)

_FRONTMATTER_RE: Final = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)


def _coerce_datetime(raw: object) -> datetime:
    """YAML may give us a datetime, a date, or a string. Normalise to a
    timezone-aware UTC datetime so KuzuDB TIMESTAMP inserts don't flip
    on local-time interpretation."""
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=UTC)
    if hasattr(raw, "year") and hasattr(raw, "month") and hasattr(raw, "day"):
        # `datetime.date` lacks tzinfo; lift to a UTC midnight datetime
        return datetime(raw.year, raw.month, raw.day, tzinfo=UTC)
    if isinstance(raw, str) and raw:
        try:
            parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError(f"unparseable last_updated: {raw!r}") from exc
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    return datetime.now(UTC)


def _compute_node_id(path: Path, kb_root: Path) -> str:
    """``path`` relative to ``kb_root``, posix-style, no extension. The
    chosen format is stable across OS, easy to debug, and uniqueness
    is enforced by the filesystem itself."""
    try:
        rel = path.relative_to(kb_root)
    except ValueError:
        # Caller passed a path outside the KB root — fall back to the
        # stem alone. Tests run from tmp dirs so this branch matters.
        rel = Path(path.name)
    return rel.with_suffix("").as_posix()


def parse_md_file(path: Path, *, kb_root: Path | None = None) -> IngestedDoc | None:
    """Read one .md and return an :class:`IngestedDoc`, or ``None`` if the
    file isn't a valid KB doc (no frontmatter, unparseable YAML, missing
    required keys). Warnings logged for each failure so a noisy KB
    surfaces problems on first ``--verbose`` run."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("ingest.read_failed", extra={"path": str(path), "error": str(exc)})
        return None

    m = _FRONTMATTER_RE.match(text)
    if not m:
        logger.warning("ingest.no_frontmatter", extra={"path": str(path)})
        return None

    try:
        meta = yaml.safe_load(m.group(1)) or {}
    except yaml.YAMLError as exc:
        logger.warning("ingest.bad_frontmatter", extra={"path": str(path), "error": str(exc)})
        return None
    if not isinstance(meta, dict):
        logger.warning("ingest.frontmatter_not_mapping", extra={"path": str(path)})
        return None

    body = m.group(2).strip()
    content_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()

    level_raw = str(meta.get("level", "")).upper().lstrip("L")
    try:
        level = int(level_raw)
    except ValueError:
        logger.warning(
            "ingest.bad_level",
            extra={"path": str(path), "level": meta.get("level")},
        )
        return None

    try:
        last_updated = _coerce_datetime(meta.get("last_updated"))
    except ValueError as exc:
        logger.warning("ingest.bad_timestamp", extra={"path": str(path), "error": str(exc)})
        return None

    root = kb_root if kb_root is not None else path.parent
    node_id = _compute_node_id(path, root)

    try:
        return IngestedDoc(
            path=path,
            node_id=node_id,
            level=level,
            topic=str(meta.get("topic", "")),
            title=str(meta.get("title", path.stem)),
            body=body,
            summary=str(meta.get("summary", "")),
            source=str(meta.get("source", "")),
            source_authority=int(meta.get("source_authority", 5)),
            applicable_when=tuple(str(c).lower() for c in meta.get("applicable_when", []) or []),
            related_concepts=tuple(str(c).lower() for c in meta.get("related_concepts", []) or []),
            last_updated=last_updated,
            content_hash=content_hash,
        )
    except (TypeError, ValueError) as exc:
        logger.warning("ingest.bad_meta_shape", extra={"path": str(path), "error": str(exc)})
        return None


# Files at these names or under these prefixes are KB metadata, not KB
# content, and are intentionally skipped by the scanner.
_SKIP_FILE_NAMES: Final[frozenset[str]] = frozenset({"README.md", "_template.md"})


def scan_kb(kb_root: Path) -> list[IngestedDoc]:
    """Walk ``kb_root``, parse every .md, return the valid docs. README
    and underscore-prefixed folders are skipped (matches the keyword
    loader behaviour so the two pipelines agree on what's "KB content").

    Underscore folders (``_audio_transcripts``, ``_chart_examples``) are
    deliberately excluded — they hold raw material that needs different
    retrieval logic and would otherwise dominate the corpus.
    """
    if not kb_root.is_dir():
        logger.info("ingest.kb_root_missing", extra={"path": str(kb_root)})
        return []

    docs: list[IngestedDoc] = []
    for md_path in sorted(kb_root.rglob("*.md")):
        if md_path.name in _SKIP_FILE_NAMES:
            continue
        if any(part.startswith("_") for part in md_path.relative_to(kb_root).parts):
            continue
        doc = parse_md_file(md_path, kb_root=kb_root)
        if doc is not None:
            docs.append(doc)
    logger.info("ingest.scan_complete", extra={"path": str(kb_root), "docs": len(docs)})
    return docs
