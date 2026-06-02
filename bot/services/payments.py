"""ЮKassa payments via native Telegram Payments (Wave 7, 2026-06-02).

No webhook / no FastAPI: the bot calls ``send_invoice`` with a ЮKassa
provider token (issued in @BotFather), Telegram renders the ЮKassa form,
and the result comes back as ``pre_checkout_query`` → ``successful_payment``
updates handled in ``bot/routers/payments.py``.

This module is router-free so both ``forecast.py`` and ``consultation.py``
can import the invoice helpers without import cycles.

Invoice ``payload`` encodes what was bought (≤128 bytes, Telegram limit):
- questions:        ``q:<plan>``                       (monthly|quarterly|annual)
- forecast monthly: ``fm:<delivery>:<school>:<chart_id>``
- forecast daily:   ``fd:<hour_local>:<school>:<chart_id>``
"""

from __future__ import annotations

from aiogram import Bot
from aiogram.types import LabeledPrice

from bot.config import Settings

# Unlimited-questions subscription tiers: plan → (price ₽, days, label).
QUESTION_PLANS: dict[str, tuple[int, int, str]] = {
    "monthly": (290, 30, "Месяц"),
    "quarterly": (990, 90, "3 месяца"),
    "annual": (2490, 365, "Год"),
}

_CURRENCY = "RUB"
_START_PARAMETER = "badzi-pay"


def payments_live(settings: Settings) -> bool:
    """True when real payments are wired: a ЮKassa provider token is set
    AND the forecast free-dev bypass is off. A single gate flips both
    forecast and question payments live at once (см. план)."""
    return (
        settings.telegram_payment_provider_token is not None and not settings.forecast_free_bypass
    )


async def send_invoice(
    bot: Bot,
    chat_id: int,
    *,
    title: str,
    description: str,
    amount_rub: int,
    payload: str,
    provider_token: str,
) -> None:
    """Send a single-line-item RUB invoice. Amount converted to the
    smallest currency unit (kopecks) as Telegram requires."""
    await bot.send_invoice(
        chat_id=chat_id,
        title=title,
        description=description,
        payload=payload,
        provider_token=provider_token,
        currency=_CURRENCY,
        prices=[LabeledPrice(label=title, amount=amount_rub * 100)],
        start_parameter=_START_PARAMETER,
    )


# ── Payload builders ──────────────────────────────────────────────────────


def question_payload(plan: str) -> str:
    return f"q:{plan}"


def forecast_monthly_payload(delivery: str, school: str, chart_id: str) -> str:
    return f"fm:{delivery}:{school}:{chart_id}"


def forecast_daily_payload(hour_local: int, school: str, chart_id: str) -> str:
    return f"fd:{hour_local}:{school}:{chart_id}"
