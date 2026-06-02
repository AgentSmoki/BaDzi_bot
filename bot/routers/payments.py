"""Telegram-native ЮKassa payment handlers (Wave 7, 2026-06-02).

Two updates close the loop:
- ``pre_checkout_query`` — Telegram asks the bot to confirm the order is
  still valid; we always approve (the payload was built by us moments ago).
- ``message.successful_payment`` — money captured by ЮKassa; we parse the
  invoice payload and activate the matching subscription.

Subscription creation for forecasts is delegated to the finalize helpers
in ``forecast.py`` (lazy import to avoid an import cycle); question-tier
subscriptions are activated here directly via ``SubscriptionRepository``.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import structlog
from aiogram import F, Router
from aiogram.types import Message, PreCheckoutQuery
from sqlalchemy.ext.asyncio import AsyncSession

from bot.services.payments import QUESTION_PLANS
from db.models import SubscriptionPlan, SubscriptionStatus, User
from db.repositories.chart_repo import ChartRepository
from db.repositories.subscription_repo import SubscriptionRepository

logger = structlog.get_logger(__name__)

payments_router = Router(name="payments")
_chart_repo = ChartRepository()
_sub_repo = SubscriptionRepository()

_PAYMENT_PROVIDER = "yookassa"


@payments_router.pre_checkout_query()
async def handle_pre_checkout(query: PreCheckoutQuery) -> None:
    """Approve every pre-checkout — the payload is ours, freshly built,
    and nothing about the order can have gone stale in seconds. ЮKassa
    rejects the charge itself on card problems."""
    await query.answer(ok=True)
    logger.info("payment.pre_checkout_ok", payload=query.invoice_payload)


@payments_router.message(F.successful_payment)
async def handle_successful_payment(
    message: Message,
    session: AsyncSession,
    user: User,
) -> None:
    """Money captured — activate the subscription encoded in the payload."""
    sp = message.successful_payment
    if sp is None:  # pragma: no cover — guarded by the F.successful_payment filter
        return
    payload = sp.invoice_payload
    charge_id = sp.provider_payment_charge_id
    parts = payload.split(":")
    kind = parts[0] if parts else ""

    if kind == "q":
        await _activate_question_plan(message, session, user, parts, charge_id)
        return

    if kind in ("fm", "fd"):
        await _activate_forecast(message, session, user, kind, parts, charge_id)
        return

    logger.warning("payment.unknown_payload", payload=payload, charge_id=charge_id)


async def _activate_question_plan(
    message: Message,
    session: AsyncSession,
    user: User,
    parts: list[str],
    charge_id: str,
) -> None:
    plan_raw = parts[1] if len(parts) > 1 else ""
    spec = QUESTION_PLANS.get(plan_raw)
    if spec is None:
        logger.warning("payment.bad_question_plan", plan=plan_raw, charge_id=charge_id)
        return
    _price, days, label = spec
    expires_at = datetime.now(tz=None) + timedelta(days=days)
    await _sub_repo.update_plan(
        session,
        user.id,
        plan=SubscriptionPlan(plan_raw),
        status=SubscriptionStatus.active,
        expires_at=expires_at,
        payment_provider=_PAYMENT_PROVIDER,
        payment_id=charge_id,
    )
    await session.commit()
    logger.info(
        "payment.question_plan_activated",
        plan=plan_raw,
        user_id=str(user.id),
        charge_id=charge_id,
    )
    await message.answer(
        f"<b>✓ Подписка «{label}» активирована</b>\n\n"
        f"Безлимитные вопросы Анастасии до {expires_at.strftime('%d.%m.%Y')}. "
        "Спасибо! Можете задавать вопрос."
    )


async def _activate_forecast(
    message: Message,
    session: AsyncSession,
    user: User,
    kind: str,
    parts: list[str],
    charge_id: str,
) -> None:
    # fm:<delivery>:<school>:<chart_id>  /  fd:<hour_local>:<school>:<chart_id>
    import uuid

    from bot.routers.forecast import (
        finalize_daily_subscription,
        finalize_monthly_subscription,
    )
    from db.models import MonthlyDelivery

    if len(parts) < 4:
        logger.warning("payment.bad_forecast_payload", parts=parts, charge_id=charge_id)
        return
    arg, school, chart_id_raw = parts[1], parts[2], parts[3]
    try:
        chart_id = uuid.UUID(chart_id_raw)
    except ValueError:
        logger.warning("payment.bad_chart_id", raw=chart_id_raw, charge_id=charge_id)
        return

    chart = await _chart_repo.get_by_id(session, chart_id)
    if chart is None or chart.user_id != user.id:
        logger.warning("payment.forecast_chart_missing", chart_id=chart_id_raw, charge_id=charge_id)
        await message.answer(
            "Оплата прошла, но карта не найдена. Напишите в поддержку — вернём средства."
        )
        return

    if message.bot is None:  # pragma: no cover — real Message always carries bot
        return

    if kind == "fm":
        await finalize_monthly_subscription(
            message.bot,
            message.chat.id,
            session,
            user_id=user.id,
            chart=chart,
            delivery=MonthlyDelivery(arg),
            school=school,
            payment_provider=_PAYMENT_PROVIDER,
            payment_id=charge_id,
        )
    else:  # fd
        await finalize_daily_subscription(
            message.bot,
            message.chat.id,
            session,
            user_id=user.id,
            chart=chart,
            hour_local=int(arg),
            school=school,
            payment_provider=_PAYMENT_PROVIDER,
            payment_id=charge_id,
        )
    logger.info(
        "payment.forecast_activated",
        kind=kind,
        user_id=str(user.id),
        chart_id=chart_id_raw,
        charge_id=charge_id,
    )
