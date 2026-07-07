"""Regression tests for calculator determinism (task 2.1.6).

Investigation showed that the previously reported "floating" pillars
between bot sessions traced back to the *input* — different values of
``tz_offset`` (DST-aware 4.0 vs naive post-2011 3.0) and ``early_rat``
(False vs True) produce different charts, as they should. The
calculator itself is deterministic for fixed input. These tests pin
that down so the regression cannot return.

If this test ever flakes, the calculator gained a non-deterministic
dependency (likely pyswisseph global state, a floating-point equality,
or a process-wide cache).
"""

from __future__ import annotations

from datetime import datetime

import pytest

from calculator import calculate_chart
from calculator.models import ChartInput

# Reference input: Anastasia, Volzhsky 12.09.1999 23:55 (DST-active in
# Russia, so true UTC offset is +4 — confirmed via pytz). Coordinates
# rounded to 4 decimals to match what the geocoders return.
_REFERENCE_INPUT = ChartInput(
    birth_datetime=datetime(1999, 9, 12, 23, 55),
    latitude=48.7894,
    longitude=44.7783,
    tz_offset=4.0,
    early_rat=False,
    gender="female",
)


def _signature(inp: ChartInput) -> str:
    chart = calculate_chart(inp)
    return "/".join(f"{p.stem}{p.branch}" for p in chart.pillars)


def test_calculate_chart_is_deterministic_within_process() -> None:
    """1000 consecutive calls with the same input must return exactly
    one distinct result. If this drifts, look for pyswisseph global
    state (set_ephe_path, set_topo) or floating-point equality in
    solar_terms / true_solar_time."""
    sigs = {_signature(_REFERENCE_INPUT) for _ in range(1000)}
    assert len(sigs) == 1, f"calculator drifted across calls: {sigs}"


@pytest.mark.parametrize(
    ("tz_offset", "early_rat", "expected_y_m_d_h"),
    [
        (3.0, False, "己卯/癸酉/戊辰/壬子"),
        (3.0, True, "己卯/癸酉/丁卯/庚子"),
        (4.0, False, "己卯/癸酉/丁卯/辛亥"),
    ],
)
def test_pillars_are_pinned_per_input_combination(
    tz_offset: float, early_rat: bool, expected_y_m_d_h: str
) -> None:
    """The three pillar combinations previously seen as 'floating' in
    MASTER.md fully explained by the (tz_offset, early_rat) pair. This
    test pins each one to its expected output so any future calculator
    change has to be made consciously."""
    inp = _REFERENCE_INPUT.model_copy(update={"tz_offset": tz_offset, "early_rat": early_rat})
    assert _signature(inp) == expected_y_m_d_h
