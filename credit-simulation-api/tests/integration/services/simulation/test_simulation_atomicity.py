from datetime import timedelta

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.exc import SQLAlchemyError

from app.errors import SimulationDeleteFailed, SimulationSaveFailed
from app.models import BankResult, BankResultReason, Session, Simulation

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize("stage", ["flush", "commit"])
async def test_save_failure_rolls_back_new_session_and_entire_graph(
    persisted_service, stage
):
    ctx = persisted_service
    failure = SQLAlchemyError("forced persistence failure")

    def fail(*args):
        raise failure

    target = "after_flush_postexec" if stage == "flush" else "before_commit"

    # Commit is invoked for the preliminary read too, so fail only the write.
    def fail_write_commit(session):
        if session.identity_map:
            fail()

    listener = fail if stage == "flush" else fail_write_commit
    event.listen(ctx.db.sync_session, target, listener)
    try:
        with pytest.raises(SimulationSaveFailed):
            await ctx.service.create(ctx.request, ctx.scenarios, None)
    finally:
        event.remove(ctx.db.sync_session, target, listener)
    async with ctx.db.begin():
        for model in (Session, Simulation, BankResult, BankResultReason):
            assert await ctx.db.scalar(select(func.count()).select_from(model)) == 0


async def test_expiration_during_bank_wait_creates_replacement(
    persisted_service, service_clock
):
    ctx = persisted_service
    first = await ctx.service.create(ctx.request, ctx.scenarios, None)
    result = ctx.banks[0].evaluate.return_value

    async def advance_clock(*args):
        service_clock.now += timedelta(days=7)
        return result

    ctx.banks[0].evaluate.side_effect = advance_clock
    second = await ctx.service.create(ctx.request, ctx.scenarios, first.new_token)
    assert second.new_token and second.new_token != first.new_token
    assert second.session_expires_at == first.session_expires_at + timedelta(days=7)
    async with ctx.db.begin():
        assert await ctx.db.scalar(select(func.count()).select_from(Session)) == 2


async def test_failed_delete_commit_preserves_simulation(persisted_service):
    ctx = persisted_service
    created = await ctx.service.create(ctx.request, ctx.scenarios, None)

    def fail(session):
        raise SQLAlchemyError("forced delete commit failure")

    event.listen(ctx.db.sync_session, "before_commit", fail)
    try:
        with pytest.raises(SimulationDeleteFailed):
            await ctx.service.delete(created.response.id, created.new_token)
    finally:
        event.remove(ctx.db.sync_session, "before_commit", fail)
    assert (
        await ctx.service.get_detail(created.response.id, created.new_token)
    ).id == created.response.id
