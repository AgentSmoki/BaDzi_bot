"""add_important_dates_flags

Wave 4e — per-chart toggle + rate-limit timestamp for important-date alerts:
- ``important_dates_enabled`` (default True) — can be turned off in /start
- ``last_important_date_at`` (nullable) — scheduler skips when <7 days ago

Revision ID: fd6512684d2f
Revises: c28ca4a32070
Create Date: 2026-05-20 12:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "fd6512684d2f"  # pragma: allowlist secret
down_revision: str | None = "c28ca4a32070"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "chart_journal_settings",
        sa.Column(
            "important_dates_enabled",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
    )
    op.add_column(
        "chart_journal_settings",
        sa.Column("last_important_date_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chart_journal_settings", "last_important_date_at")
    op.drop_column("chart_journal_settings", "important_dates_enabled")
