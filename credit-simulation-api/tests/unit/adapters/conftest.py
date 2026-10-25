import httpx
import pytest
from pydantic import HttpUrl

from app.integrations.bank_a import BankAAdapter
from app.integrations.bank_b import BankBAdapter
from app.schemas.request_schema import SimulationCreate


@pytest.fixture(params=["a", "b"])
def bank_case(request):
    return request.param


@pytest.fixture
def simulation_request():
    return SimulationCreate(
        name="Cliente Fictício",
        email="cliente@example.com",
        cpf="00000000000",
        monthly_income_cents=300000,
        employer_cnpj="00000000000000",
        requested_amount_cents=100000,
        term_months=12,
    )


@pytest.fixture
def approval(bank_case):
    if bank_case == "a":
        return {
            "approved": True,
            "offer": {
                "amountCents": 100000,
                "termMonths": 12,
                "monthlyInterestRateBps": 180,
                "installmentCents": 9340,
            },
        }
    return {
        "decision": {
            "code": "ACCEPTED",
            "conditions": {
                "principal_cents": 100000,
                "installments": 12,
                "monthly_rate_bps": 210,
                "payment_cents": 9514,
            },
        }
    }


@pytest.fixture
def make_rejection(bank_case):
    def build(reasons):
        if bank_case == "a":
            return {"approved": False, "reasons": reasons}
        return {"decision": {"code": "DECLINED", "reasons": reasons}}

    return build


@pytest.fixture
def external_codes(bank_case):
    if bank_case == "a":
        return [
            "INCOME_BELOW_MINIMUM",
            "AMOUNT_ABOVE_LIMIT",
            "TERM_NOT_SUPPORTED",
            "INSTALLMENT_ABOVE_MARGIN",
        ]
    return ["LOW_INCOME", "LIMIT_EXCEEDED", "INVALID_TERM", "INSUFFICIENT_MARGIN"]


@pytest.fixture
def adapter_factory(bank_case):
    def build(handler, timeout=1.0):
        client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
        adapter_class = BankAAdapter if bank_case == "a" else BankBAdapter
        adapter = adapter_class(client, HttpUrl("http://bank.test/api/"), timeout)
        return client, adapter

    return build
