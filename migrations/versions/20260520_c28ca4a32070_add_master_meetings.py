"""add_master_meetings

Wave 5 — recordings of sessions with a real master, transcribed and
summarised so Anastasia (the AI) can cite them when answering.

Revision ID: c28ca4a32070
Revises: 236e0c24f6ad
Create Date: 2026-05-20 08:50:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "c28ca4a32070"  # pragma: allowlist secret
down_revision: str | None = "236e0c24f6ad"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "master_meetings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chart_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(16), server_default="other", nullable=False),
        sa.Column("title", sa.String(256), nullable=True),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(16), server_default="queued", nullable=False),
        sa.Column("duration_seconds", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("transcribed_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chart_id"], ["charts.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_master_meetings_user_id", "master_meetings", ["user_id"])
    op.create_index("ix_master_meetings_chart_id", "master_meetings", ["chart_id"])
    op.create_index("ix_master_meetings_status", "master_meetings", ["status"])


def downgrade() -> None:
    op.drop_index("ix_master_meetings_status", table_name="master_meetings")
    op.drop_index("ix_master_meetings_chart_id", table_name="master_meetings")
    op.drop_index("ix_master_meetings_user_id", table_name="master_meetings")
    op.drop_table("master_meetings")
