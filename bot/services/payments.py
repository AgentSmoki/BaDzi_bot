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
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    WebAppInfo,
)

from bot.config import Settings, get_settings
from bot.services.yookassa_api import create_payment, yookassa_api_live

# Unlimited-questions subscription tiers: plan → (price ₽, days, label).
QUESTION_PLANS: dict[str, tuple[int, int, str]] = {
    "monthly": (290, 30, "Месяц"),
    "quarterly": (990, 90, "3 месяца"),
    "annual": (2490, 365, "Год"),
}

_CURRENCY = "RUB"
_START_PARAMETER = "badzi-pay"


def payments_live(settings: Settings) -> bool:
    """True when native Telegram payments are wired: a ЮKassa provider token
    is set AND the forecast free-dev bypass is off. Нативный путь отдаёт
    только карты/ЮMoney/SberPay (без СБП)."""
    return (
        settings.telegram_payment_provider_token is not None and not settings.forecast_free_bypass
    )


def payments_active(settings: Settings) -> bool:
    """Реальная оплата доступна любым способом — нативный инвойс ИЛИ
    ЮKassa REST API (Вариант B, даёт СБП). Используется для гейта кнопок
    тарифов и текста paywall."""
    return payments_live(settings) or yookassa_api_live(settings)


async def start_yookassa_payment(
    bot: Bot,
    chat_id: int,
    *,
    amount_rub: int,
    title: str,
    description: str,
    metadata: dict[str, str],
) -> None:
    """Создать платёж в ЮKassa REST API и отправить клиенту кнопки
    «Оплатить» (на форму ЮKassa со СБП) + «Проверить оплату»
    (``pay:check:<id>`` → подтверждение поллингом в payments-роутере)."""
    settings = get_settings()
    res = await create_payment(
        settings,
        amount_rub=amount_rub,
        description=description,
        metadata=metadata,
    )
    url = res.get("confirmation_url")
    if not url:
        await bot.send_message(
            chat_id, "Не получилось создать платёж. Попробуй ещё раз чуть позже."
        )
        return
    check_cb = f"pay:check:{res['id']}"
    # Web App-кнопка: форма ЮKassa (карта/СБП) открывается оверлеем ВНУТРИ
    # Telegram, без ухода во внешний браузер. Работает в приватных чатах,
    # URL обязан быть HTTPS (confirmation_url ЮKassa — https).
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💳 Оплатить", web_app=WebAppInfo(url=url))],
            [InlineKeyboardButton(text="✅ Я оплатил — проверить", callback_data=check_cb)],
        ]
    )
    await bot.send_message(
        chat_id,
        f"<b>{title}</b>\n\n{description}\n\n"
        "Нажми «Оплатить» — форма оплаты (карта или СБП) откроется прямо здесь, "
        "в Telegram. После оплаты нажми «Проверить оплату».",
        reply_markup=kb,
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
