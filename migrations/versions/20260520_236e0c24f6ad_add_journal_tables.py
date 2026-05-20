"""add_journal_tables

Wave 4 — per-chart reflection journal:
- ``chart_journal_settings``: enabled flag + reminder schedule (one row per chart)
- ``journal_entries``: one entry per chart per day (UNIQUE constraint)

Revision ID: 236e0c24f6ad
Revises: 776d382ae50d
Create Date: 2026-05-20 08:35:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "236e0c24f6ad"  # pragma: allowlist secret
down_revision: str | None = "776d382ae50d"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chart_journal_settings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chart_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("reminder_hour_local", sa.Integer(), server_default="21", nullable=False),
        sa.Column("reminder_hour_utc", sa.Integer(), server_default="18", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["chart_id"], ["charts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("chart_id"),
    )
    op.create_index(
        "ix_chart_journal_settings_chart_id",
        "chart_journal_settings",
        ["chart_id"],
    )

    op.create_table(
        "journal_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chart_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("energies_summary", sa.Text(), nullable=False),
        sa.Column("user_reflection", sa.Text(), nullable=True),
        sa.Column("source", sa.String(16), server_default="text", nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["chart_id"], ["charts.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("chart_id", "entry_date", name="uq_journal_entries_chart_date"),
    )
    op.create_index(
        "ix_journal_entries_chart_id",
        "journal_entries",
        ["chart_id"],
    )
    op.create_index(
        "ix_journal_entries_entry_date",
        "journal_entries",
        ["entry_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_journal_entries_entry_date", table_name="journal_entries")
    op.drop_index("ix_journal_entries_chart_id", table_name="journal_entries")
    op.drop_table("journal_entries")
    op.drop_index("ix_chart_journal_settings_chart_id", table_name="chart_journal_settings")
    op.drop_table("chart_journal_settings")
