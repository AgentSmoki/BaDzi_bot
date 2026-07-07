"""Pin DST-correct UTC offsets coming out of ``birth_datetime.resolve``.

Russia ran DST until 2011, so a 1999-09-12 birthdate in Volgograd has
``utcoffset == +4`` (UTC+3 standard + 1h DST). After 2011 the same
zone is permanently UTC+3. The calculator gets a *different* hour
pillar for the two cases, so the resolver must pin the historically
correct offset, not today's.

This test exists because earlier diagnostic scripts hard-coded
``tz_offset=3.0`` for 1999 input, producing a different chart than the
bot pipeline did — the source of the "floating pillars" report in
MASTER.md (task 2.1.6).
"""

from __future__ import annotations

from bot.services.birth_datetime import resolve


def test_volgograd_1999_is_utc_plus_4_dst_aware() -> None:
    r = resolve(birth_date="1999-09-12", birth_time="23:55", tz_iana="Europe/Volgograd")
    assert r.tz_offset_hours == 4.0


def test_moscow_1999_is_utc_plus_4_dst_aware() -> None:
    r = resolve(birth_date="1999-09-12", birth_time="23:55", tz_iana="Europe/Moscow")
    assert r.tz_offset_hours == 4.0


def test_volgograd_post_2011_is_utc_plus_3() -> None:
    """DST was abolished in Russia in 2011 — same calendar date in 2026
    must come out as UTC+3, not UTC+4."""
    r = resolve(birth_date="2026-09-12", birth_time="23:55", tz_iana="Europe/Volgograd")
    assert r.tz_offset_hours == 3.0


def test_no_birth_time_defaults_to_noon() -> None:
    r = resolve(birth_date="1999-09-12", birth_time=None, tz_iana="Europe/Volgograd")
    assert r.naive_local.hour == 12
    assert r.naive_local.minute == 0
