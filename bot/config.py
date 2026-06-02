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

    # ── AI (Yandex AI Studio — Tier 1 primary, ADR-009) ───────────────────────
    # SA: badzi-ai-sa, role ai.languageModels.user. Confirmed via probe
    # 2026-05-16: qwen3.6-35b-a3b отвечает HTTP 200 в folder b1gtu3ebh1mbqbmkqm9t.
    yc_ai_api_key: SecretStr
    yc_ai_folder_id: str
    yc_primary_model: str = "qwen3.6-35b-a3b"
    yc_qwen36_context: int = 262_144

    # ── AI (OpenRouter — Tier 2 emergency fallback, ADR-009) ──────────────────
    # Independent cloud (US/EU Anthropic nodes via OR). Triggered when YC
    # 429/5xx/timeout. Keep ~5 USD credit topped up; fallback fires sparsely.
    openrouter_api_key: SecretStr
    openrouter_emergency_model: str = "anthropic/claude-3.5-sonnet"
    openrouter_claude_context: int = 200_000

    # ── AI shared knobs ───────────────────────────────────────────────────────
    llm_timeout: int = 60
    # Hard cap on output tokens regardless of context window — defensive
    # against accidental 100k responses. Dynamic budget (ai.budget) normally
    # wins; this ceiling protects when the model gets chatty.
    max_output_tokens_ceiling: int = 32_000

    # ── Free-question allowance (Wave 7 UX 2026-05-24) ────────────────────────
    # Сколько бесплатных вопросов до pricing-screen. Раньше был bool
    # `free_question_used` (1 вопрос). Теперь counter `free_questions_used`
    # + этот лимит. После ``free_questions_limit`` вопросов бот шлёт
    # pricing_kb (тарифы неактивны + «Продолжить бесплатно»). ЮКасса
    # пока не подключена; skip доступен всем (см. pricing_kb docstring).
    free_questions_limit: int = 3

    # ── Skill router (Wave 6, ADR-010) ────────────────────────────────────────
    # Fast LLM that classifies user questions into a skill (work / relationships
    # / health / time / default), drives smart-entry parsing (text→chart),
    # journal-correction, and meeting summarisation. Uses Qwen3.6-35b-a3b
    # — same model as primary, just with tighter max_tokens budget. Decision
    # 2026-05-20: stay on Qwen3.6 across all fast-path needs (Bogdan).
    yc_fast_model: str = "qwen3.6-35b-a3b"
    # 4000 chosen with safety margin — Qwen3.6 thinking-class burns
    # `reasoning_content` first; live smoke 2026-05-20 hit ~1949 tokens
    # of reasoning on the original 2000 cap → finish_reason="length"
    # with empty content. Router JSON output itself is ~150-300 tokens,
    # so 4000 = ~3000 reasoning headroom + 1000 JSON. Cost-wise the
    # extra ceiling is free: unused budget is not billed.
    # See orchestrator._parse_result.
    yc_fast_max_tokens: int = 4_000
    # Feature flag — flip via Redis at runtime to disable the new routing
    # path and revert to the legacy single-system-prompt flow.
    skill_router_enabled: bool = True

    # ── Wave 3 — paid forecast subscriptions ──────────────────────────────────
    # While ЮKassa is not connected (1.12.3 backlog), every user is granted
    # the subscription on tap; payment_provider="free_dev_bypass". TODO ←
    # tasks.md «Wave 3 → подключение ЮKassa».
    forecast_free_bypass: bool = True
    forecast_monthly_price_rub: int = 500
    forecast_daily_price_rub: int = 900
    # Default hour the bot fires daily forecasts in the user's local time —
    # 04:00 chosen so the message is waiting when they wake up. Converted
    # to UTC at purchase time via chart.tz_offset.
    forecast_daily_default_hour_local: int = 4
    # Subscription period for both plans. Adjustable for promos.
    forecast_period_days: int = 30

    # ── Wave 4 — journal + TeleTranscribe ─────────────────────────────────────
    # Where the journal reminder fires by default (local hour). User can
    # override per-chart via the journal settings UI.
    journal_default_reminder_hour_local: int = 21
    # TeleTranscribe API — bot makes direct HTTP calls to transcribe voice
    # messages downloaded from Telegram. The MCP server is a Claude-side
    # convenience; the bot uses the same HTTP backend directly.
    tt_api_base_url: str = "http://93.77.187.33:8000"
    tt_api_key: SecretStr | None = None
    # Some self-hosted TT deployments are slow on cold-start (model load).
    # 90 s is enough for short voice messages (under 3 min).
    tt_timeout_seconds: int = 90

    # ── Swiss Ephemeris ───────────────────────────────────────────────────────
    swiss_ephemeris_path: Path = Path("/usr/share/swisseph")

    # ── Geocoding ─────────────────────────────────────────────────────────────
    geocoding_provider: GeocodingProvider = "nominatim"
    google_geocoder_api_key: SecretStr | None = None
    yandex_geocoder_api_key: SecretStr | None = None

    # ── KuzuDB (knowledge graph) ──────────────────────────────────────────────
    kuzu_db_path: Path = Path("./knowledge/kuzu_db")

    # ── Unsplash (Wave 7 Phase E — daily forecast hero image) ─────────────────
    # Free tier: 50 requests/hour. App registered 2026-05-22 as «BaDzi Bot».
    # Used by ai/day_image.py to fetch a natural-scenery photo matching the
    # day-pillar energy (e.g. misty mountain for 戊子 = Earth Yang + Water).
    # All three None-able so dev/CI works without keys; runtime gracefully
    # skips the image when access_key is missing.
    unsplash_application_id: str | None = None
    unsplash_access_key: SecretStr | None = None
    unsplash_secret_key: SecretStr | None = None

    # ── Yandex Object Storage (S3-compatible) ─────────────────────────────────
    yc_object_storage_bucket: str = "badzi-bot-assets"
    yc_access_key_id: SecretStr
    yc_secret_access_key: SecretStr
    yc_endpoint_url: HttpUrl = HttpUrl("https://storage.yandexcloud.net")

    # ── Payments (ЮKassa) ─────────────────────────────────────────────────────
    yukassa_shop_id: SecretStr
    yukassa_secret_key: SecretStr
    # Telegram-native payments (ЮKassa as provider). Provider token issued
    # via @BotFather → Payments → ЮKassa. Format: 381764678:TEST:... (test)
    # or :LIVE:... (prod). Optional so the bot boots without it; payment
    # flows are gated on this + ``forecast_free_bypass``.
    telegram_payment_provider_token: SecretStr | None = None

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
