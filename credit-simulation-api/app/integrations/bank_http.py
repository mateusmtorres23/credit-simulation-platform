import asyncio

import httpx
from pydantic import HttpUrl

from app.models.enums import Bank, BankErrorCode, BankResultStatus, RejectionCode
from app.schemas.bank_result_schema import BankError, FailedBankResult, RejectionReason
from app.schemas.request_schema import BankScenario

ERROR_MESSAGES = {
    BankErrorCode.TIMEOUT: "O banco não respondeu dentro do tempo limite.",
    BankErrorCode.BANK_UNAVAILABLE: "O banco está temporariamente indisponível.",
    BankErrorCode.INVALID_BANK_RESPONSE: "Não foi possível interpretar a resposta do banco.",
}
REJECTION_MESSAGES = {
    RejectionCode.INCOME_BELOW_MINIMUM: "A renda informada está abaixo do mínimo exigido pelo banco.",
    RejectionCode.AMOUNT_ABOVE_LIMIT: "O valor solicitado supera o limite oferecido pelo banco.",
    RejectionCode.TERM_NOT_SUPPORTED: "O banco não oferece o prazo solicitado.",
    RejectionCode.INSTALLMENT_ABOVE_MARGIN: "A parcela estimada supera a margem de renda aceita pelo banco.",
}


def failed_result(bank: Bank, code: BankErrorCode) -> FailedBankResult:
    return FailedBankResult(
        bank=bank,
        status=BankResultStatus.FAILED,
        error=BankError(code=code, message=ERROR_MESSAGES[code]),
    )


def rejection_reason(code: RejectionCode) -> RejectionReason:
    return RejectionReason(code=code, message=REJECTION_MESSAGES[code])


async def query_bank(
    client: httpx.AsyncClient,
    base_url: HttpUrl,
    timeout_seconds: float,
    scenario: BankScenario,
    payload: dict[str, object],
    bank: Bank,
) -> httpx.Response | FailedBankResult:
    url = str(base_url).rstrip("/") + f"/evaluations/{scenario}"
    try:
        # Includes pool waiting and reading the full response, with no retry.
        async with asyncio.timeout(timeout_seconds):
            response = await client.post(
                url, json=payload, timeout=timeout_seconds, follow_redirects=False
            )
    except (TimeoutError, httpx.TimeoutException):
        return failed_result(bank, BankErrorCode.TIMEOUT)
    except (httpx.NetworkError, httpx.ProxyError):
        return failed_result(bank, BankErrorCode.BANK_UNAVAILABLE)
    except (httpx.TransportError, httpx.DecodingError):
        return failed_result(bank, BankErrorCode.INVALID_BANK_RESPONSE)
    if response.status_code == 503:
        return failed_result(bank, BankErrorCode.BANK_UNAVAILABLE)
    if response.status_code != 200:
        return failed_result(bank, BankErrorCode.INVALID_BANK_RESPONSE)
    return response
