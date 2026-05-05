#!/usr/bin/env python3
"""Update the graphify knowledge graph for this project.

Two-tier strategy:
  1. Code graph (.py / .ts / ...) — rebuilt deterministically via tree-sitter.
     Free, fast (~seconds), runs on every invocation.
  2. Prose graph (.md / .pdf / images) — semantic extraction needs an LLM,
     which costs money. We only DETECT drift and warn the user; the actual
     LLM-based extraction must be invoked manually via `/graphify --update`
     from Claude Code (or graphify CLI with API keys configured).

Usage:
    python3 scripts/graphify_update.py            # rebuild code, check prose, report
    python3 scripts/graphify_update.py --check    # check only, don't rebuild
    python3 scripts/graphify_update.py --quiet    # only output on prose drift
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _import_graphify() -> Any | None:  # noqa: ANN401  (heterogeneous tuple of callables)
    try:
        import graphify  # noqa: F401
    except ImportError:
        print(
            "[graphify-update] graphify is not installed in this environment.\n"
            "  Install: pip install graphifyy",
            file=sys.stderr,
        )
        return None
    from graphify.cache import check_semantic_cache
    from graphify.detect import detect
    from graphify.watch import _rebuild_code

    return _rebuild_code, detect, check_semantic_cache


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check", action="store_true", help="check only; do not rebuild code graph"
    )
    parser.add_argument("--quiet", action="store_true", help="only output if prose drift exists")
    args = parser.parse_args()

    imports = _import_graphify()
    if imports is None:
        return 0  # do not block commits if graphify is missing
    rebuild_code, detect, check_semantic_cache = imports

    if not args.check:
        ok = rebuild_code(PROJECT_ROOT)
        if ok and not args.quiet:
            graph_json = PROJECT_ROOT / "graphify-out" / "graph.json"
            print(f"[graphify-update] code graph rebuilt: {graph_json}")
        elif not ok:
            print("[graphify-update] code graph rebuild failed", file=sys.stderr)

    detect_result = detect(PROJECT_ROOT)
    # graphify category names: document (.md/.txt/.rst), paper (.pdf),
    # image (.png/.jpg — vision LLM). Video excluded (needs transcription first).
    by_category: dict[str, list[str]] = {
        cat: detect_result.get("files", {}).get(cat, []) for cat in ("document", "paper", "image")
    }
    prose_files: list[str] = [f for files in by_category.values() for f in files]

    if not prose_files:
        return 0

    _, _, _, uncached = check_semantic_cache(prose_files)
    cached_count = len(prose_files) - len(uncached)

    # Persist the canonical handoff file consumed by `/graphify . --update`
    # (Step B0 of the skill pipeline). Empty file if no drift.
    uncached_txt = PROJECT_ROOT / "graphify-out" / ".graphify_uncached.txt"
    uncached_txt.parent.mkdir(parents=True, exist_ok=True)
    uncached_txt.write_text("\n".join(uncached) + ("\n" if uncached else ""), encoding="utf-8")

    if not uncached:
        if not args.quiet:
            print(
                f"[graphify-update] prose graph: {cached_count}/{len(prose_files)} cached, all current ✓"
            )
        return 0

    # Group uncached by category for compact summary.
    uncached_set = set(uncached)
    breakdown: dict[str, list[str]] = {
        cat: [f for f in files if f in uncached_set] for cat, files in by_category.items()
    }

    print("", file=sys.stderr)
    print(
        f"[graphify-update] ⚠️  Prose graph stale: {len(uncached)}/{len(prose_files)} file(s) "
        "changed or new since last LLM extraction:",
        file=sys.stderr,
    )
    for cat, items in breakdown.items():
        if not items:
            continue
        examples = items[:3]
        suffix = f" ... +{len(items) - 3} more" if len(items) > 3 else ""
        rel_examples = [str(Path(f).relative_to(PROJECT_ROOT)) for f in examples]
        print(f"    {cat:>9} ({len(items)}): {', '.join(rel_examples)}{suffix}", file=sys.stderr)
    print(
        "[graphify-update] To refresh: run `/graphify . --update` from Claude Code "
        "(uses LLM, ~$0.01-0.05/file).",
        file=sys.stderr,
    )
    print(
        "[graphify-update] To exclude assets: add patterns to .graphifyignore at project root.",
        file=sys.stderr,
    )
    print("", file=sys.stderr)
    return 0  # never block the commit; this is informational only


if __name__ == "__main__":
    sys.exit(main())
