"""Tests for bot.routers.forecast (Wave 3d + 2026-05-20 hotfix).

Callbacks short (``fc:*``) with chart_id stashed in FSM data — see
``_FSM_FORECAST_CHART`` in the router. Tests prime the FSM by calling
the show handler first or seeding ``state.update_data`` directly.

Repos + session mocked. Each test asserts the handler:
- enforces ownership (chart.user_id == user.id, sub.user_id == user.id)
- calls subscription_repo.create with the right kind+delivery+price
- pulls chart_id from FSM correctly
"""

from __future__ import annotations

import uuid as _uuid
from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import Message

from bot.routers import forecast as forecast_module
from bot.routers.forecast import (
    _FSM_FORECAST_CHART,
    _hour_local_to_utc,
    handle_buy_daily,
    handle_buy_monthly,
    handle_cancel_confirm,
    handle_daily_confirm,
    handle_daily_school_confirm,
    handle_forecast_list,
    handle_forecast_show,
    handle_monthly_confirm,
    handle_monthly_school_confirm,
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


@pytest.fixture(autouse=True)
def _stub_journal_settings_toggle(monkeypatch: pytest.MonkeyPatch) -> None:
    """2026-05-21 — forecast handlers now auto-enable important-date
    alerts after creating a subscription (Wave 4e ↔ W3 link). The
    real toggle hits the DB through ChartJournalSettings.get_or_create
    which a MagicMock session can't satisfy, so stub it on all tests."""
    monkeypatch.setattr(
        forecast_module._journal_settings_repo,
        "toggle_important_dates",
        AsyncMock(),
    )


@pytest.fixture
def fake_state() -> MagicMock:
    s = MagicMock()
    data: dict[str, Any] = {}
    s._data = data

    async def _get_data() -> dict[str, Any]:
        return dict(data)

    async def _update_data(**kw: Any) -> None:
        data.update(kw)

    s.get_data = _get_data
    s.update_data = _update_data
    return s


def _fake_chart(
    *, user_id: _uuid.UUID, tz_offset: float = 3.0, default_school: str | None = None
) -> MagicMock:
    c = MagicMock()
    c.id = _uuid.uuid4()
    c.user_id = user_id
    c.tz_offset = tz_offset
    c.default_school = default_school
    return c


def _fake_callback(data: str) -> MagicMock:
    cb = MagicMock()
    cb.message = MagicMock(spec=Message)
    cb.message.answer = AsyncMock()
    cb.message.edit_text = AsyncMock()
    # Finalize helpers confirm via message.bot.send_message + message.chat.id.
    cb.message.chat = MagicMock()
    cb.message.chat.id = 545371253
    cb.message.bot = AsyncMock()
    cb.answer = AsyncMock()
    cb.data = data
    return cb


async def _stash_chart_in_state(state: MagicMock, chart_id: _uuid.UUID) -> None:
    await state.update_data(**{_FSM_FORECAST_CHART: str(chart_id)})


# ── Utility ──────────────────────────────────────────────────────────────


def test_hour_local_to_utc_moscow() -> None:
    """Moscow (+3) at 04:00 local → 01:00 UTC."""
    assert _hour_local_to_utc(4, 3.0) == 1


def test_hour_local_to_utc_wraps_around_midnight() -> None:
    """LA (-7) at 04:00 local → 11:00 UTC; midnight wrap test."""
    assert _hour_local_to_utc(4, -7.0) == 11
    assert _hour_local_to_utc(2, 10.0) == 16


def test_hour_local_to_utc_handles_half_hour_offsets() -> None:
    """India +5:30 — we round to nearest hour since cron is hour-only."""
    assert _hour_local_to_utc(4, 5.5) == 23


# ── forecast:show (sets FSM) ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_show_displays_menu_and_stashes_chart_id(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_state: MagicMock,
) -> None:
    chart = _fake_chart(user_id=fake_user.id)
    monkeypatch.setattr(forecast_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))

    cb = _fake_callback(f"forecast:show:{chart.id}")
    await handle_forecast_show(callback=cb, session=fake_session, user=fake_user, state=fake_state)

    cb.message.answer.assert_awaited_once()
    text, kwargs = cb.message.answer.call_args.args[0], cb.message.answer.call_args.kwargs
    assert "Прогнозы" in text and "Шифу" in text
    assert "500" in text and "900" in text
    kb_data = {btn.callback_data for row in kwargs["reply_markup"].inline_keyboard for btn in row}
    # Sub-callbacks are now short prefixes (no UUID in payload).
    assert "fc:bm" in kb_data
    assert "fc:bd" in kb_data
    assert "fc:list" in kb_data
    # chart_id stashed in FSM for subsequent short-callback handlers.
    data = await fake_state.get_data()
    assert data[_FSM_FORECAST_CHART] == str(chart.id)


@pytest.mark.asyncio
async def test_show_blocks_cross_user_chart(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_state: MagicMock,
) -> None:
    chart = _fake_chart(user_id=_uuid.uuid4())
    monkeypatch.setattr(forecast_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))

    cb = _fake_callback(f"forecast:show:{chart.id}")
    await handle_forecast_show(callback=cb, session=fake_session, user=fake_user, state=fake_state)

    cb.message.answer.assert_not_awaited()
    cb.answer.assert_awaited_once()


# ── Monthly purchase ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_buy_monthly_shows_delivery_picker(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_state: MagicMock,
) -> None:
    chart = _fake_chart(user_id=fake_user.id)
    await _stash_chart_in_state(fake_state, chart.id)
    monkeypatch.setattr(forecast_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))

    cb = _fake_callback("fc:bm")
    await handle_buy_monthly(callback=cb, session=fake_session, user=fake_user, state=fake_state)

    cb.message.answer.assert_awaited_once()
    text = cb.message.answer.call_args.args[0]
    assert "месячный прогноз" in text.lower()


@pytest.mark.asyncio
async def test_monthly_confirm_weekly_stashes_delivery_and_shows_school(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_state: MagicMock,
) -> None:
    """Wave 7 Phase 2 ext (2026-05-26) — fc:mc:weekly теперь это
    промежуточный шаг: сохраняет delivery=weekly в FSM и показывает
    school_selector_kb. Подписка НЕ создаётся пока клиент не нажмёт
    fc:ms:<school>."""
    chart = _fake_chart(user_id=fake_user.id)
    await _stash_chart_in_state(fake_state, chart.id)
    monkeypatch.setattr(forecast_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))
    create_mock = AsyncMock()
    monkeypatch.setattr(forecast_module._sub_repo, "create", create_mock)

    cb = _fake_callback("fc:mc:weekly")
    await handle_monthly_confirm(
        callback=cb, session=fake_session, user=fake_user, state=fake_state
    )

    # На этом шаге подписка НЕ создаётся.
    create_mock.assert_not_awaited()
    fake_session.commit.assert_not_awaited()

    # FSM stash содержит delivery.
    data = await fake_state.get_data()
    assert data["forecast_monthly_delivery"] == "weekly"

    # Бот показал school_selector.
    answer_text = cb.message.answer.call_args.args[0]
    assert "школу" in answer_text.lower() or "школа" in answer_text.lower()


@pytest.mark.asyncio
async def test_monthly_confirm_weekly_kicks_first_delivery_inline(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_state: MagicMock,
) -> None:
    """Wave 7 2026-05-26 — после создания weekly-подписки handler
    запускает asyncio.create_task(_kick_first_delivery) который через
    asyncio.sleep(60) вызывает send_monthly_forecast_job(week=1).

    Этот тест защищает от регрессии бага: при scheduler restart > 1ч
    после создания подписки rebuild_jobs пропускал week=1 через guard
    «fire_at < now - 1h», и клиент никогда не получал первую часть.
    Inline kick перекрывает гонку — задача стартует независимо от
    APScheduler.

    Тест мокает asyncio.sleep чтобы не ждать 60 сек, и проверяет
    что после await на task'е send_monthly_forecast_job был вызван
    с week=1 + правильным subscription_id + period_start.
    """
    import asyncio

    chart = _fake_chart(user_id=fake_user.id)
    await _stash_chart_in_state(fake_state, chart.id)
    monkeypatch.setattr(forecast_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))

    sub_id = _uuid.uuid4()
    sub_started_at = datetime.now()
    created_sub = MagicMock(id=sub_id, started_at=sub_started_at)
    monkeypatch.setattr(
        forecast_module._sub_repo,
        "create",
        AsyncMock(return_value=created_sub),
    )

    # Мокаем send_monthly_forecast_job, чтобы не дёргать реальный
    # KuzuDB/LLM. Сохраняем call_args чтобы проверить kwargs.
    send_job_mock = AsyncMock()
    monkeypatch.setattr("bot.scheduler.jobs.send_monthly_forecast_job", send_job_mock)

    # Мокаем sleep(60) → immediate return, чтобы тест не висел.
    real_sleep = asyncio.sleep

    async def _fast_sleep(seconds: float) -> None:
        # Sleep(0) пропустит event loop tick, но не подождёт реальные 60с.
        await real_sleep(0)

    monkeypatch.setattr(forecast_module.asyncio, "sleep", _fast_sleep)

    # Track create_task так чтобы await'ить созданную задачу в тесте —
    # иначе она исполнится после возврата из handler и тест увидит
    # send_job_mock не вызванным.
    created_tasks: list[asyncio.Task[Any]] = []
    real_create_task = asyncio.create_task

    def _track_create_task(coro: Any, **kw: Any) -> asyncio.Task[Any]:
        task = real_create_task(coro, **kw)
        created_tasks.append(task)
        return task

    monkeypatch.setattr(forecast_module.asyncio, "create_task", _track_create_task)

    # Шаг 2: сохранить delivery в FSM.
    await fake_state.update_data(forecast_monthly_delivery="weekly")

    # Шаг 3: выбрать школу — это создаёт подписку + inline kick.
    cb = _fake_callback("fc:ms:edoha")
    await handle_monthly_school_confirm(
        callback=cb, session=fake_session, user=fake_user, state=fake_state
    )

    # Подписка создана со school=edoha.
    assert forecast_module._sub_repo.create.await_count == 1  # type: ignore[attr-defined]
    create_kwargs = forecast_module._sub_repo.create.call_args.kwargs  # type: ignore[attr-defined]
    assert create_kwargs["chosen_school"] == "edoha"

    # Подождём все созданные task'и (inline-kick coroutine).
    assert len(created_tasks) >= 1, "handler должен был стартовать inline-kick task"
    for task in created_tasks:
        await task

    # Inline kick вызвал send_monthly_forecast_job с week=1.
    send_job_mock.assert_awaited_once()
    kwargs = send_job_mock.call_args.kwargs
    assert kwargs["subscription_id"] == sub_id
    assert kwargs["week"] == 1
    assert kwargs["period_start"] == sub_started_at.date()


@pytest.mark.asyncio
async def test_monthly_confirm_bulk_kicks_first_delivery_inline(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_state: MagicMock,
) -> None:
    """Для bulk-delivery inline kick запускается с week=None (полный
    месячный прогноз одним сообщением)."""
    import asyncio

    chart = _fake_chart(user_id=fake_user.id)
    await _stash_chart_in_state(fake_state, chart.id)
    monkeypatch.setattr(forecast_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))

    sub_id = _uuid.uuid4()
    sub_started_at = datetime.now()
    created_sub = MagicMock(id=sub_id, started_at=sub_started_at)
    monkeypatch.setattr(
        forecast_module._sub_repo,
        "create",
        AsyncMock(return_value=created_sub),
    )

    send_job_mock = AsyncMock()
    monkeypatch.setattr("bot.scheduler.jobs.send_monthly_forecast_job", send_job_mock)

    real_sleep = asyncio.sleep

    async def _fast_sleep(seconds: float) -> None:
        await real_sleep(0)

    monkeypatch.setattr(forecast_module.asyncio, "sleep", _fast_sleep)

    created_tasks: list[asyncio.Task[Any]] = []
    real_create_task = asyncio.create_task

    def _track_create_task(coro: Any, **kw: Any) -> asyncio.Task[Any]:
        task = real_create_task(coro, **kw)
        created_tasks.append(task)
        return task

    monkeypatch.setattr(forecast_module.asyncio, "create_task", _track_create_task)

    await fake_state.update_data(forecast_monthly_delivery="bulk")
    cb = _fake_callback("fc:ms:classic")
    await handle_monthly_school_confirm(
        callback=cb, session=fake_session, user=fake_user, state=fake_state
    )

    for task in created_tasks:
        await task

    send_job_mock.assert_awaited_once()
    assert send_job_mock.call_args.kwargs["week"] is None


@pytest.mark.asyncio
async def test_monthly_confirm_inline_kick_failure_does_not_break_handler(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_state: MagicMock,
) -> None:
    """Inline kick — UX nicety, не контракт. Если send_monthly_forecast_job
    падает (LLM/KuzuDB down) — handler уже вернул успешный ответ клиенту,
    исключение из background task должно быть залогировано но НЕ
    propagate'нуто наружу."""
    import asyncio

    chart = _fake_chart(user_id=fake_user.id)
    await _stash_chart_in_state(fake_state, chart.id)
    monkeypatch.setattr(forecast_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))

    created_sub = MagicMock(id=_uuid.uuid4(), started_at=datetime.now())
    monkeypatch.setattr(
        forecast_module._sub_repo,
        "create",
        AsyncMock(return_value=created_sub),
    )

    boom = AsyncMock(side_effect=RuntimeError("LLM service down"))
    monkeypatch.setattr("bot.scheduler.jobs.send_monthly_forecast_job", boom)

    real_sleep = asyncio.sleep

    async def _fast_sleep(seconds: float) -> None:
        await real_sleep(0)

    monkeypatch.setattr(forecast_module.asyncio, "sleep", _fast_sleep)

    created_tasks: list[asyncio.Task[Any]] = []
    real_create_task = asyncio.create_task

    def _track_create_task(coro: Any, **kw: Any) -> asyncio.Task[Any]:
        task = real_create_task(coro, **kw)
        created_tasks.append(task)
        return task

    monkeypatch.setattr(forecast_module.asyncio, "create_task", _track_create_task)

    await fake_state.update_data(forecast_monthly_delivery="weekly")
    cb = _fake_callback("fc:ms:modern")
    # Handler сам не должен упасть — отсутствие raise = успех.
    await handle_monthly_school_confirm(
        callback=cb, session=fake_session, user=fake_user, state=fake_state
    )

    # Background task словил исключение, но не утёк наружу.
    for task in created_tasks:
        await task  # дожидаемся — внутри try/except logger.exception

    boom.assert_awaited_once()


@pytest.mark.asyncio
async def test_monthly_school_confirm_creates_bulk_subscription(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_state: MagicMock,
) -> None:
    """Шаг 3/3 для bulk delivery — создаёт подписку с chosen_school."""
    chart = _fake_chart(user_id=fake_user.id)
    await _stash_chart_in_state(fake_state, chart.id)
    monkeypatch.setattr(forecast_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))
    create_mock = AsyncMock(return_value=MagicMock(id=_uuid.uuid4(), started_at=datetime.now()))
    monkeypatch.setattr(forecast_module._sub_repo, "create", create_mock)
    # Чтобы избежать реального LLM-вызова inline kick'a, мокаем send_job + sleep.
    monkeypatch.setattr("bot.scheduler.jobs.send_monthly_forecast_job", AsyncMock())

    import asyncio

    async def _fast_sleep(seconds: float) -> None:
        await asyncio.sleep(0)

    monkeypatch.setattr(forecast_module.asyncio, "sleep", _fast_sleep)

    await fake_state.update_data(forecast_monthly_delivery="bulk")
    cb = _fake_callback("fc:ms:classic")
    await handle_monthly_school_confirm(
        callback=cb, session=fake_session, user=fake_user, state=fake_state
    )

    create_mock.assert_awaited_once()
    kwargs = create_mock.call_args.kwargs
    assert kwargs["monthly_delivery"] == MonthlyDelivery.bulk
    assert kwargs["chosen_school"] == "classic"


@pytest.mark.asyncio
async def test_monthly_confirm_rejects_invalid_delivery(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_state: MagicMock,
) -> None:
    chart = _fake_chart(user_id=fake_user.id)
    await _stash_chart_in_state(fake_state, chart.id)
    monkeypatch.setattr(forecast_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))
    create_mock = AsyncMock()
    monkeypatch.setattr(forecast_module._sub_repo, "create", create_mock)

    cb = _fake_callback("fc:mc:hourly")  # garbage
    await handle_monthly_confirm(
        callback=cb, session=fake_session, user=fake_user, state=fake_state
    )

    create_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_buy_monthly_without_fsm_chart_alerts_session_lost(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_state: MagicMock,
) -> None:
    """If FSM has no forecast_chart_id (user opened bot, didn't enter
    forecast menu first), short callbacks must surface a friendly alert
    instead of crashing."""
    create_mock = AsyncMock()
    monkeypatch.setattr(forecast_module._sub_repo, "create", create_mock)

    cb = _fake_callback("fc:bm")
    await handle_buy_monthly(callback=cb, session=fake_session, user=fake_user, state=fake_state)

    cb.message.answer.assert_not_awaited()
    cb.answer.assert_awaited_once()
    assert "сессия" in cb.answer.call_args.args[0].lower()


# ── Daily purchase ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_buy_daily_shows_hour_picker(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_state: MagicMock,
) -> None:
    chart = _fake_chart(user_id=fake_user.id)
    await _stash_chart_in_state(fake_state, chart.id)
    monkeypatch.setattr(forecast_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))

    cb = _fake_callback("fc:bd")
    await handle_buy_daily(callback=cb, session=fake_session, user=fake_user, state=fake_state)

    cb.message.answer.assert_awaited_once()
    text = cb.message.answer.call_args.args[0]
    assert "время" in text.lower()


@pytest.mark.asyncio
async def test_daily_confirm_stashes_hour_and_shows_school(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_state: MagicMock,
) -> None:
    """Wave 7 Phase 2 ext — fc:dc:<hour> теперь промежуточный шаг:
    сохраняет час в FSM и показывает school_selector_kb. Подписка
    создаётся на handle_daily_school_confirm."""
    chart = _fake_chart(user_id=fake_user.id, tz_offset=3.0)
    await _stash_chart_in_state(fake_state, chart.id)
    monkeypatch.setattr(forecast_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))
    create_mock = AsyncMock()
    monkeypatch.setattr(forecast_module._sub_repo, "create", create_mock)

    cb = _fake_callback("fc:dc:4")
    await handle_daily_confirm(callback=cb, session=fake_session, user=fake_user, state=fake_state)

    create_mock.assert_not_awaited()
    data = await fake_state.get_data()
    assert data["forecast_daily_hour_local"] == 4
    answer_text = cb.message.answer.call_args.args[0]
    assert "школу" in answer_text.lower() or "школа" in answer_text.lower()


@pytest.mark.asyncio
async def test_daily_school_confirm_creates_subscription_with_utc_hour_and_school(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_state: MagicMock,
) -> None:
    """Шаг 3/3 — выбрана школа. Подписка создаётся с правильным
    daily_send_hour_utc + chosen_school."""
    chart = _fake_chart(user_id=fake_user.id, tz_offset=3.0)
    await _stash_chart_in_state(fake_state, chart.id)
    monkeypatch.setattr(forecast_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))
    create_mock = AsyncMock(return_value=MagicMock(id=_uuid.uuid4()))
    monkeypatch.setattr(forecast_module._sub_repo, "create", create_mock)

    await fake_state.update_data(forecast_daily_hour_local=4)
    cb = _fake_callback("fc:ds:edoha")
    await handle_daily_school_confirm(
        callback=cb, session=fake_session, user=fake_user, state=fake_state
    )

    create_mock.assert_awaited_once()
    kwargs = create_mock.call_args.kwargs
    assert kwargs["kind"] == ForecastKind.daily
    assert kwargs["daily_send_hour_utc"] == 1  # 4 local - 3 tz = 1 UTC
    assert kwargs["price_rub"] == 900
    assert kwargs["chosen_school"] == "edoha"


@pytest.mark.asyncio
async def test_daily_confirm_rejects_invalid_hour(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_state: MagicMock,
) -> None:
    chart = _fake_chart(user_id=fake_user.id)
    await _stash_chart_in_state(fake_state, chart.id)
    monkeypatch.setattr(forecast_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))
    create_mock = AsyncMock()
    monkeypatch.setattr(forecast_module._sub_repo, "create", create_mock)

    cb = _fake_callback("fc:dc:99")  # bad hour
    await handle_daily_confirm(callback=cb, session=fake_session, user=fake_user, state=fake_state)

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
    monkeypatch: pytest.MonkeyPatch,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_state: MagicMock,
) -> None:
    chart = _fake_chart(user_id=fake_user.id)
    await _stash_chart_in_state(fake_state, chart.id)
    sub = _fake_sub(user_id=fake_user.id, kind=ForecastKind.daily)
    monkeypatch.setattr(forecast_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))
    monkeypatch.setattr(
        forecast_module._sub_repo, "list_active_for_chart", AsyncMock(return_value=[sub])
    )

    cb = _fake_callback("fc:list")
    await handle_forecast_list(callback=cb, session=fake_session, user=fake_user, state=fake_state)

    answer_text = cb.message.answer.call_args.args[0]
    assert "Активные подписки" in answer_text
    assert "Дневной прогноз" in answer_text


@pytest.mark.asyncio
async def test_list_empty_state(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_state: MagicMock,
) -> None:
    chart = _fake_chart(user_id=fake_user.id)
    await _stash_chart_in_state(fake_state, chart.id)
    monkeypatch.setattr(forecast_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))
    monkeypatch.setattr(
        forecast_module._sub_repo, "list_active_for_chart", AsyncMock(return_value=[])
    )

    cb = _fake_callback("fc:list")
    await handle_forecast_list(callback=cb, session=fake_session, user=fake_user, state=fake_state)
    assert "пока нет" in cb.message.answer.call_args.args[0].lower()


@pytest.mark.asyncio
async def test_cancel_confirm_calls_repo_cancel(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_state: MagicMock,
) -> None:
    sub = _fake_sub(user_id=fake_user.id, kind=ForecastKind.daily)
    chart = _fake_chart(user_id=fake_user.id)
    await _stash_chart_in_state(fake_state, chart.id)
    monkeypatch.setattr(forecast_module._sub_repo, "get_by_id", AsyncMock(return_value=sub))
    monkeypatch.setattr(forecast_module._chart_repo, "get_by_id", AsyncMock(return_value=chart))
    cancel_mock = AsyncMock(return_value=True)
    monkeypatch.setattr(forecast_module._sub_repo, "cancel", cancel_mock)

    cb = _fake_callback(f"fc:cc:{sub.id}")
    await handle_cancel_confirm(callback=cb, session=fake_session, user=fake_user, state=fake_state)

    cancel_mock.assert_awaited_once_with(fake_session, sub.id)
    fake_session.commit.assert_awaited_once()
    cb.message.edit_text.assert_awaited_once()


@pytest.mark.asyncio
async def test_cancel_confirm_blocks_cross_user_sub(
    monkeypatch: pytest.MonkeyPatch,
    fake_session: MagicMock,
    fake_user: MagicMock,
    fake_state: MagicMock,
) -> None:
    sub = _fake_sub(user_id=_uuid.uuid4(), kind=ForecastKind.daily)  # someone else's
    monkeypatch.setattr(forecast_module._sub_repo, "get_by_id", AsyncMock(return_value=sub))
    cancel_mock = AsyncMock()
    monkeypatch.setattr(forecast_module._sub_repo, "cancel", cancel_mock)

    cb = _fake_callback(f"fc:cc:{sub.id}")
    await handle_cancel_confirm(callback=cb, session=fake_session, user=fake_user, state=fake_state)

    cancel_mock.assert_not_awaited()
    cb.answer.assert_awaited_once()
