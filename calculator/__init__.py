from datetime import UTC, timedelta

from calculator.auxiliary import calculate_auxiliary_pillars
from calculator.day_master import element_balance
from calculator.hidden_stems import chart_hidden_stems
from calculator.interactions import calculate_interactions
from calculator.luck_pillars import calculate_luck_pillars
from calculator.models import ChartInput, ChartOutput
from calculator.pillars import calculate_pillars
from calculator.structures import calculate_structures
from calculator.symbolic_stars import calculate_symbolic_stars
from calculator.ten_gods import chart_ten_gods
from calculator.true_solar_time import true_solar_time


def calculate_chart(inp: ChartInput) -> ChartOutput:
    """High-level facade: orchestrates every sub-module into a ChartOutput.

    Calculator submodules are stateless and side-effect-free — this is pure
    composition. Extension blocks (luck pillars, interactions, symbolic stars,
    auxiliary, structures) are computed unconditionally; ChartInput.gender
    drives whether luck_pillars returns a value.
    """
    pillars = calculate_pillars(inp)
    hidden = chart_hidden_stems(pillars, school=inp.hidden_stems_school)
    ten_gods = chart_ten_gods(pillars, hidden)
    balance = element_balance(pillars, hidden)

    utc_aware = (inp.birth_datetime - timedelta(hours=inp.tz_offset)).replace(tzinfo=UTC)
    tst = true_solar_time(utc_aware, longitude=inp.longitude)

    return ChartOutput(
        input=inp,
        true_solar_time=tst,
        pillars=pillars,
        day_master=pillars[2].stem,
        hidden_stems=hidden,
        ten_gods=ten_gods,
        element_balance=balance,
        luck_pillars=calculate_luck_pillars(inp),
        interactions=calculate_interactions(pillars),
        symbolic_stars=calculate_symbolic_stars(pillars),
        auxiliary=calculate_auxiliary_pillars(pillars),
        structures=calculate_structures(pillars),
    )


__all__ = ["calculate_chart"]
