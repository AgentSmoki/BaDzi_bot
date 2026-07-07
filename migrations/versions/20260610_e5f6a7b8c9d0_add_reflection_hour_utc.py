"""reflection_hour_utc — вечерняя рефлексия в 18:00 местного времени карты

Wave 4e v2 (2026-06-10) — day-of приглашение записать рефлексию переезжает
из глобального скана 09:00 UTC (12:00 MSK) в почасовой скан, который шлёт
его в 18:00 локального времени карты. Backfill переводит 18:00 local в UTC
через charts.tz_offset.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-06-10 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"  # pragma: allowlist secret
down_revision: str | Sequence[str] | None = "d4e5f6a7b8c9"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "chart_journal_settings",
        sa.Column("reflection_hour_utc", sa.Integer(), nullable=False, server_default="15"),
    )
    # 18:00 local → UTC hour. Двойной модуль защищает от отрицательных
    # значений при tz_offset > 18 (теоретический UTC+19..) и < 0.
    op.execute(
        """
        UPDATE chart_journal_settings
        SET reflection_hour_utc = ((18 - round(c.tz_offset))::int % 24 + 24) % 24
        FROM charts c
        WHERE chart_journal_settings.chart_id = c.id
        """
    )


def downgrade() -> None:
    op.drop_column("chart_journal_settings", "reflection_hour_utc")
