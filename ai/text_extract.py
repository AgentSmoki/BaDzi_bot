"""Smart text → birth data extraction (Wave 2, пункт 6).

User pastes a free-form sentence like
    «27.04.88 Севастополь время 07:03 утра примерно»
or
    «Родился 15 июля 1990 в Москве, женщина, время не помню»
and we extract date/time/city/gender/has_birth_time as a typed
``ExtractedBirthData``. Missing fields are reported so the caller can
fall back to the regular FSM flow for the parts the user didn't supply.

Implementation: one fast LLM call (same fast model as the skill-router),
JSON output via ``response_format``, graceful fallback on any parse or
network error so the bot can still ask the user pošagovo without the
LLM being mandatory.
"""

from __future__ import annotations

import json
import re
from typing import Final, Literal

import structlog
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ai.orchestrator import ChatMessage, OrchestratorError, chat
from ai.prompts import load_birth_extract_prompt
from bot.config import get_settings

logger = structlog.get_logger(__name__)

Gender = Literal["male", "female"]

_JSON_BLOCK_RE: Final = re.compile(r"\{.*\}", re.DOTALL)


class ExtractedBirthData(BaseModel):
    """LLM-parsed birth data + provenance.

    All field-data optional — missing entries (``date_iso=None`` etc.)
    mean the user didn't supply them; the bot then asks via FSM. The
    consultation flow uses ``confidence`` to decide whether to confirm
    with the user (high) or ignore and go straight to FSM (low)."""

    model_config = ConfigDict(frozen=True)

    date_iso: str | None = Field(default=None)
    """ISO 8601 date YYYY-MM-DD, or None if user didn't supply."""
    time_iso: str | None = Field(default=None)
    """ISO time HH:MM (24h), or None."""
    city: str | None = Field(default=None)
    """Raw city/locality string the user wrote — passed to geocoder for
    disambiguation. None = user didn't mention a place."""
    gender: Gender | None = Field(default=None)
    has_birth_time: bool = Field(default=False)
    """``True`` only when ``time_iso`` is supplied. Mirrors the manual-
    FSM flag so downstream code (resolve_birth_datetime, render_chart)
    can branch identically."""
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    """LLM's self-rated confidence 0-1. <0.4 → caller should drop
    extracted fields and ask pošagovo."""
    raw_text: str = ""
    """The original user message, kept for logging and re-tries."""

    @property
    def missing_fields(self) -> list[str]:
        """Names of mandatory fields the LLM couldn't fill. ``time`` is
        excluded because «без времени» is a valid input."""
        missing = []
        if not self.date_iso:
            missing.append("date")
        if not self.city:
            missing.append("city")
        if not self.gender:
            missing.append("gender")
        return missing

    @property
    def is_complete(self) -> bool:
        """All mandatory fields present. ``time`` is optional."""
        return not self.missing_fields


def _empty_fallback(raw_text: str, reason: str) -> ExtractedBirthData:
    """Used on any LLM / parse / validation error. Returns an
    «everything missing» extract so the caller falls back to FSM."""
    logger.warning("text_extract.fallback", reason=reason, text_preview=raw_text[:120])
    return ExtractedBirthData(
        date_iso=None,
        time_iso=None,
        city=None,
        gender=None,
        has_birth_time=False,
        confidence=0.0,
        raw_text=raw_text,
    )


def _extract_json(text: str) -> str:
    match = _JSON_BLOCK_RE.search(text)
    if match is None:
        raise ValueError("no JSON object in LLM output")
    return match.group(0)


async def extract_birth_data(text: str) -> ExtractedBirthData:
    """Call the fast LLM and return parsed ``ExtractedBirthData``.

    Never raises — any parse / network / 4xx error is downgraded to
    an empty extract with ``confidence=0.0`` so the consultation
    handler can route to FSM without try/except boilerplate."""
    cleaned = text.strip()
    if not cleaned:
        return _empty_fallback("", "empty_input")

    settings = get_settings()
    system_prompt = load_birth_extract_prompt()
    messages = [
        ChatMessage(role="system", content=system_prompt),
        ChatMessage(role="user", content=cleaned),
    ]
    try:
        result = await chat(
            provider="openrouter",
            model=settings.fast_model,
            messages=messages,
            temperature=0.1,
            max_tokens=settings.fast_max_tokens,
            response_format={"type": "json_object"},
        )
    except OrchestratorError as exc:
        return _empty_fallback(cleaned, f"upstream_{type(exc).__name__}")

    try:
        json_blob = _extract_json(result.text)
    except ValueError:
        return _empty_fallback(cleaned, "no_json")

    try:
        parsed = json.loads(json_blob)
    except json.JSONDecodeError:
        return _empty_fallback(cleaned, "json_decode")

    # Inject raw_text so the model doesn't need to echo it back.
    parsed["raw_text"] = cleaned
    # Pin has_birth_time to «time present»: protects against the LLM
    # returning time_iso=null but has_birth_time=true.
    if not parsed.get("time_iso"):
        parsed["has_birth_time"] = False

    try:
        return ExtractedBirthData.model_validate(parsed)
    except ValidationError as exc:
        logger.warning(
            "text_extract.validation_error",
            error=str(exc),
            text_preview=cleaned[:120],
        )
        return _empty_fallback(cleaned, "validation")
