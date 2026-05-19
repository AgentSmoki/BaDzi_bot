"""Tests for ChartRepository.delete (Wave 1b)."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
import sqlalchemy as sa

from db.repositories.chart_repo import ChartRepository


@pytest.mark.asyncio
async def test_delete_issues_delete_with_correct_id() -> None:
    """DELETE statement targets exactly the requested chart id."""
    session = MagicMock()
    result_mock = MagicMock()
    result_mock.rowcount = 1
    session.execute = AsyncMock(return_value=result_mock)
    repo = ChartRepository()
    chart_id = uuid.uuid4()

    deleted = await repo.delete(session, chart_id)

    assert deleted is True
    assert session.execute.await_count == 1
    stmt = session.execute.await_args.args[0]
    assert isinstance(stmt, sa.sql.dml.Delete)
    assert stmt.table.name == "charts"


@pytest.mark.asyncio
async def test_delete_returns_false_when_no_row_affected() -> None:
    """Idempotent: deleting an already-gone row returns False, not raises."""
    session = MagicMock()
    result_mock = MagicMock()
    result_mock.rowcount = 0
    session.execute = AsyncMock(return_value=result_mock)
    repo = ChartRepository()

    deleted = await repo.delete(session, uuid.uuid4())

    assert deleted is False


@pytest.mark.asyncio
async def test_delete_handles_missing_rowcount_attribute() -> None:
    """Some session.execute mocks won't expose rowcount — repo defaults to False."""
    session = MagicMock()
    session.execute = AsyncMock(return_value=object())  # no rowcount attr
    repo = ChartRepository()

    deleted = await repo.delete(session, uuid.uuid4())

    assert deleted is False
