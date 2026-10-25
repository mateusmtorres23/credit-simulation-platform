from typing import Annotated, Literal

from pydantic import BeforeValidator, EmailStr, Field, StringConstraints

from app.schemas.types import (
    PositiveMoney,
    RequestedAmount,
    SimulationSchema,
    TermMonths,
)


def _prepare_email(value: object) -> object:
    if isinstance(value, str):
        value = value.strip()
        if len(value) > 254:
            raise ValueError("Email must have at most 254 characters.")
    return value


BankScenario = Literal["normal", "slow", "unavailable"]


class SimulationCreate(SimulationSchema):
    name: Annotated[
        str,
        StringConstraints(
            strict=True, strip_whitespace=True, min_length=1, max_length=150
        ),
    ]
    email: Annotated[EmailStr, Field(strict=True), BeforeValidator(_prepare_email)]
    cpf: Annotated[str, StringConstraints(strict=True, pattern=r"^[0-9]{11}$")]
    monthly_income_cents: PositiveMoney
    employer_cnpj: Annotated[
        str, StringConstraints(strict=True, pattern=r"^[0-9]{14}$")
    ]
    requested_amount_cents: RequestedAmount
    term_months: TermMonths


class SimulationScenarios(SimulationSchema):
    bank_a_scenario: BankScenario = "normal"
    bank_b_scenario: BankScenario = "normal"


class SimulationPagination(SimulationSchema):
    # Query parameters arrive as strings; body/offer integers remain strict.
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=10, ge=1, le=50)
