import hashlib

import pytest
from sqlalchemy import delete, func, select, text

from app.database import create_session_factory
from app.models import BankResult, Session, Simulation

pytestmark = pytest.mark.asyncio


async def test_service_returns_only_after_real_commit_and_commits_deletion(
    engine, build_service
):
    token_hash = None
    try:
        async with create_session_factory(engine)() as db, engine.connect() as reader:
            ctx = build_service(db)
            created = await ctx.service.create(ctx.request, ctx.scenarios, None)
            assert not db.in_transaction()
            token_hash = hashlib.sha256(created.new_token.encode()).digest()
            owner_id = await reader.scalar(
                select(Session.id).where(Session.token_hash == token_hash)
            )
            assert owner_id is not None
            assert (
                await reader.scalar(
                    select(Simulation.id).where(Simulation.id == created.response.id)
                )
                == created.response.id
            )
            assert (
                await reader.scalar(
                    select(func.count())
                    .select_from(BankResult)
                    .where(BankResult.simulation_id == created.response.id)
                )
                == 2
            )
            # Both connections remain checked out simultaneously for this check.
            async with db.begin():
                writer_pid = await db.scalar(text("SELECT pg_backend_pid()"))
                assert (
                    await reader.scalar(text("SELECT pg_backend_pid()")) != writer_pid
                )
            await ctx.service.delete(created.response.id, created.new_token)
            assert (
                await reader.scalar(
                    select(Simulation.id).where(Simulation.id == created.response.id)
                )
                is None
            )
            assert (
                await reader.scalar(select(Session.id).where(Session.id == owner_id))
                == owner_id
            )
    finally:
        if token_hash is not None:
            async with engine.begin() as cleanup:
                await cleanup.execute(
                    delete(Session).where(Session.token_hash == token_hash)
                )
