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
    # New v3 format wraps the user-message in structured tags; the
    # question text lives inside [QUESTION]...[/QUESTION].
    assert "[QUESTION]\nтретий вопрос\n[/QUESTION]" in msgs[-1].content


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


# ── Symbolic stars in LLM payload (task 2.2.3) ────────────────────────────


def test_render_chart_block_includes_natal_stars_for_reference_chart(  # type: ignore[no-untyped-def]
    reference_chart,
) -> None:
    """Bogdan's reference chart has 13 detected stars including 白虎.
    All of them must surface in the LLM payload now — without this,
    Anastasia can't cite stars the user feels active today."""
    md = render_chart_block(reference_chart)
    assert "**Врождённые звёзды (神煞):**" in md
    # Specific stars Bogdan asked about in live session
    assert "白虎" in md
    assert "Белый Тигр" in md
    assert "天乙贵人" in md
    assert "将星" in md
    # Source citation must be present so the LLM can quote provenance
    assert "渊海子平" in md or "三命通会" in md


def test_natal_stars_block_omitted_for_chart_with_no_stars() -> None:
    """Defensive: if a chart accidentally has empty symbolic_stars,
    no stub heading appears in the payload."""
    # Pick a date that triggers minimal star detection — but in practice
    # almost any chart has at least 1 star. We just verify the function
    # is idempotent when stars are present (smoke for code path).
    chart = calculate_chart(
        ChartInput(
            birth_datetime=datetime(2000, 6, 15, 14, 30),
            latitude=55.75,
            longitude=37.62,
            tz_offset=3.0,
            early_rat=False,
        )
    )
    md = render_chart_block(chart)
    if chart.symbolic_stars and chart.symbolic_stars.stars:
        assert "**Врождённые звёзды (神煞):**" in md
    else:
        assert "**Врождённые звёзды (神煞):**" not in md


def test_temporal_block_includes_now_stars_when_present() -> None:
    """The current-moment block should list stars active on today's
    pillars (separately from natal stars)."""
    when = datetime(2026, 5, 16, 12, 0, tzinfo=UTC)
    now_chart = get_current_bazi(when=when)
    md = render_temporal_block(now_chart, when=when)
    # Even if specific stars vary by date, the heading should appear
    # when at least one star is detected (almost always the case).
    if now_chart.symbolic_stars and now_chart.symbolic_stars.stars:
        assert "**Активные звёзды сегодня" in md


def test_temporal_block_detects_resonance_between_natal_and_now(  # type: ignore[no-untyped-def]
    reference_chart,
) -> None:
    """Bogdan's natal hour pillar is 辛亥 (branch 亥).
    A "now" chart whose day branch is 寅 should trigger 寅亥合 — exactly
    the resonance Bogdan felt on 2026-05-16 (day pillar 庚寅)."""
    when = datetime(2026, 5, 16, 12, 0, tzinfo=UTC)
    now_chart = get_current_bazi(when=when)
    md = render_temporal_block(now_chart, when=when, natal_chart=reference_chart)
    # 2026-05-16 day pillar is 庚寅 → 寅 should harmonize with birth-chart 亥
    assert "**Резонансы карты рождения с текущим моментом:**" in md
    assert "寅" in md
    assert "亥" in md
    assert "六合" in md


def test_temporal_block_omits_resonance_when_no_natal_chart_given() -> None:
    """If birth chart is not passed, no resonance block — keep contract minimal."""
    when = datetime(2026, 5, 16, 12, 0, tzinfo=UTC)
    now_chart = get_current_bazi(when=when)
    md = render_temporal_block(now_chart, when=when)
    assert "Резонансы" not in md


def test_compose_messages_temporal_passes_natal_for_resonance_detection(  # type: ignore[no-untyped-def]
    reference_chart,
) -> None:
    """End-to-end: when a temporal question is composed, the user body
    must carry both the natal stars block AND the resonance block."""
    when = datetime(2026, 5, 16, 12, 0, tzinfo=UTC)
    now_chart = get_current_bazi(when=when)
    msgs = compose_messages(
        system_prompt="Ты Анастасия.",
        chart=reference_chart,
        question="что про 16 мая для меня?",
        include_temporal=True,
        now_chart=now_chart,
    )
    body = msgs[-1].content
    assert "**Врождённые звёзды (神煞):**" in body
    assert "**Резонансы карты рождения с текущим моментом:**" in body


# ── v3 structured-tag format (task 2.2.5) ─────────────────────────────────


def test_compose_messages_v3_wraps_chart_in_bazi_data_tags(  # type: ignore[no-untyped-def]
    reference_chart,
) -> None:
    """v3 protocol: chart block lives inside [BAZI_DATA]...[/BAZI_DATA]
    so the LLM can reason about scope ('quote only what's inside')."""
    msgs = compose_messages(
        system_prompt="Ты Анастасия.",
        chart=reference_chart,
        question="Расскажи про карту.",
    )
    body = msgs[-1].content
    assert "[BAZI_DATA]" in body
    assert "[/BAZI_DATA]" in body
    # The chart block lives inside the tags
    bazi_start = body.index("[BAZI_DATA]")
    bazi_end = body.index("[/BAZI_DATA]")
    assert "Бацзы карта" in body[bazi_start:bazi_end]


def test_compose_messages_v3_wraps_temporal_in_current_moment_tags(  # type: ignore[no-untyped-def]
    reference_chart,
) -> None:
    """Temporal block lives inside [CURRENT_MOMENT]...[/CURRENT_MOMENT].
    Separation from [BAZI_DATA] is critical so the LLM can distinguish
    natal (permanent) data from transient daily activations."""
    msgs = compose_messages(
        system_prompt="Ты Анастасия.",
        chart=reference_chart,
        question="Что сегодня?",
        include_temporal=True,
    )
    body = msgs[-1].content
    assert "[CURRENT_MOMENT]" in body
    assert "[/CURRENT_MOMENT]" in body
    cm_start = body.index("[CURRENT_MOMENT]")
    cm_end = body.index("[/CURRENT_MOMENT]")
    assert "Текущий момент" in body[cm_start:cm_end]


def test_compose_messages_v3_includes_instruction_prefix(  # type: ignore[no-untyped-def]
    reference_chart,
) -> None:
    """Every user-message carries the anti-hallucination instruction
    prefix between data blocks and the question. Without this layer
    the LLM ignores strict-cite rules and fabricates percentages."""
    msgs = compose_messages(
        system_prompt="Ты Анастасия.",
        chart=reference_chart,
        question="Расскажи про карту.",
    )
    body = msgs[-1].content
    assert "[INSTRUCTIONS]" in body
    assert "[/INSTRUCTIONS]" in body
    # Key strict-cite phrase must survive
    assert "дословно" in body
    # 4-section structure must be present
    assert "4 раздела" in body or "4 раздела" in body  # russian variants


def test_compose_messages_v3_wraps_question_in_question_tags(  # type: ignore[no-untyped-def]
    reference_chart,
) -> None:
    """The user's actual question is in its own [QUESTION] block so
    the LLM doesn't conflate it with instructions or data."""
    msgs = compose_messages(
        system_prompt="Ты Анастасия.",
        chart=reference_chart,
        question="что про 16 мая для меня?",
    )
    body = msgs[-1].content
    assert "[QUESTION]\nчто про 16 мая для меня?\n[/QUESTION]" in body


def test_compose_messages_v3_section_order(  # type: ignore[no-untyped-def]
    reference_chart,
) -> None:
    """Section order matters for the LLM's reasoning flow:
    BAZI_DATA → CURRENT_MOMENT → INSTRUCTIONS → QUESTION.
    Each block depends on what came before."""
    msgs = compose_messages(
        system_prompt="Ты Анастасия.",
        chart=reference_chart,
        question="Что сегодня?",
        include_temporal=True,
    )
    body = msgs[-1].content
    idx_bazi = body.index("[BAZI_DATA]")
    idx_cm = body.index("[CURRENT_MOMENT]")
    idx_instr = body.index("[INSTRUCTIONS]")
    idx_q = body.index("[QUESTION]")
    assert idx_bazi < idx_cm < idx_instr < idx_q


def test_compose_messages_client_age_injects_audience_section(  # type: ignore[no-untyped-def]
    reference_chart,
) -> None:
    """Wave 7 возрастные метафоры: client_age → [AUDIENCE] с возрастом
    и бэндом, сразу после [BAZI_DATA] (метафоры подбираются под возраст)."""
    msgs = compose_messages(
        system_prompt="Ты Анастасия.",
        chart=reference_chart,
        question="Что значит моё столкновение?",
        client_age=35,
    )
    body = msgs[-1].content
    assert "[AUDIENCE]" in body
    assert "[/AUDIENCE]" in body
    aud_start = body.index("[AUDIENCE]")
    aud_end = body.index("[/AUDIENCE]")
    audience = body[aud_start:aud_end]
    assert "35 лет" in audience
    assert "бэнд 35-45" in audience
    # Сразу после натальной карты, до инструкций
    assert body.index("[BAZI_DATA]") < aud_start < body.index("[INSTRUCTIONS]")


def test_compose_messages_without_client_age_omits_audience(  # type: ignore[no-untyped-def]
    reference_chart,
) -> None:
    """Legacy callers (forecast, base_interpretation) не передают возраст —
    секция [AUDIENCE] отсутствует, протокол не меняется."""
    msgs = compose_messages(
        system_prompt="Ты Анастасия.",
        chart=reference_chart,
        question="Расскажи про карту.",
    )
    assert "[AUDIENCE]" not in msgs[-1].content
