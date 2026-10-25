from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.errors import SimulationNotFound
from app.models import BankResult, BankResultReason, Session, Simulation
from app.schemas.request_schema import SimulationPagination

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize("credential", [None, "invalid", "unknown", "expired"])
async def test_inaccessible_session_has_empty_history_and_uniform_not_found(
    persisted_service, service_clock, credential
):
    ctx = persisted_service
    created = await ctx.service.create(ctx.request, ctx.scenarios, None)
    token = credential
    if credential == "unknown":
        token = "a" * 43
    elif credential == "expired":
        token = created.new_token
        service_clock.now += timedelta(days=7)
    history = await ctx.service.list_history(
        token, SimulationPagination(page=3, page_size=2)
    )
    assert history.model_dump() == {"items": [], "total": 0, "page": 3, "page_size": 2}
    with pytest.raises(SimulationNotFound):
        await ctx.service.get_detail(created.response.id, token)
    with pytest.raises(SimulationNotFound):
        await ctx.service.delete(created.response.id, token)
    async with ctx.db.begin():
        assert await ctx.db.scalar(select(func.count()).select_from(Session)) == 1
        assert await ctx.db.scalar(select(func.count()).select_from(Simulation)) == 1


async def test_foreign_and_missing_simulations_share_not_found(persisted_service):
    ctx = persisted_service
    first = await ctx.service.create(ctx.request, ctx.scenarios, None)
    other = await ctx.service.create(ctx.request, ctx.scenarios, None)
    for simulation_id in (first.response.id, uuid4()):
        with pytest.raises(SimulationNotFound):
            await ctx.service.get_detail(simulation_id, other.new_token)
        with pytest.raises(SimulationNotFound):
            await ctx.service.delete(simulation_id, other.new_token)


async def test_delete_commits_cascades_and_preserves_other_records(persisted_service):
    ctx = persisted_service
    first = await ctx.service.create(ctx.request, ctx.scenarios, None)
    sibling = await ctx.service.create(ctx.request, ctx.scenarios, first.new_token)
    await ctx.service.delete(first.response.id, first.new_token)
    with pytest.raises(SimulationNotFound):
        await ctx.service.get_detail(first.response.id, first.new_token)
    assert (
        await ctx.service.get_detail(sibling.response.id, first.new_token)
    ).id == sibling.response.id
    async with ctx.db.begin():
        for model, expected in [
            (Session, 1),
            (Simulation, 1),
            (BankResult, 2),
            (BankResultReason, 0),
        ]:
            assert (
                await ctx.db.scalar(select(func.count()).select_from(model)) == expected
            )
    for bank in ctx.banks:
        assert bank.evaluate.await_count == 2
