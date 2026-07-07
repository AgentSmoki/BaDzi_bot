"""free_questions_used as counter (Wave 7 UX)

Заменяет ``free_question_used: bool`` (1 бесплатный вопрос) на
``free_questions_used: int`` (счётчик, лимит из settings.free_questions_limit
= 3 по умолчанию).

Backfill rule:
- old free_question_used = True  → new free_questions_used = 3 (исчерпали)
- old free_question_used = False → new free_questions_used = 0 (новый)

Так существующие юзеры не получают «бонус» к бесплатным вопросам после
миграции — лимит остаётся тем же что и был, просто формализован счётчиком.

Revision ID: 4af483b51b7e
Revises: fd6512684d2f
Create Date: 2026-05-24 10:34:59.819814

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "4af483b51b7e"  # pragma: allowlist secret
down_revision: str | None = "fd6512684d2f"  # pragma: allowlist secret
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Add counter column, backfill from old bool, drop old bool."""
    # 1. Новая колонка (default 0, NOT NULL — для свежих юзеров).
    op.add_column(
        "users",
        sa.Column(
            "free_questions_used",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
    )

    # 2. Backfill — existing rows: True → 3 (исчерпали), False → 0.
    op.execute(
        """
        UPDATE users
        SET free_questions_used = CASE
            WHEN free_question_used = TRUE THEN 3
            ELSE 0
        END
        """
    )

    # 3. Drop старый bool.
    op.drop_column("users", "free_question_used")


def downgrade() -> None:
    """Restore old bool column from counter.

    Backfill rule на откат:
    - free_questions_used > 0 → free_question_used = TRUE
    - free_questions_used = 0 → free_question_used = FALSE

    Теряем точное значение счётчика, но flag-семантика восстанавливается.
    """
    op.add_column(
        "users",
        sa.Column(
            "free_question_used",
            sa.Boolean(),
            server_default=sa.false(),
            nullable=False,
        ),
    )
    op.execute("UPDATE users SET free_question_used = (free_questions_used > 0)")
    op.drop_column("users", "free_questions_used")
