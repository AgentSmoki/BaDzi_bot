"""ЮKassa REST API payments (Вариант B — единственный путь с СБП).

Нативный Telegram-инвойс (``Bot.send_invoice``) показывает только карты,
ЮMoney и SberPay — СБП там недоступен (подтверждено поддержкой ЮKassa).
Чтобы дать клиенту СБП, создаём платёж через ЮKassa REST API
(``POST /v3/payments``), отдаём ему ``confirmation_url`` (кнопка
«Оплатить»), а подтверждаем оплату поллингом ``GET /v3/payments/{id}``
по нажатию «Проверить оплату». Публичный webhook не нужен.

Что куплено — кодируем в ``metadata`` платежа, чтобы при подтверждении
знать, какую подписку активировать (роутер ``bot/routers/payments.py``).
"""

from __future__ import annotations

import base64
import uuid
from typing import Any

import httpx
import structlog

from bot.config import Settings

logger = structlog.get_logger(__name__)

_API_BASE = "https://api.yookassa.ru/v3"
_TIMEOUT = 30.0


def yookassa_api_live(settings: Settings) -> bool:
    """True когда оплата через ЮKassa API реально включена: задан флаг,
    есть shop_id + секретный ключ, и выключен free-dev-bypass."""
    return (
        settings.yookassa_api_enabled
        and bool(settings.yukassa_shop_id.get_secret_value())
        and bool(settings.yukassa_secret_key.get_secret_value())
        and not settings.forecast_free_bypass
    )


def _auth_header(settings: Settings) -> str:
    """ЮKassa использует HTTP Basic: ``shopId:secretKey``."""
    shop = settings.yukassa_shop_id.get_secret_value()
    secret = settings.yukassa_secret_key.get_secret_value()
    token = base64.b64encode(f"{shop}:{secret}".encode()).decode()
    return f"Basic {token}"


def new_idempotence_key() -> str:
    """Уникальный ключ идемпотентности на одно создание платежа —
    защищает от двойного списания при ретрае сети."""
    return uuid.uuid4().hex


async def create_payment(
    settings: Settings,
    *,
    amount_rub: int,
    description: str,
    metadata: dict[str, str],
    idempotence_key: str | None = None,
) -> dict[str, Any]:
    """Создать платёж и вернуть ``{id, status, confirmation_url}``.

    ``confirmation: redirect`` → ЮKassa отдаёт ссылку на свою форму
    оплаты (там доступен СБП); после оплаты клиента возвращает на
    ``settings.yookassa_return_url`` (deep-link обратно в бота).
    """
    payload: dict[str, Any] = {
        "amount": {"value": f"{amount_rub}.00", "currency": "RUB"},
        "capture": True,
        "confirmation": {"type": "redirect", "return_url": settings.yookassa_return_url},
        "description": description[:128],
        "metadata": metadata,
    }
    # Фискализация (54-ФЗ): если задан email для чека — прикладываем receipt,
    # иначе магазин с включёнными чеками вернёт 400 «Receipt is missing».
    if settings.yookassa_receipt_email:
        payload["receipt"] = {
            "customer": {"email": settings.yookassa_receipt_email},
            "items": [
                {
                    "description": description[:128],
                    "quantity": "1.00",
                    "amount": {"value": f"{amount_rub}.00", "currency": "RUB"},
                    "vat_code": settings.yookassa_vat_code,
                    "payment_mode": "full_payment",
                    "payment_subject": "service",
                }
            ],
        }
    headers = {
        "Authorization": _auth_header(settings),
        "Idempotence-Key": idempotence_key or new_idempotence_key(),
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.post(f"{_API_BASE}/payments", json=payload, headers=headers)
    resp.raise_for_status()
    data = resp.json()
    confirmation = data.get("confirmation") or {}
    result = {
        "id": data["id"],
        "status": data["status"],
        "confirmation_url": confirmation.get("confirmation_url"),
    }
    logger.info("yookassa.payment_created", payment_id=result["id"], status=result["status"])
    return result


async def get_payment(settings: Settings, payment_id: str) -> dict[str, Any]:
    """Вернуть текущее состояние платежа: ``{id, status, paid, metadata}``.

    ``status`` ∈ pending | waiting_for_capture | succeeded | canceled.
    Активируем подписку только при ``succeeded``.
    """
    headers = {"Authorization": _auth_header(settings)}
    async with httpx.AsyncClient(timeout=_TIMEOUT) as client:
        resp = await client.get(f"{_API_BASE}/payments/{payment_id}", headers=headers)
    resp.raise_for_status()
    data = resp.json()
    return {
        "id": data["id"],
        "status": data["status"],
        "paid": bool(data.get("paid", False)),
        "metadata": data.get("metadata") or {},
    }
