from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import HttpUrl, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["development", "staging", "production"]
LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
GeocodingProvider = Literal["nominatim"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="forbid",
    )

    # ── Telegram ──────────────────────────────────────────────────────────────
    bot_token: SecretStr
    admin_telegram_id: int

    # ── Database / Cache ──────────────────────────────────────────────────────
    database_url: str
    redis_url: str

    # ── AI (OpenRouter) ───────────────────────────────────────────────────────
    openrouter_api_key: SecretStr
    # Claude 3.5 Sonnet — non-thinking model, ~5-10s end-to-end vs ~55s
    # for K2.6 (which burns ~70% latency on internal reasoning). Anthropic
    # also tunes hard against context-leakage hallucinations — important
    # for our 39 KB persona prompt where K2.6 was inventing chart numbers
    # by mixing training-data examples into the answer. Kept K2.6 as
    # fallback so we have an alternative provider if Anthropic 5xx-s.
    default_llm_model: str = "anthropic/claude-3.5-sonnet"
    fallback_llm_model: str = "moonshotai/kimi-k2.6"
    llm_timeout: int = 60
    max_output_tokens: int = 8192

    # ── Swiss Ephemeris ───────────────────────────────────────────────────────
    swiss_ephemeris_path: Path = Path("/usr/share/swisseph")

    # ── Geocoding ─────────────────────────────────────────────────────────────
    geocoding_provider: GeocodingProvider = "nominatim"
    google_geocoder_api_key: SecretStr | None = None
    yandex_geocoder_api_key: SecretStr | None = None

    # ── KuzuDB (knowledge graph) ──────────────────────────────────────────────
    kuzu_db_path: Path = Path("./knowledge/kuzu_db")

    # ── Yandex Object Storage (S3-compatible) ─────────────────────────────────
    yc_object_storage_bucket: str = "badzi-bot-assets"
    yc_access_key_id: SecretStr
    yc_secret_access_key: SecretStr
    yc_endpoint_url: HttpUrl = HttpUrl("https://storage.yandexcloud.net")

    # ── Payments (ЮKassa) ─────────────────────────────────────────────────────
    yukassa_shop_id: SecretStr
    yukassa_secret_key: SecretStr

    # ── Monitoring (Langfuse) ─────────────────────────────────────────────────
    langfuse_public_key: SecretStr
    langfuse_secret_key: SecretStr
    langfuse_host: HttpUrl = HttpUrl("https://cloud.langfuse.com")

    # ── Web / Admin ───────────────────────────────────────────────────────────
    web_base_url: HttpUrl
    admin_basic_auth_user: str = "admin"
    admin_basic_auth_password: SecretStr

    # ── Card rendering ────────────────────────────────────────────────────────
    hieroglyphs_path: Path = Path("./assets/hieroglyphs")

    # ── Feature flags (initial values; runtime override via Redis) ────────────
    ai_enabled: bool = True
    payments_enabled: bool = True
    card_rendering_enabled: bool = True

    # ── App ───────────────────────────────────────────────────────────────────
    environment: Environment = "development"
    log_level: LogLevel = "INFO"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
