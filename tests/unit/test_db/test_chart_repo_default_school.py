"""Tests for ChartRepository.set_default_school (Wave 7 / 1.18.14).

Session is mocked — we verify the UPDATE call shape (charts row pinned,
default_school value set or cleared) rather than running real SQL.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
import sqlalchemy as sa

from db.models import Chart
from db.repositories.chart_repo import ChartRepository


@pytest.mark.asyncio
async def test_set_default_school_issues_update_with_value() -> None:
    session = MagicMock()
    session.execute = AsyncMock()
    repo = ChartRepository()

    chart_id = uuid.uuid4()
    await repo.set_default_school(session, chart_id, "edoha")

    assert session.execute.await_count == 1
    stmt = session.execute.await_args.args[0]
    assert isinstance(stmt, sa.sql.dml.Update)
    assert stmt.table.name == "charts"
    bound = stmt.compile(compile_kwargs={"literal_binds": False}).params
    assert bound["default_school"] == "edoha"


@pytest.mark.asyncio
async def test_set_default_school_can_clear_to_none() -> None:
    session = MagicMock()
    session.execute = AsyncMock()
    repo = ChartRepository()

    chart_id = uuid.uuid4()
    await repo.set_default_school(session, chart_id, None)

    stmt = session.execute.await_args.args[0]
    bound = stmt.compile(compile_kwargs={"literal_binds": False}).params
    assert bound["default_school"] is None


@pytest.mark.asyncio
async def test_set_default_school_targets_correct_row() -> None:
    session = MagicMock()
    session.execute = AsyncMock()
    repo = ChartRepository()

    chart_id = uuid.uuid4()
    await repo.set_default_school(session, chart_id, "classic")

    stmt = session.execute.await_args.args[0]
    where_clauses = list(stmt._where_criteria)
    assert len(where_clauses) == 1
    assert "id" in str(where_clauses[0])


def test_chart_model_default_school_column_declared() -> None:
    assert hasattr(Chart, "default_school")
    assert Chart.__table__.c.default_school.nullable is True
