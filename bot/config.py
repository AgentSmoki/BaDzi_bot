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

    # ── AI (OpenRouter — единый провайдер, ADR-012) ───────────────────────────
    # Вся LLM-генерация идёт через OpenRouter. Tier 1 — основной ответчик
    # (Qwen3.7-Plus), Tier 2 — emergency fallback на 429/5xx/timeout Tier 1
    # (Gemini 2.5 Pro — другая семья моделей, чтобы сбой одной не клал обе
    # ступени). Держать баланс OpenRouter пополненным — теперь через него
    # идёт весь трафик, не только fallback.
    openrouter_api_key: SecretStr
    primary_model: str = "qwen/qwen3.7-plus"
    primary_context: int = 1_000_000
    emergency_model: str = "google/gemini-2.5-pro"
    emergency_context: int = 1_000_000

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

    # ── Fast LLM (skill-router, smart-entry parse, concept-extract, day-image) ─
    # Дешёвая быстрая модель для классификации/парсинга/JSON-выхода.
    # Gemini Flash: дёшево, быстро, нативный JSON-режим (ADR-012). Та же
    # модель обслуживает skill-router, smart-entry (text→chart),
    # concept-extract для RAG и day-image query.
    fast_model: str = "google/gemini-2.5-flash"
    # Запас под reasoning у thinking-моделей; JSON-выход ~150-300 токенов.
    # Неиспользованный бюджет не биллится. См. orchestrator._parse_result.
    fast_max_tokens: int = 4_000
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
    # convenience; the bot uses the same HTTP backend directly. После переезда
    # на Timeweb (2026-06) — стабильное имя Cloudflare-туннеля TT (старый YC
    # 93.77.187.33 удалён). На том же сервере можно и host-gateway, но имя
    # туннеля стабильнее.
    tt_api_base_url: str = "https://api.neuroimpuls.ru"
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

    # ── Payments (ЮKassa) ─────────────────────────────────────────────────────
    yukassa_shop_id: SecretStr
    yukassa_secret_key: SecretStr
    # Telegram-native payments (ЮKassa as provider). Provider token issued
    # via @BotFather → Payments → ЮKassa. Format: 381764678:TEST:... (test)
    # or :LIVE:... (prod). Optional so the bot boots without it; payment
    # flows are gated on this + ``forecast_free_bypass``.
    telegram_payment_provider_token: SecretStr | None = None
    # ── Payments via ЮKassa REST API (Вариант B — единственный путь с СБП) ──
    # Нативный Telegram-инвойс показывает только карты/ЮMoney/SberPay.
    # Когда ``yookassa_api_enabled=True`` и заданы shop_id+secret_key —
    # платежи создаются через ЮKassa API (POST /v3/payments): кнопка
    # «Оплатить» (confirmation_url) + подтверждение поллингом GET
    # /v3/payments/{id} по кнопке «Проверить оплату». СБП доступен на форме.
    yookassa_api_enabled: bool = False
    yookassa_return_url: str = "https://t.me/EdoHa_Badzi_bot"
    # Фискализация (54-ФЗ): если у магазина включены чеки, ЮKassa требует
    # ``receipt`` в каждом платеже. Контакт покупателя для чека и код НДС.
    # vat_code: 1 = без НДС (УСН), 6 = НДС 20/120 и т.д.
    yookassa_receipt_email: str = ""
    yookassa_vat_code: int = 1

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
