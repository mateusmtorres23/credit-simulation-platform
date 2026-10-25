import pytest
from factories import (
    make_graph,
)
from sqlalchemy import delete, func, select, text
from sqlalchemy.orm import selectinload

from app.models import BankResult, BankResultReason, Session, Simulation
from app.models.enums import Bank, RejectionCode

pytestmark = pytest.mark.asyncio


async def test_generated_uuids_are_unique_v4(db, graph):
    records = [
        graph.session,
        graph.simulation,
        graph.approved_result,
        graph.rejected_result,
        *graph.rejected_result.reasons,
    ]
    ids = [record.id for record in records]
    assert len(set(ids)) == len(records)
    assert all(value.version == 4 for value in ids)


async def test_relationship_loading_and_order(db, graph):
    simulation_id = graph.simulation.id
    db.expunge_all()
    saved = (
        await db.scalars(
            select(Simulation)
            .where(Simulation.id == simulation_id)
            .options(
                selectinload(Simulation.session),
                selectinload(Simulation.bank_results).selectinload(BankResult.reasons),
            )
        )
    ).one()
    assert saved.session.id == graph.session.id
    assert [result.bank for result in saved.bank_results] == [Bank.BANK_A, Bank.BANK_B]
    assert saved.bank_results[0].installment_cents == 9340
    assert [reason.position for reason in saved.bank_results[1].reasons] == [0, 1]
    assert [reason.code for reason in saved.bank_results[1].reasons] == [
        RejectionCode.INCOME_BELOW_MINIMUM,
        RejectionCode.TERM_NOT_SUPPORTED,
    ]


async def test_enums_store_contract_values(db, graph):
    rows = (
        await db.execute(
            text("SELECT bank::text, status::text FROM bank_results ORDER BY bank")
        )
    ).all()
    assert rows == [("bank_a", "approved"), ("bank_b", "rejected")]


@pytest.mark.parametrize(
    "entity,expected",
    [
        ("session", {"sessions": 1, "simulations": 1, "bank_results": 2, "reasons": 2}),
        (
            "simulation",
            {"sessions": 2, "simulations": 1, "bank_results": 2, "reasons": 2},
        ),
        (
            "rejected_result",
            {"sessions": 2, "simulations": 2, "bank_results": 3, "reasons": 2},
        ),
    ],
)
async def test_postgresql_cascade_preserves_unrelated_records(
    db, graph, entity, expected
):
    other = make_graph()
    db.add(other.session)
    await db.flush()
    record = getattr(graph, entity)
    # Core DELETE bypasses the ORM unit of work: PostgreSQL must cascade.
    await db.execute(delete(type(record).__table__).where(type(record).id == record.id))
    models = {
        "sessions": Session,
        "simulations": Simulation,
        "bank_results": BankResult,
        "reasons": BankResultReason,
    }
    counts = {
        name: await db.scalar(select(func.count()).select_from(model))
        for name, model in models.items()
    }
    assert counts == expected
    assert await db.get(Session, other.session.id) is not None
