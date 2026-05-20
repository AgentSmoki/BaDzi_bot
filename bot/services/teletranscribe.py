"""HTTP client for the TeleTranscribe service (Wave 4c).

Bot uses TeleTranscribe to transcribe voice messages dropped into the
journal flow. The MCP server (referenced in Bogdan's roadmap) is a
Claude-Code-side convenience; the bot needs a regular HTTP path, which
is what this module provides.

API contract (inferred from MCP env vars and tt_api_base_url):
    POST /v1/transcribe
    Headers: Authorization: Bearer <api_key>
    Body: multipart-file ``audio`` + optional ``language=ru``
    Response: {"text": "...", ...}

If the deployment's API shape differs, the request builder is the
only place to adjust.
"""

from __future__ import annotations

import structlog
from aiohttp import ClientSession, ClientTimeout, FormData

from bot.config import get_settings

logger = structlog.get_logger(__name__)


class TeleTranscribeError(Exception):
    """Raised on any non-200 / network / parse failure. Caller decides
    whether to surface a Telegram «не получилось расшифровать» message
    or to retry."""


async def transcribe_voice(
    *,
    audio_bytes: bytes,
    filename: str = "voice.oga",
    language: str = "ru",
) -> str:
    """Transcribe a Telegram voice message.

    ``audio_bytes`` is the raw .oga/.ogg/.mp3 content the bot downloads
    via ``bot.download(file_id)``. Returns the recognised text. Raises
    ``TeleTranscribeError`` on failure (caller falls back to «please
    type instead»).
    """
    settings = get_settings()
    if settings.tt_api_key is None:
        raise TeleTranscribeError("TT_API_KEY not configured")

    url = settings.tt_api_base_url.rstrip("/") + "/v1/transcribe"
    headers = {"Authorization": f"Bearer {settings.tt_api_key.get_secret_value()}"}
    timeout = ClientTimeout(total=settings.tt_timeout_seconds)

    data = FormData()
    data.add_field("audio", audio_bytes, filename=filename, content_type="audio/ogg")
    data.add_field("language", language)

    try:
        async with ClientSession(timeout=timeout) as http:
            async with http.post(url, headers=headers, data=data) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise TeleTranscribeError(f"TT returned {resp.status}: {body[:300]}")
                payload = await resp.json()
    except TeleTranscribeError:
        raise
    except Exception as exc:
        raise TeleTranscribeError(f"TT network error: {exc}") from exc

    text = payload.get("text")
    if not isinstance(text, str) or not text.strip():
        raise TeleTranscribeError(f"TT returned empty/invalid text: {payload!r}")
    logger.info(
        "teletranscribe.success",
        text_len=len(text),
        audio_bytes=len(audio_bytes),
    )
    return text.strip()
