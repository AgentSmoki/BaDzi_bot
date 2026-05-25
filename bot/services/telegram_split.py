"""Split long LLM answers into chunks that fit Telegram's 4096-char limit.

Shared by `bot/routers/consultation.py` and `bot/scheduler/jobs.py` so
that consultation answers and scheduled forecasts use the same paragraph-
aware splitter. Без этого forecasts падают на «Bad Request: message is
too long» когда LLM пишет блоки 100-220 слов × 5-6 = выше 4096 chars.
"""

from __future__ import annotations

TG_MAX_CHARS: int = 4000
"""Soft limit ниже 4096 чтобы зарезервировать место под HTML-теги."""


def split_for_telegram(text: str, max_len: int = TG_MAX_CHARS) -> list[str]:
    """Split a long LLM answer into chunks that fit Telegram's limit.

    Prefers paragraph boundaries (double newline), falls back to
    single newlines, then to hard char-slice if a paragraph itself
    is longer than `max_len`. Empty chunks are dropped.
    """
    if len(text) <= max_len:
        return [text]

    out: list[str] = []
    current = ""
    for paragraph in text.split("\n\n"):
        candidate = paragraph if not current else f"{current}\n\n{paragraph}"
        if len(candidate) <= max_len:
            current = candidate
            continue
        if current:
            out.append(current)
            current = ""
        if len(paragraph) <= max_len:
            current = paragraph
            continue
        # One paragraph alone is bigger than max_len — split on lines,
        # then char-slice as the last resort.
        for line in paragraph.split("\n"):
            line_candidate = line if not current else f"{current}\n{line}"
            if len(line_candidate) <= max_len:
                current = line_candidate
                continue
            if current:
                out.append(current)
                current = ""
            if len(line) <= max_len:
                current = line
            else:
                for i in range(0, len(line), max_len):
                    piece = line[i : i + max_len]
                    if current:
                        out.append(current)
                        current = ""
                    if i + max_len < len(line):
                        out.append(piece)
                    else:
                        current = piece
    if current:
        out.append(current)
    return [c for c in out if c]
