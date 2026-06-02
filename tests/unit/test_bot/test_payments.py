"""Tests for ЮKassa Telegram-native payments (Wave 7, 2026-06-02).

Covers: payload builders, the payments_live gate, pricing_kb toggling,
pre_checkout approval, and successful_payment dispatch (question plan +
forecast monthly/daily + bad payloads). Repos/finalize mocked.
"""

from __future__ import annotations

import uuid as _uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from bot.keyboards import pricing_kb
from bot.routers import payments as payments_module
from bot.routers.payments import handle_pre_checkout, handle_successful_payment
from bot.services.payments import (
    QUESTION_PLANS,
    forecast_daily_payload,
    forecast_monthly_payload,
    payments_live,
    question_payload,
)
from db.models import SubscriptionPlan

# ── payload builders ─────────────────────────────────────────────────────


def test_payload_builders_roundtrip() -> None:
    assert question_payload("monthly") == "q:monthly"
    cid = "11111111-1111-1111-1111-111111111111"
    assert forecast_monthly_payload("weekly", "edoha", cid) == f"fm:weekly:edoha:{cid}"
    assert forecast_daily_payload(4, "classic", cid) == f"fd:4:classic:{cid}"
    # Telegram caps payload at 128 bytes — our longest stays well under.
    assert len(forecast_monthly_payload("weekly", "classic", cid)) <= 128


# ── payments_live gate ────────────────────────────────────────────────────


def _settings(token: str | None, bypass: bool) -> MagicMock:
    s = MagicMock()
    s.telegram_payment_provider_token = MagicMock() if token else None
    s.forecast_free_bypass = bypass
    return s


def test_payments_live_requires_token_and_no_bypass() -> None:
    assert payments_live(_settings("381:TEST:x", bypass=False)) is True
    assert payments_live(_settings("381:TEST:x", bypass=True)) is False
    assert payments_live(_settings(None, bypass=False)) is False
    assert payments_live(_settings(None, bypass=True)) is False


# ── pricing_kb toggling ────────────────────────────────────────────────────


def _callbacks(kb: object) -> set[str]:
    return {btn.callback_data for row in kb.inline_keyboard for btn in row}  # type: ignore[attr-defined]


def test_pricing_kb_active_shows_buy_buttons_no_skip() -> None:
    data = _callbacks(pricing_kb(payments_active=True))
    assert "pay:buy:monthly" in data
    assert "pay:buy:annual" in data
    assert "pricing:skip" not in data
    assert not any(c.startswith("pay:disabled:") for c in data)


def test_pricing_kb_inactive_shows_disabled_and_skip() -> None:
    data = _callbacks(pricing_kb(payments_active=False))
    assert "pay:disabled:monthly" in data
    assert "pricing:skip" in data
    assert not any(c.startswith("pay:buy:") for c in data)


# ── pre_checkout ───────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_pre_checkout_always_approves() -> None:
    query = MagicMock()
    query.answer = AsyncMock()
    query.invoice_payload = "q:monthly"
    await handle_pre_checkout(query)
    query.answer.assert_awaited_once_with(ok=True)


# ── successful_payment ─────────────────────────────────────────────────────


def _fake_user() -> MagicMock:
    u = MagicMock()
    u.id = _uuid.uuid4()
    return u


def _fake_message(payload: str, charge: str = "charge-123") -> MagicMock:
    m = MagicMock()
    m.successful_payment = MagicMock()
    m.successful_payment.invoice_payload = payload
    m.successful_payment.provider_payment_charge_id = charge
    m.answer = AsyncMock()
    m.chat = MagicMock()
    m.chat.id = 999
    m.bot = AsyncMock()
    return m


@pytest.mark.asyncio
async def test_successful_payment_question_plan_activates_subscription(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _fake_user()
    session = MagicMock()
    session.commit = AsyncMock()
    update_mock = AsyncMock()
    monkeypatch.setattr(payments_module._sub_repo, "update_plan", update_mock)

    msg = _fake_message(question_payload("quarterly"), charge="yk-777")
    await handle_successful_payment(message=msg, session=session, user=user)

    update_mock.assert_awaited_once()
    kwargs = update_mock.call_args.kwargs
    assert kwargs["plan"] == SubscriptionPlan.quarterly
    assert kwargs["payment_provider"] == "yookassa"
    assert kwargs["payment_id"] == "yk-777"
    session.commit.assert_awaited_once()
    msg.answer.assert_awaited_once()


@pytest.mark.asyncio
async def test_successful_payment_forecast_monthly_calls_finalize(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _fake_user()
    session = MagicMock()
    chart = MagicMock()
    chart.user_id = user.id
    monkeypatch.setattr(payments_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))

    finalize_mock = AsyncMock()
    monkeypatch.setattr("bot.routers.forecast.finalize_monthly_subscription", finalize_mock)

    cid = str(_uuid.uuid4())
    msg = _fake_message(forecast_monthly_payload("weekly", "edoha", cid), charge="yk-mm")
    await handle_successful_payment(message=msg, session=session, user=user)

    finalize_mock.assert_awaited_once()
    kwargs = finalize_mock.call_args.kwargs
    assert kwargs["school"] == "edoha"
    assert kwargs["payment_provider"] == "yookassa"
    assert kwargs["payment_id"] == "yk-mm"


@pytest.mark.asyncio
async def test_successful_payment_forecast_daily_calls_finalize(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _fake_user()
    session = MagicMock()
    chart = MagicMock()
    chart.user_id = user.id
    monkeypatch.setattr(payments_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))

    finalize_mock = AsyncMock()
    monkeypatch.setattr("bot.routers.forecast.finalize_daily_subscription", finalize_mock)

    cid = str(_uuid.uuid4())
    msg = _fake_message(forecast_daily_payload(7, "classic", cid), charge="yk-dd")
    await handle_successful_payment(message=msg, session=session, user=user)

    finalize_mock.assert_awaited_once()
    kwargs = finalize_mock.call_args.kwargs
    assert kwargs["hour_local"] == 7
    assert kwargs["school"] == "classic"
    assert kwargs["payment_provider"] == "yookassa"


@pytest.mark.asyncio
async def test_successful_payment_forecast_blocks_cross_user_chart(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Paid, but the chart_id in the payload isn't this user's → refund
    notice, no subscription created."""
    user = _fake_user()
    session = MagicMock()
    other_chart = MagicMock()
    other_chart.user_id = _uuid.uuid4()  # different owner
    monkeypatch.setattr(
        payments_module._chart_repo, "get_by_id", AsyncMock(return_value=other_chart)
    )
    finalize_mock = AsyncMock()
    monkeypatch.setattr("bot.routers.forecast.finalize_monthly_subscription", finalize_mock)

    cid = str(_uuid.uuid4())
    msg = _fake_message(forecast_monthly_payload("bulk", "modern", cid))
    await handle_successful_payment(message=msg, session=session, user=user)

    finalize_mock.assert_not_awaited()
    msg.answer.assert_awaited_once()  # refund/support notice


@pytest.mark.asyncio
async def test_successful_payment_unknown_payload_is_noop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _fake_user()
    session = MagicMock()
    session.commit = AsyncMock()
    update_mock = AsyncMock()
    monkeypatch.setattr(payments_module._sub_repo, "update_plan", update_mock)

    msg = _fake_message("garbage:payload")
    await handle_successful_payment(message=msg, session=session, user=user)

    update_mock.assert_not_awaited()
    session.commit.assert_not_awaited()


def test_question_plans_cover_three_tiers() -> None:
    assert set(QUESTION_PLANS) == {"monthly", "quarterly", "annual"}
    # (price, days, label) shape
    price, days, label = QUESTION_PLANS["annual"]
    assert price == 2490
    assert days == 365
    assert isinstance(label, str)
