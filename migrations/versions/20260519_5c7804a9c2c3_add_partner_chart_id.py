"""add_partner_chart_id

Phase 3 of Wave 6 (ADR-010 «Skill-based AI routing»): when the
relationships skill fires and the user mentions a specific partner,
the consultation handler offers an «Add partner chart» button. The
linked chart belongs to the same user (so it's discoverable via the
regular list_charts UI), but the owner chart points to it through
``partner_chart_id`` so the AI prompt knows which one to render in
the ``[PARTNER_CHART]`` section.

``ondelete=SET NULL`` — if the partner chart is deleted, the link
disappears rather than cascading and killing the owner chart.

Revision ID: 5c7804a9c2c3
Revises: 151398db4f39
Create Date: 2026-05-19 19:30:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "5c7804a9c2c3"  # pragma: allowlist secret
down_revision: str | None = "151398db4f39"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "charts",
        sa.Column(
            "partner_chart_id",
            postgresql.UUID(as_uuid=True),
            nullable=True,
        ),
    )
    op.create_foreign_key(
        "fk_charts_partner_chart_id",
        "charts",
        "charts",
        ["partner_chart_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_charts_partner_chart_id",
        "charts",
        ["partner_chart_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_charts_partner_chart_id", table_name="charts")
    op.drop_constraint("fk_charts_partner_chart_id", "charts", type_="foreignkey")
    op.drop_column("charts", "partner_chart_id")
