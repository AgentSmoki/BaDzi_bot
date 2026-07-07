from dataclasses import dataclass
from datetime import UTC, datetime, time

import pytz


@dataclass(frozen=True)
class ResolvedBirthDateTime:
    naive_local: datetime  # local civil time, naive — what the calculator expects
    utc_aware: datetime  # UTC-aware — for storage and display
    tz_offset_hours: float  # offset on the actual birth date (DST-correct)


def resolve(
    *,
    birth_date: str,
    birth_time: str | None,
    tz_iana: str,
) -> ResolvedBirthDateTime:
    """Combine ISO date + ISO time + IANA tz into the trio the rest of the
    pipeline needs. When birth_time is None we default to noon (the calculator
    will skip the hour pillar; chart_data still records has_birth_time=False).
    """
    parsed_date = datetime.fromisoformat(birth_date).date()
    if birth_time:
        parsed_time = time.fromisoformat(birth_time)
    else:
        parsed_time = time(12, 0)

    naive_local = datetime.combine(parsed_date, parsed_time)
    tz = pytz.timezone(tz_iana)
    localized = tz.localize(naive_local)
    utc_offset = localized.utcoffset()
    if utc_offset is None:
        raise ValueError(f"Could not derive UTC offset for {tz_iana} on {parsed_date}")

    return ResolvedBirthDateTime(
        naive_local=naive_local,
        utc_aware=localized.astimezone(UTC),
        tz_offset_hours=utc_offset.total_seconds() / 3600.0,
    )
