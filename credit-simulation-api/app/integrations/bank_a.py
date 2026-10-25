import httpx
from pydantic import HttpUrl, ValidationError

from app.integrations.bank_a_contract import BANK_A_RESPONSE, BankAApproval
from app.integrations.bank_http import failed_result, query_bank, rejection_reason
from app.models.enums import Bank, BankErrorCode, BankResultStatus
from app.schemas.bank_result_schema import (
    ApprovedBankResult,
    BankOffer,
    BankResult,
    FailedBankResult,
    RejectedBankResult,
)
from app.schemas.request_schema import BankScenario, SimulationCreate


class BankAAdapter:
    def __init__(
        self, client: httpx.AsyncClient, base_url: HttpUrl, timeout_seconds: float
    ) -> None:
        self._client = client
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds

    async def evaluate(
        self, request: SimulationCreate, scenario: BankScenario
    ) -> BankResult:
        payload: dict[str, object] = {
            "name": request.name,
            "email": str(request.email),
            "cpf": request.cpf,
            "monthlyIncomeCents": request.monthly_income_cents,
            "employerCnpj": request.employer_cnpj,
            "requestedAmountCents": request.requested_amount_cents,
            "termMonths": request.term_months,
        }
        response = await query_bank(
            self._client,
            self._base_url,
            self._timeout_seconds,
            scenario,
            payload,
            Bank.BANK_A,
        )
        if isinstance(response, FailedBankResult):
            return response
        try:
            evaluation = BANK_A_RESPONSE.validate_json(response.content)
            if isinstance(evaluation, BankAApproval):
                offer = evaluation.offer
                return ApprovedBankResult(
                    bank=Bank.BANK_A,
                    status=BankResultStatus.APPROVED,
                    offer=BankOffer(
                        amount_cents=offer.amountCents,
                        term_months=offer.termMonths,
                        monthly_interest_rate_bps=offer.monthlyInterestRateBps,
                        installment_cents=offer.installmentCents,
                    ),
                )
            return RejectedBankResult(
                bank=Bank.BANK_A,
                status=BankResultStatus.REJECTED,
                reasons=[rejection_reason(code) for code in evaluation.reasons],
            )
        except ValidationError:
            return failed_result(Bank.BANK_A, BankErrorCode.INVALID_BANK_RESPONSE)
