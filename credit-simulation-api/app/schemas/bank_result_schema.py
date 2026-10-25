from typing import Annotated, Literal

from pydantic import Field, field_validator

from app.models.enums import Bank, BankErrorCode, BankResultStatus, RejectionCode
from app.schemas.types import (
    MonthlyInterestRate,
    NonblankText,
    PositiveMoney,
    SimulationSchema,
    TermMonths,
)


class BankOffer(SimulationSchema):
    amount_cents: PositiveMoney
    term_months: TermMonths
    monthly_interest_rate_bps: MonthlyInterestRate
    installment_cents: PositiveMoney


class RejectionReason(SimulationSchema):
    code: RejectionCode
    message: NonblankText


class BankError(SimulationSchema):
    code: BankErrorCode
    message: NonblankText


class BankResultBase(SimulationSchema):
    bank: Bank


class ApprovedBankResult(BankResultBase):
    status: Literal[BankResultStatus.APPROVED]
    offer: BankOffer


class RejectedBankResult(BankResultBase):
    status: Literal[BankResultStatus.REJECTED]
    reasons: Annotated[list[RejectionReason], Field(min_length=1)]

    @field_validator("reasons")
    @classmethod
    def validate_unique_codes(
        cls, reasons: list[RejectionReason]
    ) -> list[RejectionReason]:
        if len({reason.code for reason in reasons}) != len(reasons):
            raise ValueError("Rejection codes must not be repeated.")
        return reasons


class FailedBankResult(BankResultBase):
    status: Literal[BankResultStatus.FAILED]
    error: BankError


BankResult = Annotated[
    ApprovedBankResult | RejectedBankResult | FailedBankResult,
    Field(discriminator="status"),
]


class BankResultSummary(BankResultBase):
    status: BankResultStatus
