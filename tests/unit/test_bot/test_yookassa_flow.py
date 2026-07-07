"""Tests for the ЮKassa REST API payment flow (Вариант B / СБП):
``payments_active`` gate, ``start_yookassa_payment``, the ``pay:check:*``
handler and the redis double-activation guard.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import fakeredis.aioredis
import httpx
import pytest
from aiogram.types import Message

from ai.context import HistoryStore
from bot.routers import payments as payments_module
from bot.routers.payments import handle_pay_check
from bot.services import payments as payments_service


def _settings(*, api: bool, token: object = None, bypass: bool = False) -> MagicMock:
    s = MagicMock()
    s.yookassa_api_enabled = api
    s.yukassa_shop_id = MagicMock(get_secret_value=lambda: "1378794")
    s.yukassa_secret_key = MagicMock(get_secret_value=lambda: "live_secret")
    s.forecast_free_bypass = bypass
    s.telegram_payment_provider_token = token
    return s


# ── payments_active gate ────────────────────────────────────────────────────


def test_payments_active_true_when_api_live() -> None:
    assert payments_service.payments_active(_settings(api=True)) is True


def test_payments_active_true_when_native_live() -> None:
    s = _settings(api=False, token=MagicMock())
    assert payments_service.payments_active(s) is True


def test_payments_active_false_when_bypass_and_no_token() -> None:
    assert payments_service.payments_active(_settings(api=True, bypass=True)) is False


# ── redis double-activation guard ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_try_mark_payment_is_idempotent() -> None:
    store = HistoryStore(fakeredis.aioredis.FakeRedis(decode_responses=True))
    assert await store.try_mark_payment("pay-1") is True
    assert await store.try_mark_payment("pay-1") is False  # уже обработан
    assert await store.try_mark_payment("pay-2") is True  # другой платёж


# ── start_yookassa_payment ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_start_payment_sends_pay_and_check_buttons(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(payments_service, "get_settings", lambda: _settings(api=True))
    monkeypatch.setattr(
        payments_service,
        "create_payment",
        AsyncMock(return_value={"id": "pay-77", "confirmation_url": "https://yoomoney/x"}),
    )
    bot = MagicMock()
    bot.send_message = AsyncMock()
    await payments_service.start_yookassa_payment(
        bot,
        555,
        amount_rub=290,
        title="Безлимит",
        description="desc",
        metadata={"kind": "q", "plan": "monthly"},
    )
    bot.send_message.assert_awaited_once()
    kb = bot.send_message.call_args.kwargs["reply_markup"]
    cbs = [b.callback_data for row in kb.inline_keyboard for b in row if b.callback_data]
    webapp_urls = [b.web_app.url for row in kb.inline_keyboard for b in row if b.web_app]
    assert "pay:check:pay-77" in cbs
    assert "https://yoomoney/x" in webapp_urls


# ── handle_pay_check ────────────────────────────────────────────────────────


def _check_callback() -> MagicMock:
    cb = MagicMock()
    cb.data = "pay:check:pay-9"
    cb.message = MagicMock(spec=Message)
    cb.message.answer = AsyncMock()
    cb.answer = AsyncMock()
    return cb


@pytest.mark.asyncio
async def test_pay_check_activates_question_plan_on_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(payments_module, "get_settings", lambda: _settings(api=True))
    monkeypatch.setattr(
        payments_module,
        "get_payment",
        AsyncMock(
            return_value={
                "id": "pay-9",
                "status": "succeeded",
                "metadata": {"kind": "q", "plan": "monthly"},
            }
        ),
    )
    update_plan = AsyncMock()
    monkeypatch.setattr(payments_module._sub_repo, "update_plan", update_plan)
    session = MagicMock()
    session.commit = AsyncMock()
    user = MagicMock()
    user.id = MagicMock()
    history = MagicMock()
    history.try_mark_payment = AsyncMock(return_value=True)
    cb = _check_callback()

    await handle_pay_check(callback=cb, session=session, user=user, history_store=history)

    update_plan.assert_awaited_once()
    session.commit.assert_awaited()
    cb.message.answer.assert_awaited()  # «Подписка активирована»


@pytest.mark.asyncio
async def test_pay_check_pending_does_not_activate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(payments_module, "get_settings", lambda: _settings(api=True))
    monkeypatch.setattr(
        payments_module,
        "get_payment",
        AsyncMock(return_value={"id": "pay-9", "status": "pending", "metadata": {}}),
    )
    update_plan = AsyncMock()
    monkeypatch.setattr(payments_module._sub_repo, "update_plan", update_plan)
    history = MagicMock()
    history.try_mark_payment = AsyncMock(return_value=True)
    cb = _check_callback()

    await handle_pay_check(
        callback=cb, session=MagicMock(), user=MagicMock(), history_store=history
    )

    update_plan.assert_not_awaited()
    history.try_mark_payment.assert_not_awaited()  # до guard не дошли
    assert cb.answer.call_args.kwargs.get("show_alert") is True


@pytest.mark.asyncio
async def test_pay_check_double_tap_blocked_by_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(payments_module, "get_settings", lambda: _settings(api=True))
    monkeypatch.setattr(
        payments_module,
        "get_payment",
        AsyncMock(
            return_value={
                "id": "pay-9",
                "status": "succeeded",
                "metadata": {"kind": "q", "plan": "monthly"},
            }
        ),
    )
    update_plan = AsyncMock()
    monkeypatch.setattr(payments_module._sub_repo, "update_plan", update_plan)
    history = MagicMock()
    history.try_mark_payment = AsyncMock(return_value=False)  # уже активирован
    cb = _check_callback()

    await handle_pay_check(
        callback=cb, session=MagicMock(), user=MagicMock(), history_store=history
    )

    update_plan.assert_not_awaited()
    assert cb.answer.call_args.kwargs.get("show_alert") is True


@pytest.mark.asyncio
async def test_pay_check_network_error_is_graceful(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(payments_module, "get_settings", lambda: _settings(api=True))
    monkeypatch.setattr(
        payments_module,
        "get_payment",
        AsyncMock(side_effect=httpx.ConnectError("down")),
    )
    history = MagicMock()
    history.try_mark_payment = AsyncMock()
    cb = _check_callback()

    await handle_pay_check(
        callback=cb, session=MagicMock(), user=MagicMock(), history_store=history
    )

    assert cb.answer.call_args.kwargs.get("show_alert") is True
