from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from factories import make_session
from sqlalchemy import event
from sqlalchemy.exc import SQLAlchemyError

from app.errors import HistoryUnavailable, SimulationDeleteFailed, SimulationSaveFailed
from app.schemas.request_schema import SimulationPagination

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize("stage", ["lookup", "prepare", "flush", "commit"])
async def test_save_failures_do_not_return_success_or_token(simulation_context, stage):
    ctx = simulation_context
    failure = SQLAlchemyError("private-database-details")
    if stage == "lookup":
        ctx.sessions.find_active.side_effect = failure
    elif stage == "prepare":
        ctx.sessions.prepare_for_simulation.side_effect = failure
    elif stage == "flush":
        ctx.db.flush = AsyncMock(side_effect=failure)
    else:
        commits = 0

        def fail_save_commit(session):
            nonlocal commits
            commits += 1
            if commits == 2:
                raise failure

        event.listen(ctx.db.sync_session, "before_commit", fail_save_commit)
    with pytest.raises(SimulationSaveFailed) as error:
        await ctx.service.create(ctx.request, ctx.scenarios, "a" * 43)
    assert error.value.__cause__ is failure
    assert "private-" not in str(error.value)
    assert not ctx.db.in_transaction()
    if stage == "lookup":
        for bank in ctx.banks:
            bank.evaluate.assert_not_awaited()


@pytest.mark.parametrize(
    "operation,exception",
    [
        ("list", HistoryUnavailable),
        ("detail", HistoryUnavailable),
        ("delete", SimulationDeleteFailed),
    ],
)
async def test_history_lookup_failure_is_not_an_empty_history(
    simulation_context, operation, exception
):
    ctx = simulation_context
    ctx.sessions.find_active.side_effect = SQLAlchemyError("private-error")
    with pytest.raises(exception):
        if operation == "list":
            await ctx.service.list_history("a" * 43, SimulationPagination())
        elif operation == "detail":
            await ctx.service.get_detail(uuid4(), "a" * 43)
        else:
            await ctx.service.delete(uuid4(), "a" * 43)
    for bank in ctx.banks:
        bank.evaluate.assert_not_awaited()


@pytest.mark.parametrize(
    "operation,exception",
    [
        ("list", HistoryUnavailable),
        ("detail", HistoryUnavailable),
        ("delete", SimulationDeleteFailed),
    ],
)
async def test_repository_failure_after_session_lookup_is_translated(
    simulation_context, operation, exception
):
    ctx = simulation_context
    session = make_session(id=uuid4())
    ctx.sessions.find_active.return_value = session
    ctx.sessions.revalidate_for_write.return_value = session
    failure = SQLAlchemyError("private-query-details")
    if operation == "list":
        ctx.repo.list_for_session.side_effect = failure
        call = ctx.service.list_history("a" * 43, SimulationPagination())
    elif operation == "detail":
        ctx.repo.find_for_session.side_effect = failure
        call = ctx.service.get_detail(uuid4(), "a" * 43)
    else:
        ctx.repo.delete_for_session.side_effect = failure
        call = ctx.service.delete(uuid4(), "a" * 43)
    with pytest.raises(exception) as error:
        await call
    assert error.value.__cause__ is failure
    assert not ctx.db.in_transaction()
