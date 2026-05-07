"""Tests for ai.temporal_context.

Uses real ChartOutput from calculate_chart — calculator is
deterministic and fast (no need to fixture)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from ai.orchestrator import ChatMessage
from ai.temporal_context import (
    compose_messages,
    get_current_bazi,
    render_chart_block,
    render_temporal_block,
)
from calculator import calculate_chart
from calculator.models import ChartInput


@pytest.fixture
def reference_chart():
    """Anastasia's reference chart (same as test_determinism.py)."""
    return calculate_chart(
        ChartInput(
            birth_datetime=datetime(1999, 9, 12, 23, 55),
            latitude=48.7894,
            longitude=44.7783,
            tz_offset=4.0,
            early_rat=False,
            gender="female",
        )
    )


def test_render_chart_block_includes_all_required_sections(reference_chart) -> None:  # type: ignore[no-untyped-def]
    md = render_chart_block(reference_chart)
    # Schema cues every block must have so the LLM sees a stable layout
    assert "**Бацзы карта**" in md
    assert "Дневной Хозяин" in md
    assert "**Четыре столпа" in md
    assert "**Скрытые стволы:**" in md
    assert "**10 Богов:**" in md
    assert "**Баланс пяти стихий:**" in md
    # Reference chart has hour pillar so luck pillars block must appear
    assert "**Ближайшие столпы удачи:**" in md


def test_render_chart_block_quotes_pillars_in_y_m_d_h_order(reference_chart) -> None:  # type: ignore[no-untyped-def]
    md = render_chart_block(reference_chart)
    pillars_line = next(line for line in md.splitlines() if "Четыре столпа" in line)
    # Reference chart pillars: 己卯 · 癸酉 · 丁卯 · 辛亥 (DST tz=4)
    for token in ("己卯", "癸酉", "丁卯", "辛亥"):
        assert token in pillars_line


def test_render_temporal_block_has_now_label_and_pillars() -> None:
    chart = get_current_bazi()
    when = datetime(2026, 5, 7, 18, 0, tzinfo=UTC)
    md = render_temporal_block(chart, when=when)
    assert "Текущий момент" in md
    assert "2026-05-07 18:00 UTC" in md
    assert "Дневной Хозяин дня" in md
    assert "Столпы (Y·M·D·H)" in md


def test_get_current_bazi_returns_a_valid_chart_for_now() -> None:
    """Smoke test only — actual values change every hour. Just check
    the calculator path through `get_current_bazi` doesn't crash and
    yields the four pillars."""
    chart = get_current_bazi()
    assert len(chart.pillars) == 4
    # Day master must be one of the 10 Heavenly Stems
    assert chart.day_master in tuple("甲乙丙丁戊己庚辛壬癸")


def test_get_current_bazi_is_deterministic_for_fixed_when() -> None:
    """Pinning the moment should yield the same chart every call —
    same as the calculator determinism guarantee for natal charts."""
    when = datetime(2026, 5, 7, 12, 0, tzinfo=UTC)
    a = get_current_bazi(when=when)
    b = get_current_bazi(when=when)
    assert [(p.stem, p.branch) for p in a.pillars] == [(p.stem, p.branch) for p in b.pillars]


def test_compose_messages_minimal_layout(reference_chart) -> None:  # type: ignore[no-untyped-def]
    msgs = compose_messages(
        system_prompt="Ты Анастасия.",
        chart=reference_chart,
        question="Расскажи кратко.",
    )
    # 1 system + 1 user, no history, no temporal
    assert len(msgs) == 2
    assert msgs[0].role == "system"
    assert msgs[0].content == "Ты Анастасия."
    assert msgs[1].role == "user"
    assert "Бацзы карта" in msgs[1].content
    assert "Расскажи кратко." in msgs[1].content
    assert "Текущий момент" not in msgs[1].content


def test_compose_messages_with_history_preserves_order(reference_chart) -> None:  # type: ignore[no-untyped-def]
    history = [
        ChatMessage(role="user", content="первый вопрос"),
        ChatMessage(role="assistant", content="первый ответ"),
        ChatMessage(role="user", content="второй вопрос"),
        ChatMessage(role="assistant", content="второй ответ"),
    ]
    msgs = compose_messages(
        system_prompt="Ты Анастасия.",
        chart=reference_chart,
        question="третий вопрос",
        history=history,
    )
    # 1 system + 4 history + 1 fresh user = 6 total
    assert len(msgs) == 6
    assert [m.role for m in msgs] == [
        "system",
        "user",
        "assistant",
        "user",
        "assistant",
        "user",
    ]
    assert msgs[1].content == "первый вопрос"
    assert msgs[-1].content.endswith("Вопрос: третий вопрос")


def test_compose_messages_with_temporal_appends_now_block(reference_chart) -> None:  # type: ignore[no-untyped-def]
    msgs = compose_messages(
        system_prompt="Ты Анастасия.",
        chart=reference_chart,
        question="Что меня ждёт сейчас?",
        include_temporal=True,
    )
    user_body = msgs[-1].content
    assert "Бацзы карта" in user_body
    assert "Текущий момент" in user_body
    assert "Что меня ждёт сейчас?" in user_body


def test_compose_messages_temporal_uses_provided_now_chart(reference_chart) -> None:  # type: ignore[no-untyped-def]
    """If the caller already computed the current Bazi, don't recompute."""
    pinned = calculate_chart(
        ChartInput(
            birth_datetime=datetime(2024, 1, 15, 12, 0),
            latitude=55.7558,
            longitude=37.6173,
            tz_offset=3.0,
            early_rat=False,
        )
    )
    msgs = compose_messages(
        system_prompt="Ты Анастасия.",
        chart=reference_chart,
        question="Сравни мою карту с сегодняшним днём.",
        include_temporal=True,
        now_chart=pinned,
    )
    # Pinned chart's day master must show up in the temporal block
    assert pinned.day_master in msgs[-1].content
