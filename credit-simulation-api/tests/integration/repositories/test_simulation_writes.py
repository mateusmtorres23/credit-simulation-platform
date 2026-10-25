from uuid import uuid4

import pytest
from factories import make_graph, make_simulation
from sqlalchemy import func, select

from app.models import BankResult, BankResultReason, Session, Simulation
from app.repositories.simulation_repository import SimulationRepository

pytestmark = pytest.mark.asyncio


async def test_add_stages_entire_graph_and_caller_can_rollback(db):
    graph = make_graph()
    SimulationRepository(db).add(graph.simulation)
    assert graph.simulation in db.new
    assert graph.simulation.id is None
    await db.flush()
    simulation_id, owner_id = graph.simulation.id, graph.session.id
    assert await db.scalar(select(func.count()).select_from(BankResult)) == 2
    assert await db.scalar(select(func.count()).select_from(BankResultReason)) == 2
    await db.rollback()
    assert await db.get(Simulation, simulation_id) is None
    assert await db.get(Session, owner_id) is None


@pytest.mark.parametrize("case", ["foreign", "missing", "expired"])
async def test_delete_does_not_remove_inaccessible_records(db, graph, case):
    owner = uuid4() if case == "foreign" else graph.session.id
    simulation_id = uuid4() if case == "missing" else graph.simulation.id
    now = graph.session.expires_at if case == "expired" else graph.session.created_at
    assert not await SimulationRepository(db).delete_for_session(
        simulation_id, owner, now=now
    )
    assert await db.scalar(select(func.count()).select_from(Simulation)) == 1
    assert await db.scalar(select(func.count()).select_from(BankResult)) == 2
    assert await db.scalar(select(func.count()).select_from(BankResultReason)) == 2


async def test_delete_cascades_only_target_and_preserves_owner_and_sibling(db, graph):
    sibling = make_simulation(graph.session)
    db.add(sibling)
    await db.flush()
    owner, target = graph.session.id, graph.simulation.id
    repo = SimulationRepository(db)
    assert await repo.delete_for_session(target, owner, now=graph.session.created_at)
    assert not await repo.delete_for_session(
        target, owner, now=graph.session.created_at
    )
    assert await db.scalar(select(func.count()).select_from(BankResult)) == 0
    assert await db.scalar(select(func.count()).select_from(BankResultReason)) == 0
    assert await db.get(Session, owner) is not None
    assert await db.get(Simulation, sibling.id) is not None
