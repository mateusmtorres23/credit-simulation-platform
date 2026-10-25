from typing import Annotated, Literal

from pydantic import Field, TypeAdapter

from app.schemas.types import (
    MonthlyInterestRate,
    PositiveMoney,
    SimulationSchema,
    TermMonths,
)

BankBReason = Literal[
    "LOW_INCOME", "LIMIT_EXCEEDED", "INVALID_TERM", "INSUFFICIENT_MARGIN"
]


class BankBConditions(SimulationSchema):
    principal_cents: PositiveMoney
    installments: TermMonths
    monthly_rate_bps: MonthlyInterestRate
    payment_cents: PositiveMoney


class BankBAcceptance(SimulationSchema):
    code: Literal["ACCEPTED"]
    conditions: BankBConditions


class BankBDecline(SimulationSchema):
    code: Literal["DECLINED"]
    reasons: Annotated[list[BankBReason], Field(min_length=1)]


class BankBResponse(SimulationSchema):
    decision: Annotated[BankBAcceptance | BankBDecline, Field(discriminator="code")]


BANK_B_RESPONSE = TypeAdapter(BankBResponse)
