from pydantic import TypeAdapter

from app.models.bank_result import BankResult as StoredBankResult
from app.models.bank_result_reason import BankResultReason
from app.models.enums import BankResultStatus
from app.models.simulation import Simulation
from app.schemas.bank_result_schema import (
    ApprovedBankResult,
    BankResult,
    BankResultSummary,
    RejectedBankResult,
)
from app.schemas.response_schema import (
    SimulationDetailResponse,
    SimulationRequestSummary,
    SimulationSummary,
)

RESULT_ADAPTER = TypeAdapter(BankResult)


def store_bank_result(result: BankResult) -> StoredBankResult:
    stored = StoredBankResult(bank=result.bank, status=result.status, reasons=[])
    if isinstance(result, ApprovedBankResult):
        for name, value in result.offer.model_dump().items():
            setattr(stored, name, value)
    elif isinstance(result, RejectedBankResult):
        stored.reasons = [
            BankResultReason(code=reason.code, message=reason.message, position=index)
            for index, reason in enumerate(result.reasons)
        ]
    else:
        stored.error_code = result.error.code
        stored.error_message = result.error.message
    return stored


def restore_bank_result(stored: StoredBankResult) -> BankResult:
    data: dict[str, object] = {"bank": stored.bank, "status": stored.status}
    if stored.status == BankResultStatus.APPROVED:
        data["offer"] = {
            "amount_cents": stored.amount_cents,
            "term_months": stored.term_months,
            "monthly_interest_rate_bps": stored.monthly_interest_rate_bps,
            "installment_cents": stored.installment_cents,
        }
    elif stored.status == BankResultStatus.REJECTED:
        data["reasons"] = [
            {"code": reason.code, "message": reason.message}
            for reason in stored.reasons
        ]
    elif stored.status == BankResultStatus.FAILED:
        data["error"] = {"code": stored.error_code, "message": stored.error_message}
    return RESULT_ADAPTER.validate_python(data)


def simulation_detail(simulation: Simulation) -> SimulationDetailResponse:
    return SimulationDetailResponse(
        id=simulation.id,
        created_at=simulation.created_at,
        request=SimulationRequestSummary(
            monthly_income_cents=simulation.monthly_income_cents,
            requested_amount_cents=simulation.requested_amount_cents,
            term_months=simulation.term_months,
        ),
        results=[restore_bank_result(result) for result in simulation.bank_results],
    )


def simulation_summary(simulation: Simulation) -> SimulationSummary:
    return SimulationSummary(
        id=simulation.id,
        created_at=simulation.created_at,
        requested_amount_cents=simulation.requested_amount_cents,
        term_months=simulation.term_months,
        results=[
            BankResultSummary(bank=result.bank, status=result.status)
            for result in simulation.bank_results
        ],
    )
