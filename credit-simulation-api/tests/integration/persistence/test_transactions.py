import pytest
from factories import (
    make_graph,
)
from sqlalchemy import delete, func, select, text

from app.database import create_session_factory
from app.models import BankResult, BankResultReason, Session, Simulation

pytestmark = pytest.mark.asyncio


async def test_rollback_removes_all_pending_records(db):
    graph = make_graph()
    db.add(graph.session)
    await db.flush()
    session_id, simulation_id = graph.session.id, graph.simulation.id
    await db.rollback()
    assert await db.get(Session, session_id) is None
    assert await db.get(Simulation, simulation_id) is None
    assert await db.scalar(select(func.count()).select_from(BankResult)) == 0
    assert await db.scalar(select(func.count()).select_from(BankResultReason)) == 0


async def test_session_commit_inside_savepoint_keeps_loaded_values(
    db, saved_simulation
):
    await db.commit()
    assert saved_simulation.requested_amount_cents == 100000


async def test_real_commit_is_visible_to_an_independent_connection(engine):
    graph = make_graph()
    factory = create_session_factory(engine)
    session_id = None
    try:
        async with factory() as writer, engine.connect() as reader:
            writer.add(graph.session)
            await writer.flush()
            session_id = graph.session.id
            query = (
                select(func.count())
                .select_from(Session)
                .where(Session.id == session_id)
            )
            assert await reader.scalar(query) == 0
            writer_pid = await writer.scalar(text("SELECT pg_backend_pid()"))
            assert await reader.scalar(text("SELECT pg_backend_pid()")) != writer_pid
            # No outer transaction/savepoint: this reaches PostgreSQL COMMIT.
            await writer.commit()
            assert await reader.scalar(query) == 1
            simulation = (
                await reader.execute(
                    select(Simulation.__table__).where(
                        Simulation.id == graph.simulation.id
                    )
                )
            ).one()
            assert simulation.requested_amount_cents == 100000
            assert (
                await reader.scalar(
                    select(func.count())
                    .select_from(BankResult)
                    .where(BankResult.simulation_id == graph.simulation.id)
                )
                == 2
            )
            assert (
                await reader.scalar(
                    select(func.count())
                    .select_from(BankResultReason)
                    .where(BankResultReason.bank_result_id == graph.rejected_result.id)
                )
                == 2
            )
    finally:
        if session_id is not None:
            async with engine.begin() as cleanup:
                await cleanup.execute(delete(Session).where(Session.id == session_id))
