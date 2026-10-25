from datetime import timedelta
from uuid import uuid4

import pytest
from factories import MAX_SAFE_INTEGER
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from app.models import Simulation

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    "field,value,constraint",
    [
        ("monthly_income_cents", 0, "ck_simulations_monthly_income_cents_range"),
        (
            "monthly_income_cents",
            MAX_SAFE_INTEGER + 1,
            "ck_simulations_monthly_income_cents_range",
        ),
        ("requested_amount_cents", 99, "ck_simulations_requested_amount_cents_range"),
        (
            "requested_amount_cents",
            MAX_SAFE_INTEGER + 1,
            "ck_simulations_requested_amount_cents_range",
        ),
        ("term_months", 0, "ck_simulations_term_months_range"),
        ("term_months", 121, "ck_simulations_term_months_range"),
    ],
)
async def test_rejects_out_of_range_values(
    db, saved_simulation, field, value, constraint
):
    with pytest.raises(IntegrityError, match=constraint):
        async with db.begin_nested():
            await db.execute(
                update(Simulation)
                .where(Simulation.id == saved_simulation.id)
                .values({field: value})
            )


@pytest.mark.parametrize(
    "field,low,high",
    [
        ("monthly_income_cents", 1, MAX_SAFE_INTEGER),
        ("requested_amount_cents", 100, MAX_SAFE_INTEGER),
        ("term_months", 1, 120),
    ],
)
async def test_accepts_boundaries(db, saved_simulation, field, low, high):
    for value in (low, high):
        await db.execute(
            update(Simulation)
            .where(Simulation.id == saved_simulation.id)
            .values({field: value})
        )


@pytest.mark.parametrize("parent_id", [None, "missing"])
async def test_simulation_requires_existing_session(db, saved_simulation, parent_id):
    with pytest.raises(IntegrityError):
        async with db.begin_nested():
            await db.execute(
                update(Simulation)
                .where(Simulation.id == saved_simulation.id)
                .values(session_id=None if parent_id is None else uuid4())
            )


async def test_simulation_dates_and_request_round_trip(db, saved_simulation):
    simulation_id, created_at = saved_simulation.id, saved_simulation.created_at
    db.expunge_all()
    saved = await db.get(Simulation, simulation_id)
    assert saved.created_at == created_at
    assert saved.created_at.utcoffset() == timedelta(0)
    assert (
        saved.monthly_income_cents,
        saved.requested_amount_cents,
        saved.term_months,
    ) == (300000, 100000, 12)
