import pytest
from factories import make_graph, make_session
from sqlalchemy import delete, select, text
from sqlalchemy.exc import DBAPIError

from app.database import create_session_factory
from app.models import Session, Simulation
from app.repositories.session_repository import SessionRepository
from app.repositories.simulation_repository import SimulationRepository

pytestmark = pytest.mark.asyncio


async def test_repository_does_not_commit_insert_or_delete(engine):
    graph = make_graph()
    factory = create_session_factory(engine)
    owner_id = None
    try:
        async with factory() as writer, engine.connect() as reader:
            SessionRepository(writer).add(graph.session)
            SimulationRepository(writer).add(graph.simulation)
            await writer.flush()
            owner_id, simulation_id = graph.session.id, graph.simulation.id
            query = select(Simulation.id).where(Simulation.id == simulation_id)
            assert await reader.scalar(query) is None
            await writer.commit()
            assert await reader.scalar(query) == simulation_id
            assert await SimulationRepository(writer).delete_for_session(
                simulation_id, owner_id, now=graph.session.created_at
            )
            assert await reader.scalar(query) == simulation_id
            await writer.rollback()
            assert await reader.scalar(query) == simulation_id
    finally:
        if owner_id is not None:
            async with engine.begin() as cleanup:
                await cleanup.execute(delete(Session).where(Session.id == owner_id))


async def test_session_lock_blocks_cleanup_until_transaction_ends(engine):
    factory = create_session_factory(engine)
    owner = make_session()
    owner_id = None
    try:
        async with factory() as seed:
            seed.add(owner)
            await seed.commit()
            owner_id, now = owner.id, owner.created_at
        async with factory() as locker, factory() as cleanup:
            assert (
                await SessionRepository(locker).find_active_by_id(
                    owner_id, now=now, for_update=True
                )
                is not None
            )
            locker_pid = await locker.scalar(text("SELECT pg_backend_pid()"))
            assert await cleanup.scalar(text("SELECT pg_backend_pid()")) != locker_pid
            await cleanup.execute(text("SET LOCAL lock_timeout = '100ms'"))
            with pytest.raises(DBAPIError) as error:
                await cleanup.execute(delete(Session).where(Session.id == owner_id))
            assert error.value.orig.sqlstate == "55P03"
            await cleanup.rollback()
            await locker.rollback()
            await cleanup.execute(text("SET LOCAL lock_timeout = '2s'"))
            await cleanup.execute(delete(Session).where(Session.id == owner_id))
            await cleanup.commit()
    finally:
        if owner_id is not None:
            async with engine.begin() as cleanup:
                await cleanup.execute(delete(Session).where(Session.id == owner_id))
