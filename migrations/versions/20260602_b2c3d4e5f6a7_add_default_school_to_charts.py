"""add default_school to charts

Wave 7 / ADR-011 (1.18.14, 2026-06-02) — «запомнить выбор школы».
Per-chart дефолтная школа интерпретации (classic / edoha / modern).
NULL = спрашивать школу каждую консультацию (текущее поведение); если
установлена — consultation/forecast пропускают селектор и берут дефолт.

nullable=True без server_default — существующие карты остаются NULL
(продолжают спрашивать), что и есть прежнее поведение.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-02 09:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | Sequence[str] | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "charts",
        sa.Column("default_school", sa.String(length=16), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("charts", "default_school")
