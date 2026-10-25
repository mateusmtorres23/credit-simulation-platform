from uuid import uuid4

import pytest
from factories import (
    make_reason,
)
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError

from app.models import BankResultReason
from app.models.enums import RejectionCode

pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize("message", ["", " ", "\t\r\n"])
async def test_blank_message_is_rejected(db, saved_reason, message):
    with pytest.raises(
        IntegrityError, match="ck_bank_result_reasons_message_not_blank"
    ):
        async with db.begin_nested():
            await db.execute(
                update(BankResultReason)
                .where(BankResultReason.id == saved_reason.id)
                .values(message=message)
            )


async def test_position_cannot_be_negative(db, saved_reason):
    with pytest.raises(
        IntegrityError, match="ck_bank_result_reasons_position_nonnegative"
    ):
        async with db.begin_nested():
            await db.execute(
                update(BankResultReason)
                .where(BankResultReason.id == saved_reason.id)
                .values(position=-1)
            )


@pytest.mark.parametrize("parent_id", [None, "missing"])
async def test_reason_requires_existing_result(db, saved_reason, parent_id):
    with pytest.raises(IntegrityError):
        async with db.begin_nested():
            await db.execute(
                update(BankResultReason)
                .where(BankResultReason.id == saved_reason.id)
                .values(bank_result_id=None if parent_id is None else uuid4())
            )


@pytest.mark.parametrize(
    "code,position,constraint",
    [
        (RejectionCode.TERM_NOT_SUPPORTED, 1, "uq_bank_result_reasons_result_code"),
        (RejectionCode.AMOUNT_ABOVE_LIMIT, 0, "uq_bank_result_reasons_result_position"),
    ],
)
async def test_duplicate_code_or_position_is_rejected(
    db, saved_reason, code, position, constraint
):
    with pytest.raises(IntegrityError, match=constraint):
        async with db.begin_nested():
            duplicate = make_reason(
                saved_reason.bank_result, code=code, position=position
            )
            db.add(duplicate)
            await db.flush()
