"""Возраст клиента и возрастные бэнды (Wave 7 — возрастные метафоры).

Возраст идёт в ``[AUDIENCE]`` секцию промпта, чтобы Анастасия подбирала
метафоры-примеры под мир клиента (см. «Возрастные метафоры» в base.md).
Бэнды согласованы с базами примеров в base_classic/edoha/modern.md.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Final

# (верхняя граница не включительно, лейбл) — последняя ступень открыта.
AGE_BANDS: Final[tuple[tuple[int, str], ...]] = (
    (25, "до 25"),
    (35, "25-35"),
    (45, "35-45"),
    (60, "45-60"),
)
OLDEST_BAND_LABEL: Final = "60+"


def client_age_years(birth: datetime, *, today: date | None = None) -> int:
    """Полных лет по календарю (учитывает, наступил ли день рождения
    в этом году — деление на 365 промахивается на високосных)."""
    ref = today or date.today()
    born = birth.date()
    years = ref.year - born.year
    if (ref.month, ref.day) < (born.month, born.day):
        years -= 1
    return max(0, years)


def age_band_label(age: int) -> str:
    """Лейбл возрастного бэнда для ``[AUDIENCE]`` секции."""
    for upper, label in AGE_BANDS:
        if age < upper:
            return label
    return OLDEST_BAND_LABEL
