from uuid import uuid4

import pytest
from factories import (
    MAX_SAFE_INTEGER,
    make_bank_result,
)
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from app.models import BankResult
from app.models.enums import BankErrorCode, BankResultStatus

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    "field,value,constraint",
    [
        ("amount_cents", 0, "ck_bank_results_amount_cents_range"),
        ("amount_cents", MAX_SAFE_INTEGER + 1, "ck_bank_results_amount_cents_range"),
        ("installment_cents", 0, "ck_bank_results_installment_cents_range"),
        (
            "installment_cents",
            MAX_SAFE_INTEGER + 1,
            "ck_bank_results_installment_cents_range",
        ),
        (
            "monthly_interest_rate_bps",
            -1,
            "ck_bank_results_monthly_interest_rate_bps_range",
        ),
        (
            "monthly_interest_rate_bps",
            MAX_SAFE_INTEGER + 1,
            "ck_bank_results_monthly_interest_rate_bps_range",
        ),
        ("term_months", 0, "ck_bank_results_term_months_range"),
        ("term_months", 121, "ck_bank_results_term_months_range"),
    ],
)
async def test_rejects_out_of_range_values(
    db, approved_result, field, value, constraint
):
    with pytest.raises(IntegrityError, match=constraint):
        async with db.begin_nested():
            await db.execute(
                update(BankResult)
                .where(BankResult.id == approved_result.id)
                .values({field: value})
            )


@pytest.mark.parametrize(
    "field,low,high",
    [
        ("amount_cents", 1, MAX_SAFE_INTEGER),
        ("installment_cents", 1, MAX_SAFE_INTEGER),
        ("monthly_interest_rate_bps", 0, MAX_SAFE_INTEGER),
        ("term_months", 1, 120),
    ],
)
async def test_accepts_boundaries(db, approved_result, field, low, high):
    for value in (low, high):
        await db.execute(
            update(BankResult)
            .where(BankResult.id == approved_result.id)
            .values({field: value})
        )


@pytest.mark.parametrize(
    "changes",
    [
        {"amount_cents": None},
        {"term_months": None},
        {"monthly_interest_rate_bps": None},
        {"installment_cents": None},
        {"error_code": BankErrorCode.TIMEOUT},
        {"error_message": "Unexpected error"},
        {"status": BankResultStatus.REJECTED},
        {"status": BankResultStatus.FAILED},
    ],
)
async def test_approved_result_requires_complete_offer_without_error(
    db, approved_result, changes
):
    with pytest.raises(IntegrityError, match="ck_bank_results_status_fields"):
        async with db.begin_nested():
            await db.execute(
                update(BankResult)
                .where(BankResult.id == approved_result.id)
                .values(**changes)
            )


@pytest.mark.parametrize(
    "changes",
    [
        {"status": BankResultStatus.APPROVED},
        {"amount_cents": 100},
        {"term_months": 12},
        {"monthly_interest_rate_bps": 0},
        {"installment_cents": 1},
        {"error_code": BankErrorCode.TIMEOUT},
        {"error_message": "Timeout"},
        {"status": BankResultStatus.FAILED},
        {"status": BankResultStatus.FAILED, "error_code": BankErrorCode.TIMEOUT},
        {"status": BankResultStatus.FAILED, "error_message": "Timeout"},
    ],
)
async def test_rejected_and_failed_result_field_combinations(
    db, rejected_result, changes
):
    with pytest.raises(IntegrityError, match="ck_bank_results_status_fields"):
        async with db.begin_nested():
            await db.execute(
                update(BankResult)
                .where(BankResult.id == rejected_result.id)
                .values(**changes)
            )


@pytest.mark.parametrize("parent_id", [None, "missing"])
async def test_result_requires_existing_simulation(db, approved_result, parent_id):
    with pytest.raises(IntegrityError):
        async with db.begin_nested():
            await db.execute(
                update(BankResult)
                .where(BankResult.id == approved_result.id)
                .values(simulation_id=None if parent_id is None else uuid4())
            )


async def test_one_result_per_bank_per_simulation(db, approved_result):
    with pytest.raises(IntegrityError, match="uq_bank_results_simulation_bank"):
        async with db.begin_nested():
            duplicate = make_bank_result(approved_result.simulation)
            db.add(duplicate)
            await db.flush()


async def test_failed_result_round_trip(db):
    failed = make_bank_result(status=BankResultStatus.FAILED)
    db.add(failed)
    await db.flush()
    result_id = failed.id
    db.expunge_all()
    saved = await db.get(BankResult, result_id)
    assert saved.error_code is BankErrorCode.TIMEOUT
    assert saved.error_message == "O banco não respondeu."
    assert saved.amount_cents is None


@pytest.mark.parametrize("message", ["", " ", "\t\r\n"])
async def test_blank_error_message_is_rejected(db, message):
    with pytest.raises(IntegrityError, match="ck_bank_results_error_message_not_blank"):
        async with db.begin_nested():
            failed = make_bank_result(
                status=BankResultStatus.FAILED, error_message=message
            )
            db.add(failed)
            await db.flush()
