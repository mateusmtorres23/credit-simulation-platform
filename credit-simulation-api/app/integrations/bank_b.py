import httpx
from pydantic import HttpUrl, ValidationError

from app.integrations.bank_b_contract import BANK_B_RESPONSE, BankBAcceptance
from app.integrations.bank_http import failed_result, query_bank, rejection_reason
from app.models.enums import Bank, BankErrorCode, BankResultStatus, RejectionCode
from app.schemas.bank_result_schema import (
    ApprovedBankResult,
    BankOffer,
    BankResult,
    FailedBankResult,
    RejectedBankResult,
)
from app.schemas.request_schema import BankScenario, SimulationCreate

REJECTION_CODES = {
    "LOW_INCOME": RejectionCode.INCOME_BELOW_MINIMUM,
    "LIMIT_EXCEEDED": RejectionCode.AMOUNT_ABOVE_LIMIT,
    "INVALID_TERM": RejectionCode.TERM_NOT_SUPPORTED,
    "INSUFFICIENT_MARGIN": RejectionCode.INSTALLMENT_ABOVE_MARGIN,
}


class BankBAdapter:
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
            "applicant": {
                "full_name": request.name,
                "email_address": str(request.email),
                "tax_id": request.cpf,
                "income_cents": request.monthly_income_cents,
                "employer_tax_id": request.employer_cnpj,
            },
            "loan": {
                "amount_cents": request.requested_amount_cents,
                "installments": request.term_months,
            },
        }
        response = await query_bank(
            self._client,
            self._base_url,
            self._timeout_seconds,
            scenario,
            payload,
            Bank.BANK_B,
        )
        if isinstance(response, FailedBankResult):
            return response
        try:
            decision = BANK_B_RESPONSE.validate_json(response.content).decision
            if isinstance(decision, BankBAcceptance):
                offer = decision.conditions
                return ApprovedBankResult(
                    bank=Bank.BANK_B,
                    status=BankResultStatus.APPROVED,
                    offer=BankOffer(
                        amount_cents=offer.principal_cents,
                        term_months=offer.installments,
                        monthly_interest_rate_bps=offer.monthly_rate_bps,
                        installment_cents=offer.payment_cents,
                    ),
                )
            return RejectedBankResult(
                bank=Bank.BANK_B,
                status=BankResultStatus.REJECTED,
                reasons=[
                    rejection_reason(REJECTION_CODES[code]) for code in decision.reasons
                ],
            )
        except ValidationError:
            return failed_result(Bank.BANK_B, BankErrorCode.INVALID_BANK_RESPONSE)
