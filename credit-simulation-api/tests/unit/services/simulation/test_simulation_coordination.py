import asyncio

import pytest
from pydantic import ValidationError

from app.schemas.request_schema import SimulationScenarios

pytestmark = pytest.mark.asyncio


async def test_banks_run_concurrently_outside_transaction_in_fixed_order(
    simulation_context,
):
    ctx = simulation_context
    entered = [asyncio.Event(), asyncio.Event()]
    originals = [bank.evaluate.return_value for bank in ctx.banks]

    async def evaluate(index):
        assert not ctx.db.in_transaction()
        entered[index].set()
        await entered[1 - index].wait()
        return originals[index]

    async def evaluate_a(*args):
        return await evaluate(0)

    async def evaluate_b(*args):
        return await evaluate(1)

    ctx.banks[0].evaluate.side_effect = evaluate_a
    ctx.banks[1].evaluate.side_effect = evaluate_b
    scenarios = SimulationScenarios(
        bank_a_scenario="slow", bank_b_scenario="unavailable"
    )
    created = await asyncio.wait_for(
        ctx.service.create(ctx.request, scenarios, None), 2
    )
    assert [result.bank for result in created.response.results] == ["bank_a", "bank_b"]
    ctx.banks[0].evaluate.assert_awaited_once_with(ctx.request, "slow")
    ctx.banks[1].evaluate.assert_awaited_once_with(ctx.request, "unavailable")
    stored = ctx.repo.add.call_args.args[0]
    assert stored.created_at == created.response.created_at
    assert not ctx.db.in_transaction()
    assert created.new_token not in repr(created)


async def test_invalid_bank_identity_prevents_persistence(simulation_context):
    ctx = simulation_context
    ctx.banks[1].evaluate.return_value = ctx.banks[0].evaluate.return_value
    with pytest.raises(ValidationError):
        await ctx.service.create(ctx.request, ctx.scenarios, None)
    ctx.repo.add.assert_not_called()
    ctx.sessions.prepare_for_simulation.assert_not_awaited()


async def test_unexpected_bank_failure_cancels_sibling(simulation_context):
    ctx = simulation_context
    entered, cancelled = asyncio.Event(), asyncio.Event()

    async def failing(*args):
        await entered.wait()
        raise RuntimeError("programming failure")

    async def pending(*args):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    ctx.banks[0].evaluate.side_effect = failing
    ctx.banks[1].evaluate.side_effect = pending
    with pytest.raises(ExceptionGroup) as error:
        await asyncio.wait_for(ctx.service.create(ctx.request, ctx.scenarios, None), 2)
    assert isinstance(error.value.exceptions[0], RuntimeError)
    assert cancelled.is_set()
    ctx.repo.add.assert_not_called()


async def test_external_cancellation_propagates_without_persistence(simulation_context):
    ctx = simulation_context
    entered = asyncio.Event()

    async def pending(*args):
        entered.set()
        await asyncio.Event().wait()

    for bank in ctx.banks:
        bank.evaluate.side_effect = pending
    task = asyncio.create_task(ctx.service.create(ctx.request, ctx.scenarios, None))
    await asyncio.wait_for(entered.wait(), 2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    ctx.repo.add.assert_not_called()
