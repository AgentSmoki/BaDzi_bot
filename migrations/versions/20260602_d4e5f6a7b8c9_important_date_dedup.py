"""per-date dedup for important-date alerts

Wave 4e fix (2026-06-02) — раздельный дедуп предупреждения (за 1-2 дня) и
приглашения рефлексии (в день даты), чтобы (а) не слать одну дату дважды
за неделю, (б) слать рефлексию именно в день важной даты.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-02 11:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: str | Sequence[str] | None = "c3d4e5f6a7b8"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "chart_journal_settings",
        sa.Column("last_important_warning_date", sa.Date(), nullable=True),
    )
    op.add_column(
        "chart_journal_settings",
        sa.Column("last_reflection_prompt_date", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chart_journal_settings", "last_reflection_prompt_date")
    op.drop_column("chart_journal_settings", "last_important_warning_date")
