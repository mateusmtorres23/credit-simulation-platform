from uuid import uuid4

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import InvalidRequestError

from app.models.enums import Bank, RejectionCode
from app.repositories.simulation_repository import SimulationRepository

pytestmark = pytest.mark.asyncio


async def test_detail_loads_complete_graph_in_bank_and_reason_order(db, graph):
    simulation_id, owner_id = graph.simulation.id, graph.session.id
    now = graph.session.created_at
    db.expunge_all()
    result = await SimulationRepository(db).find_for_session(
        simulation_id, owner_id, now=now
    )
    db.expunge_all()
    assert [item.bank for item in result.bank_results] == [Bank.BANK_A, Bank.BANK_B]
    assert result.bank_results[0].amount_cents == 100000
    assert result.bank_results[0].reasons == []
    assert [reason.code for reason in result.bank_results[1].reasons] == [
        RejectionCode.INCOME_BELOW_MINIMUM,
        RejectionCode.TERM_NOT_SUPPORTED,
    ]


@pytest.mark.parametrize("case", ["foreign", "missing", "expired"])
async def test_detail_list_and_count_reject_inaccessible_sessions(db, graph, case):
    repo = SimulationRepository(db)
    owner = uuid4() if case == "foreign" else graph.session.id
    simulation_id = uuid4() if case == "missing" else graph.simulation.id
    now = graph.session.expires_at if case == "expired" else graph.session.created_at
    assert await repo.find_for_session(simulation_id, owner, now=now) is None
    # A missing simulation does not hide other valid records in the same session.
    expected = 1 if case == "missing" else 0
    assert await repo.count_for_session(owner, now=now) == expected
    assert (
        len(await repo.list_for_session(owner, now=now, page=1, page_size=10))
        == expected
    )


async def test_history_loads_only_result_summary_without_lazy_io(db, graph):
    owner_id, now = graph.session.id, graph.session.created_at
    db.expunge_all()
    items = await SimulationRepository(db).list_for_session(
        owner_id, now=now, page=1, page_size=10
    )
    assert len(items) == 1
    assert [result.bank for result in items[0].bank_results] == [
        Bank.BANK_A,
        Bank.BANK_B,
    ]
    for result in items[0].bank_results:
        assert "amount_cents" in inspect(result).unloaded
        assert "reasons" in inspect(result).unloaded
        with pytest.raises(InvalidRequestError):
            _ = result.amount_cents
        with pytest.raises(InvalidRequestError):
            _ = result.reasons


async def test_detail_after_history_loads_previously_deferred_offer_and_reasons(
    db, graph
):
    owner_id, simulation_id, now = (
        graph.session.id,
        graph.simulation.id,
        graph.session.created_at,
    )
    db.expunge_all()
    repo = SimulationRepository(db)
    summary = (await repo.list_for_session(owner_id, now=now, page=1, page_size=10))[0]
    detail = await repo.find_for_session(simulation_id, owner_id, now=now)
    assert detail is summary
    assert detail.bank_results[0].amount_cents == 100000
    assert len(detail.bank_results[1].reasons) == 2
