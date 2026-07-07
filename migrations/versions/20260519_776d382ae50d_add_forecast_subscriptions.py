"""add_forecast_subscriptions

Wave 3a — paid per-chart forecast subscriptions and delivery log.

``chart_forecast_subscriptions``: one row per active subscription.
Re-buying creates a new row (history-preserving). Filter active via
``status='active' AND expires_at>now()``.

``forecast_deliveries``: one row per scheduled-slot send. Unique
(subscription_id, slot_key) blocks dupes if the scheduler retries.

Revision ID: 776d382ae50d
Revises: 5c7804a9c2c3
Create Date: 2026-05-19 22:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "776d382ae50d"  # pragma: allowlist secret
down_revision: str | None = "5c7804a9c2c3"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "chart_forecast_subscriptions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("chart_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("monthly_delivery", sa.String(16), nullable=True),
        sa.Column("daily_send_hour_utc", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.String(16),
            server_default="active",
            nullable=False,
        ),
        sa.Column("started_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("price_rub", sa.Integer(), nullable=False),
        sa.Column("payment_provider", sa.String(32), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["chart_id"], ["charts.id"], ondelete="CASCADE"),
    )
    op.create_index(
        "ix_chart_forecast_subs_user_id",
        "chart_forecast_subscriptions",
        ["user_id"],
    )
    op.create_index(
        "ix_chart_forecast_subs_chart_id",
        "chart_forecast_subscriptions",
        ["chart_id"],
    )
    op.create_index(
        "ix_chart_forecast_subs_kind",
        "chart_forecast_subscriptions",
        ["kind"],
    )
    op.create_index(
        "ix_chart_forecast_subs_status",
        "chart_forecast_subscriptions",
        ["status"],
    )

    op.create_table(
        "forecast_deliveries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("subscription_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slot_key", sa.String(64), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(
            ["subscription_id"],
            ["chart_forecast_subscriptions.id"],
            ondelete="CASCADE",
        ),
        sa.UniqueConstraint("subscription_id", "slot_key", name="uq_forecast_deliveries_slot"),
    )
    op.create_index(
        "ix_forecast_deliveries_subscription_id",
        "forecast_deliveries",
        ["subscription_id"],
    )
    op.create_index(
        "ix_forecast_deliveries_slot_key",
        "forecast_deliveries",
        ["slot_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_forecast_deliveries_slot_key", table_name="forecast_deliveries")
    op.drop_index("ix_forecast_deliveries_subscription_id", table_name="forecast_deliveries")
    op.drop_table("forecast_deliveries")
    op.drop_index("ix_chart_forecast_subs_status", table_name="chart_forecast_subscriptions")
    op.drop_index("ix_chart_forecast_subs_kind", table_name="chart_forecast_subscriptions")
    op.drop_index(
        "ix_chart_forecast_subs_chart_id",
        table_name="chart_forecast_subscriptions",
    )
    op.drop_index("ix_chart_forecast_subs_user_id", table_name="chart_forecast_subscriptions")
    op.drop_table("chart_forecast_subscriptions")
