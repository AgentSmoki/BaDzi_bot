"""One-shot migration (Wave 7 Phase 5): tag every teacher-KB markdown
with ``school:`` frontmatter so the RAG layer can filter retrieval.

Classification rule (path-based — explicit, auditable, easy to override):

* Files whose basename starts with ``anastasia_`` → ``classic``
  (curated chunks of the Anastasia v2 system prompt — pure Цзы Пин).
* Files under ``L7_predictive_patterns/`` → ``classic``
  (DM strength / 用神 — applied classical-school methodology).
* Files under ``L6_structures/`` → ``classic`` (25 格局 = Цзы Пин).
* Everything else → ``universal``
  (L1 foundations, L2 stems/branches, L4 interactions, 12 growth stages,
  baihu — shared base theory across all schools).

The script reads each file, splits frontmatter from body, inserts a
``school:`` line if absent (no-op if already tagged), and writes back.
Run once after Phase 5 schema lands; the parser then picks the value up
on the next ``python -m knowledge.ingest --source teacher`` run.

Usage:
    python scripts/tag_teacher_school.py [--dry-run]

Prints a per-file action log so the operator can eyeball the
classifier's verdict before letting it commit edits.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Final

KB_ROOT: Final[Path] = Path("База/teacher")
SKIP_NAMES: Final[frozenset[str]] = frozenset({"README.md", "_template.md"})
FRONTMATTER_RE: Final[re.Pattern[str]] = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.DOTALL)
SCHOOL_LINE_RE: Final[re.Pattern[str]] = re.compile(r"^school:\s*", re.MULTILINE)


def classify(rel_path: Path) -> str:
    """Return ``classic`` / ``edoha`` / ``modern`` / ``universal`` for the
    given path relative to ``KB_ROOT``. See module docstring for the
    rule. Pure function — no I/O."""
    name = rel_path.name
    parts = {part.lower() for part in rel_path.parts}

    if name.startswith("anastasia_"):
        return "classic"
    if "l7_predictive_patterns" in parts:
        return "classic"
    if "l6_structures" in parts:
        return "classic"
    return "universal"


def tag_file(path: Path, *, dry_run: bool) -> str:
    """Insert ``school:`` into the file's frontmatter. Returns a one-word
    action label for the log: ``tagged`` / ``already`` / ``skip``."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"  [error] cannot read {path}: {exc}", file=sys.stderr)
        return "error"

    m = FRONTMATTER_RE.match(text)
    if not m:
        print(f"  [skip ] {path.relative_to(KB_ROOT)} — no frontmatter")
        return "skip"

    fm, body = m.group(1), m.group(2)
    if SCHOOL_LINE_RE.search(fm):
        # Already tagged — keep existing value (might have been edited
        # manually). Idempotent: re-running the script is a no-op.
        return "already"

    school = classify(path.relative_to(KB_ROOT))
    # Insert ``school:`` line right after the last frontmatter key so it
    # stays close to other metadata. Trailing newline avoids collapsing
    # the closing fence onto the new line.
    new_fm = fm.rstrip() + f"\nschool: {school}\n"
    new_text = f"---\n{new_fm}---\n{body}"

    rel = path.relative_to(KB_ROOT)
    print(f"  [{'dry  ' if dry_run else 'tag  '}] {rel} → school: {school}")
    if not dry_run:
        path.write_text(new_text, encoding="utf-8")
    return "tagged"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print intended changes without writing files.",
    )
    args = parser.parse_args(argv)

    if not KB_ROOT.is_dir():
        print(f"KB root not found: {KB_ROOT.resolve()}", file=sys.stderr)
        return 2

    counts: dict[str, int] = {}
    print(f"Scanning {KB_ROOT}/ ...")
    for md_path in sorted(KB_ROOT.rglob("*.md")):
        if md_path.name in SKIP_NAMES:
            continue
        # Skip underscore folders (_audio_transcripts/) — same rule as
        # ingest scan_kb so we don't tag files that won't be ingested.
        if any(part.startswith("_") for part in md_path.relative_to(KB_ROOT).parts):
            continue
        action = tag_file(md_path, dry_run=args.dry_run)
        counts[action] = counts.get(action, 0) + 1

    print(f"\nDone. {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
