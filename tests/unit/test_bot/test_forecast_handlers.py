"""Tests for bot.routers.forecast (Wave 3d).

Repo + session are mocked. Each test asserts the handler:
- checks chart.user_id == user.id
- builds the correct keyboard / payload
- calls subscription_repo.create with the right kind+delivery+price
"""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Message

from bot.routers import forecast as forecast_module
from bot.routers.forecast import (
    _hour_local_to_utc,
    handle_cancel_confirm,
    handle_daily_confirm,
    handle_forecast_list,
    handle_forecast_show,
    handle_monthly_confirm,
)
from db.models import ForecastKind, MonthlyDelivery, SubscriptionStatus

# ── Fixtures ─────────────────────────────────────────────────────────────


@pytest.fixture
def fake_user() -> MagicMock:
    u = MagicMock()
    u.id = _uuid.uuid4()
    u.telegram_id = 545371253
    return u


@pytest.fixture
def fake_session() -> MagicMock:
    s = MagicMock()
    s.commit = AsyncMock()
    return s


def _fake_chart(*, user_id: _uuid.UUID, tz_offset: float = 3.0) -> MagicMock:
    c = MagicMock()
    c.id = _uuid.uuid4()
    c.user_id = user_id
    c.tz_offset = tz_offset
    return c


def _fake_callback(data: str) -> MagicMock:
    cb = MagicMock()
    cb.message = MagicMock(spec=Message)
    cb.message.answer = AsyncMock()
    cb.message.edit_text = AsyncMock()
    cb.answer = AsyncMock()
    cb.data = data
    return cb


# ── Utility ──────────────────────────────────────────────────────────────


def test_hour_local_to_utc_moscow() -> None:
    """Moscow (+3) at 04:00 local → 01:00 UTC."""
    assert _hour_local_to_utc(4, 3.0) == 1


def test_hour_local_to_utc_wraps_around_midnight() -> None:
    """LA (-7) at 04:00 local → 11:00 UTC; midnight wrap test."""
    # If hour_local=4 and offset=-7 → 4-(-7)=11 → 11 UTC.
    assert _hour_local_to_utc(4, -7.0) == 11
    # Negative case: hour_local=2 and offset=10 → (2-10) % 24 = 16 UTC.
    assert _hour_local_to_utc(2, 10.0) == 16


def test_hour_local_to_utc_handles_half_hour_offsets() -> None:
    """India +5:30 — we round to nearest hour since cron is hour-only."""
    # 4 - 5.5 = -1.5 → int(-1.5) = -1 → -1 % 24 = 23.
    assert _hour_local_to_utc(4, 5.5) == 23


# ── forecast:show ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_show_displays_menu(
    monkeypatch: pytest.MonkeyPatch, fake_session: MagicMock, fake_user: MagicMock
) -> None:
    chart = _fake_chart(user_id=fake_user.id)
    monkeypatch.setattr(forecast_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))

    cb = _fake_callback(f"forecast:show:{chart.id}")
    await handle_forecast_show(callback=cb, session=fake_session, user=fake_user)

    cb.message.answer.assert_awaited_once()
    text, kwargs = cb.message.answer.call_args.args[0], cb.message.answer.call_args.kwargs
    assert "Прогнозы Анастасии" in text
    assert "500" in text and "900" in text
    kb_data = {btn.callback_data for row in kwargs["reply_markup"].inline_keyboard for btn in row}
    assert f"forecast:buy_monthly:{chart.id}" in kb_data
    assert f"forecast:buy_daily:{chart.id}" in kb_data
    assert f"forecast:list:{chart.id}" in kb_data


@pytest.mark.asyncio
async def test_show_blocks_cross_user_chart(
    monkeypatch: pytest.MonkeyPatch, fake_session: MagicMock, fake_user: MagicMock
) -> None:
    chart = _fake_chart(user_id=_uuid.uuid4())  # other user
    monkeypatch.setattr(forecast_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))

    cb = _fake_callback(f"forecast:show:{chart.id}")
    await handle_forecast_show(callback=cb, session=fake_session, user=fake_user)

    cb.message.answer.assert_not_awaited()
    cb.answer.assert_awaited_once()


# ── Monthly purchase ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_monthly_confirm_creates_weekly_subscription(
    monkeypatch: pytest.MonkeyPatch, fake_session: MagicMock, fake_user: MagicMock
) -> None:
    chart = _fake_chart(user_id=fake_user.id)
    monkeypatch.setattr(forecast_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))
    create_mock = AsyncMock(return_value=MagicMock(id=_uuid.uuid4()))
    monkeypatch.setattr(forecast_module._sub_repo, "create", create_mock)

    cb = _fake_callback(f"forecast:monthly_confirm:{chart.id}:weekly")
    await handle_monthly_confirm(callback=cb, session=fake_session, user=fake_user)

    create_mock.assert_awaited_once()
    kwargs = create_mock.call_args.kwargs
    assert kwargs["kind"] == ForecastKind.monthly
    assert kwargs["monthly_delivery"] == MonthlyDelivery.weekly
    assert kwargs["price_rub"] == 500
    assert kwargs["payment_provider"] == "free_dev_bypass"
    fake_session.commit.assert_awaited_once()
    answer_text = cb.message.answer.call_args.args[0]
    assert "активирована" in answer_text.lower()
    assert "раз в неделю" in answer_text


@pytest.mark.asyncio
async def test_monthly_confirm_creates_bulk_subscription(
    monkeypatch: pytest.MonkeyPatch, fake_session: MagicMock, fake_user: MagicMock
) -> None:
    chart = _fake_chart(user_id=fake_user.id)
    monkeypatch.setattr(forecast_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))
    create_mock = AsyncMock(return_value=MagicMock(id=_uuid.uuid4()))
    monkeypatch.setattr(forecast_module._sub_repo, "create", create_mock)

    cb = _fake_callback(f"forecast:monthly_confirm:{chart.id}:bulk")
    await handle_monthly_confirm(callback=cb, session=fake_session, user=fake_user)

    kwargs = create_mock.call_args.kwargs
    assert kwargs["monthly_delivery"] == MonthlyDelivery.bulk


@pytest.mark.asyncio
async def test_monthly_confirm_rejects_invalid_delivery(
    monkeypatch: pytest.MonkeyPatch, fake_session: MagicMock, fake_user: MagicMock
) -> None:
    chart = _fake_chart(user_id=fake_user.id)
    monkeypatch.setattr(forecast_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))
    create_mock = AsyncMock()
    monkeypatch.setattr(forecast_module._sub_repo, "create", create_mock)

    cb = _fake_callback(f"forecast:monthly_confirm:{chart.id}:hourly")  # garbage
    await handle_monthly_confirm(callback=cb, session=fake_session, user=fake_user)

    create_mock.assert_not_awaited()


# ── Daily purchase ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_daily_confirm_creates_subscription_with_utc_hour(
    monkeypatch: pytest.MonkeyPatch, fake_session: MagicMock, fake_user: MagicMock
) -> None:
    chart = _fake_chart(user_id=fake_user.id, tz_offset=3.0)
    monkeypatch.setattr(forecast_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))
    create_mock = AsyncMock(return_value=MagicMock(id=_uuid.uuid4()))
    monkeypatch.setattr(forecast_module._sub_repo, "create", create_mock)

    cb = _fake_callback(f"forecast:daily_confirm:{chart.id}:4")
    await handle_daily_confirm(callback=cb, session=fake_session, user=fake_user)

    create_mock.assert_awaited_once()
    kwargs = create_mock.call_args.kwargs
    assert kwargs["kind"] == ForecastKind.daily
    assert kwargs["daily_send_hour_utc"] == 1  # 4 local - 3 tz = 1 UTC
    assert kwargs["price_rub"] == 900


@pytest.mark.asyncio
async def test_daily_confirm_rejects_invalid_hour(
    monkeypatch: pytest.MonkeyPatch, fake_session: MagicMock, fake_user: MagicMock
) -> None:
    chart = _fake_chart(user_id=fake_user.id)
    monkeypatch.setattr(forecast_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))
    create_mock = AsyncMock()
    monkeypatch.setattr(forecast_module._sub_repo, "create", create_mock)

    cb = _fake_callback(f"forecast:daily_confirm:{chart.id}:99")  # bad hour
    await handle_daily_confirm(callback=cb, session=fake_session, user=fake_user)

    create_mock.assert_not_awaited()


# ── List + cancel ────────────────────────────────────────────────────────


def _fake_sub(*, user_id: _uuid.UUID, kind: ForecastKind) -> MagicMock:
    s = MagicMock()
    s.id = _uuid.uuid4()
    s.user_id = user_id
    s.kind = kind
    s.monthly_delivery = MonthlyDelivery.weekly if kind == ForecastKind.monthly else None
    s.daily_send_hour_utc = 1 if kind == ForecastKind.daily else None
    s.status = SubscriptionStatus.active
    s.expires_at = datetime.now() + timedelta(days=20)
    return s


@pytest.mark.asyncio
async def test_list_shows_active_subs(
    monkeypatch: pytest.MonkeyPatch, fake_session: MagicMock, fake_user: MagicMock
) -> None:
    chart = _fake_chart(user_id=fake_user.id)
    sub = _fake_sub(user_id=fake_user.id, kind=ForecastKind.daily)
    monkeypatch.setattr(forecast_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))
    monkeypatch.setattr(
        forecast_module._sub_repo, "list_active_for_chart", AsyncMock(return_value=[sub])
    )

    cb = _fake_callback(f"forecast:list:{chart.id}")
    await handle_forecast_list(callback=cb, session=fake_session, user=fake_user)

    answer_text = cb.message.answer.call_args.args[0]
    assert "Активные подписки" in answer_text
    assert "Дневной прогноз" in answer_text


@pytest.mark.asyncio
async def test_list_empty_state(
    monkeypatch: pytest.MonkeyPatch, fake_session: MagicMock, fake_user: MagicMock
) -> None:
    chart = _fake_chart(user_id=fake_user.id)
    monkeypatch.setattr(forecast_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))
    monkeypatch.setattr(
        forecast_module._sub_repo, "list_active_for_chart", AsyncMock(return_value=[])
    )

    cb = _fake_callback(f"forecast:list:{chart.id}")
    await handle_forecast_list(callback=cb, session=fake_session, user=fake_user)
    assert "пока нет" in cb.message.answer.call_args.args[0].lower()


@pytest.mark.asyncio
async def test_cancel_confirm_calls_repo_cancel(
    monkeypatch: pytest.MonkeyPatch, fake_session: MagicMock, fake_user: MagicMock
) -> None:
    sub = _fake_sub(user_id=fake_user.id, kind=ForecastKind.daily)
    chart_id = _uuid.uuid4()
    monkeypatch.setattr(forecast_module._sub_repo, "get_by_id", AsyncMock(return_value=sub))
    cancel_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(forecast_module._sub_repo, "cancel", cancel_mock)

    cb = _fake_callback(f"forecast:cancel_confirm:{sub.id}:{chart_id}")
    await handle_cancel_confirm(callback=cb, session=fake_session, user=fake_user)

    cancel_mock.assert_awaited_once_with(fake_session, sub.id)
    fake_session.commit.assert_awaited_once()
    cb.message.edit_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_cancel_confirm_blocks_cross_user_sub(
    monkeypatch: pytest.MonkeyPatch, fake_session: MagicMock, fake_user: MagicMock
) -> None:
    sub = _fake_sub(user_id=_uuid.uuid4(), kind=ForecastKind.daily)  # someone else's
    chart_id = _uuid.uuid4()
    monkeypatch.setattr(forecast_module._sub_repo, "get_by_id", AsyncMock(return_value=sub))
    cancel_mock = AsyncMock()
    monkeypatch.setattr(forecast_module._sub_repo, "cancel", cancel_mock)

    cb = _fake_callback(f"forecast:cancel_confirm:{sub.id}:{chart_id}")
    await handle_cancel_confirm(callback=cb, session=fake_session, user=fake_user)

    cancel_mock.assert_not_awaited()
    cb.answer.assert_awaited_once()
