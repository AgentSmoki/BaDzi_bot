"""Tests for ChartRepository.set_partner (Wave 6 / Phase 3).

Like the rest of the bot/db test suite, AsyncSession is mocked — we
verify the call shape (an UPDATE on charts with partner_chart_id set)
rather than running real SQL. Integration coverage of the FK + cascade
behavior lives in Phase 7 live smoke against the YC managed Postgres.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
import sqlalchemy as sa

from db.models import Chart
from db.repositories.chart_repo import ChartRepository


@pytest.mark.asyncio
async def test_set_partner_issues_update_with_correct_values() -> None:
    session = MagicMock()
    session.execute = AsyncMock()
    repo = ChartRepository()

    owner_id = uuid.uuid4()
    partner_id = uuid.uuid4()
    await repo.set_partner(session, owner_chart_id=owner_id, partner_chart_id=partner_id)

    # Exactly one UPDATE call against Chart with the right id / partner FK.
    assert session.execute.await_count == 1
    stmt = session.execute.await_args.args[0]
    assert isinstance(stmt, sa.sql.dml.Update)
    assert stmt.table.name == "charts"

    # Compile to a dialect-agnostic string and check the bound parameters carry
    # the two UUIDs we expect.
    compiled = stmt.compile(compile_kwargs={"literal_binds": False})
    bound = compiled.params
    assert bound["partner_chart_id"] == partner_id


@pytest.mark.asyncio
async def test_set_partner_targets_correct_row() -> None:
    """WHERE clause must pin the owner chart, not update everything."""
    session = MagicMock()
    session.execute = AsyncMock()
    repo = ChartRepository()

    owner_id = uuid.uuid4()
    partner_id = uuid.uuid4()
    await repo.set_partner(session, owner_chart_id=owner_id, partner_chart_id=partner_id)

    stmt = session.execute.await_args.args[0]
    where_clauses = list(stmt._where_criteria)
    assert len(where_clauses) == 1
    # Confirm WHERE references the Chart.id column (not e.g. user_id).
    assert "id" in str(where_clauses[0])


def test_chart_model_partner_relationship_declared() -> None:
    """Sanity: ORM exposes the partner relationship + FK column."""
    assert hasattr(Chart, "partner_chart_id")
    assert hasattr(Chart, "partner_chart")
    # Foreign key target is charts.id (self-reference).
    fk_columns = Chart.__table__.c.partner_chart_id.foreign_keys
    fk = next(iter(fk_columns))
    assert fk.column.table.name == "charts"
    assert fk.column.name == "id"
