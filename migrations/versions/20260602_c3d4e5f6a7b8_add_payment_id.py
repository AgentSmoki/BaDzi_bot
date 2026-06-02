"""add payment_id to subscriptions and chart_forecast_subscriptions

Wave 7 (2026-06-02) — подключение оплаты ЮKassa через нативные Telegram-
платежи. Храним provider_payment_charge_id из successful_payment для
аудита и сверки. NULL для free/bypass-строк.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-02 10:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c3d4e5f6a7b8"
down_revision: str | Sequence[str] | None = "b2c3d4e5f6a7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column("payment_id", sa.String(length=128), nullable=True),
    )
    op.add_column(
        "chart_forecast_subscriptions",
        sa.Column("payment_id", sa.String(length=128), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chart_forecast_subscriptions", "payment_id")
    op.drop_column("subscriptions", "payment_id")
