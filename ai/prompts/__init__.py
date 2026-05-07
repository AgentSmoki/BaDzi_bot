"""System prompts as code-first loadable resources.

Prompts are .md files alongside this module so version control sees
diffs as readable text, but consumers always load via ``get_prompt``
to keep file paths off call sites.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Final

_PROMPTS_DIR: Final = Path(__file__).resolve().parent

ANASTASIA_SYSTEM: Final = "anastasia_system"


@lru_cache(maxsize=8)
def get_prompt(name: str) -> str:
    """Return the contents of ``ai/prompts/<name>.md``.

    Cached: prompts are static at runtime, the 68 KB Anastasia file
    being the dominant case. Pass a stable identifier (``ANASTASIA_SYSTEM``
    constant) instead of a hand-typed string at call sites.
    """
    path = _PROMPTS_DIR / f"{name}.md"
    if not path.is_file():
        raise FileNotFoundError(f"prompt not found: {path}")
    return path.read_text(encoding="utf-8")


def load_system_prompt() -> str:
    """Shorthand for the only prompt anyone loads in 1.8: Anastasia's
    persona. Kept as a function (not a constant) so the read happens
    on first use, not at import — startup stays fast even if the
    prompt grows."""
    return get_prompt(ANASTASIA_SYSTEM)
