from typing import Annotated, Literal

from pydantic import Field, TypeAdapter, model_validator

from app.models.enums import RejectionCode
from app.schemas.types import (
    MonthlyInterestRate,
    PositiveMoney,
    SimulationSchema,
    TermMonths,
)


class BankAOffer(SimulationSchema):
    amountCents: PositiveMoney
    termMonths: TermMonths
    monthlyInterestRateBps: MonthlyInterestRate
    installmentCents: PositiveMoney


class BankAResponse(SimulationSchema):
    @model_validator(mode="before")
    @classmethod
    def require_boolean_decision(cls, value: object) -> object:
        if (
            isinstance(value, dict)
            and "approved" in value
            and type(value["approved"]) is not bool
        ):
            raise ValueError("Bank A decision must be a boolean.")
        return value


class BankAApproval(BankAResponse):
    approved: Literal[True]
    offer: BankAOffer


class BankARejection(BankAResponse):
    approved: Literal[False]
    reasons: Annotated[list[RejectionCode], Field(min_length=1)]


BANK_A_RESPONSE = TypeAdapter(
    Annotated[BankAApproval | BankARejection, Field(discriminator="approved")]
)
