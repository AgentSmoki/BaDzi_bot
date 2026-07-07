"""create_initial_tables

Revision ID: 151398db4f39
Revises:
Create Date: 2026-05-04 14:15:25.811807

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "151398db4f39"  # pragma: allowlist secret
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False),
        sa.Column("username", sa.String(64), nullable=True),
        sa.Column("first_name", sa.String(128), nullable=False),
        sa.Column("locale", sa.String(8), server_default="ru", nullable=False),
        sa.Column("free_question_used", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("telegram_id"),
    )
    op.create_index("ix_users_telegram_id", "users", ["telegram_id"])

    op.create_table(
        "charts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(128), nullable=True),
        sa.Column("birth_datetime_utc", sa.DateTime(), nullable=False),
        sa.Column("birth_datetime_original", sa.DateTime(), nullable=False),
        sa.Column("latitude", sa.Double(), nullable=False),
        sa.Column("longitude", sa.Double(), nullable=False),
        sa.Column("tz_offset", sa.Double(), nullable=False),
        sa.Column("early_rat", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "hidden_stems_school",
            sa.String(32),
            server_default="traditional",
            nullable=False,
        ),
        sa.Column("chart_data", postgresql.JSONB(), nullable=False),
        sa.Column("has_birth_time", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_charts_user_id", "charts", ["user_id"])

    op.create_table(
        "subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("plan", sa.String(16), server_default="free", nullable=False),
        sa.Column("status", sa.String(16), server_default="active", nullable=False),
        sa.Column("questions_remaining", sa.Integer(), nullable=True),
        sa.Column("session_expires_at", sa.DateTime(), nullable=True),
        sa.Column("monthly_expires_at", sa.DateTime(), nullable=True),
        sa.Column("payment_provider", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
    )

    op.create_table(
        "consultations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chart_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("topic", sa.String(128), nullable=True),
        sa.Column("user_message", sa.Text(), nullable=False),
        sa.Column("ai_response", sa.Text(), nullable=False),
        sa.Column("model_used", sa.String(128), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False),
        sa.Column("completion_tokens", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("trace_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["chart_id"], ["charts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_consultations_user_id", "consultations", ["user_id"])
    op.create_index("ix_consultations_chart_id", "consultations", ["chart_id"])
    op.create_index("ix_consultations_trace_id", "consultations", ["trace_id"])

    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chart_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["chart_id"], ["charts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_events_chart_id", "events", ["chart_id"])


def downgrade() -> None:
    op.drop_table("events")
    op.drop_table("consultations")
    op.drop_table("subscriptions")
    op.drop_table("charts")
    op.drop_table("users")
