from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, Field

from app.models.enums import Bank
from app.schemas.bank_result_schema import (
    BankResult,
    BankResultBase,
    BankResultSummary,
)
from app.schemas.request_schema import SimulationPagination
from app.schemas.types import (
    PositiveMoney,
    RequestedAmount,
    SimulationSchema,
    SimulationTimestamp,
    TermMonths,
)


class SimulationRequestSummary(SimulationSchema):
    monthly_income_cents: PositiveMoney
    requested_amount_cents: RequestedAmount
    term_months: TermMonths


def _require_bank_order[Result: BankResultBase](results: list[Result]) -> list[Result]:
    if [result.bank for result in results] != [Bank.BANK_A, Bank.BANK_B]:
        raise ValueError(
            "Results must contain Bank A followed by Bank B, exactly once."
        )
    return results


CompleteBankResults = Annotated[
    list[BankResult],
    Field(min_length=2, max_length=2),
    AfterValidator(_require_bank_order),
]


SummaryBankResults = Annotated[
    list[BankResultSummary],
    Field(min_length=2, max_length=2),
    AfterValidator(_require_bank_order),
]


class SimulationRecord(SimulationSchema):
    id: UUID
    created_at: SimulationTimestamp


class SimulationCreatedResponse(SimulationRecord):
    results: CompleteBankResults


class SimulationDetailResponse(SimulationCreatedResponse):
    request: SimulationRequestSummary


class SimulationSummary(SimulationRecord):
    requested_amount_cents: RequestedAmount
    term_months: TermMonths
    results: SummaryBankResults


class SimulationHistoryResponse(SimulationPagination):
    items: list[SimulationSummary]
    total: Annotated[int, Field(strict=True, ge=0)]
