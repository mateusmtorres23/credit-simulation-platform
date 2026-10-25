from datetime import timedelta
from uuid import UUID

import pytest
from factories import make_session, make_simulation

from app.repositories.simulation_repository import SimulationRepository

pytestmark = pytest.mark.asyncio


async def test_history_orders_by_date_then_id_and_paginates_only_owner(db):
    owner = make_session()
    now = owner.created_at
    records = [
        make_simulation(owner, id=UUID(int=1), created_at=now),
        make_simulation(owner, id=UUID(int=2), created_at=now),
        make_simulation(owner, id=UUID(int=3), created_at=now + timedelta(seconds=1)),
    ]
    db.add_all(records + [make_simulation()])
    await db.flush()
    repo = SimulationRepository(db)
    first = await repo.list_for_session(owner.id, now=now, page=1, page_size=2)
    second = await repo.list_for_session(owner.id, now=now, page=2, page_size=2)
    assert [item.id for item in first] == [UUID(int=3), UUID(int=2)]
    assert [item.id for item in second] == [UUID(int=1)]
    assert await repo.count_for_session(owner.id, now=now) == 3
    assert await repo.list_for_session(owner.id, now=now, page=3, page_size=2) == []


@pytest.mark.parametrize("page,page_size", [(0, 10), (-1, 10), (1, 0), (1, 51)])
async def test_invalid_pagination_is_rejected(db, saved_session, page, page_size):
    with pytest.raises(ValueError, match="Invalid history pagination"):
        await SimulationRepository(db).list_for_session(
            saved_session.id,
            now=saved_session.created_at,
            page=page,
            page_size=page_size,
        )


@pytest.mark.parametrize("page_size", [1, 50])
async def test_page_size_boundaries_are_accepted(db, saved_simulation, page_size):
    items = await SimulationRepository(db).list_for_session(
        saved_simulation.session_id,
        now=saved_simulation.created_at,
        page=1,
        page_size=page_size,
    )
    assert [item.id for item in items] == [saved_simulation.id]
