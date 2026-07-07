"""add chosen_school to chart_forecast_subscriptions

Wave 7 Phase 2 ext (2026-05-26) — выбор школы (classic / edoha / modern)
при оформлении подписки на дневной/месячный прогноз. Раньше прогнозы
шли через base.md + skill_time без школьной надстройки, теперь
forecast.py подгружает base_<school>.md как и консультации.

server_default='classic' — back-compat для уже существующих подписок
(они получают классическую интерпретацию пока клиент не пересоздаст).

Revision ID: a1b2c3d4e5f6
Revises: 4af483b51b7e
Create Date: 2026-05-26 06:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "4af483b51b7e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "chart_forecast_subscriptions",
        sa.Column(
            "chosen_school",
            sa.String(length=16),
            nullable=False,
            server_default="classic",
        ),
    )


def downgrade() -> None:
    op.drop_column("chart_forecast_subscriptions", "chosen_school")
