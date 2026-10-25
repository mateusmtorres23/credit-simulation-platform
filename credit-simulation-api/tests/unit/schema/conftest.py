from uuid import uuid4

import pytest


@pytest.fixture
def request_data():
    return {
        "name": "Cliente Fictício",
        "email": "cliente@example.com",
        "cpf": "00000000000",
        "monthly_income_cents": 300000,
        "employer_cnpj": "00000000000000",
        "requested_amount_cents": 100000,
        "term_months": 12,
    }


@pytest.fixture
def offer_data():
    return {
        "amount_cents": 100000,
        "term_months": 12,
        "monthly_interest_rate_bps": 180,
        "installment_cents": 9340,
    }


def _make_bank_result(bank="bank_a", status="approved"):
    result = {"bank": bank, "status": status}
    if status == "approved":
        result["offer"] = {
            "amount_cents": 100000,
            "term_months": 12,
            "monthly_interest_rate_bps": 180,
            "installment_cents": 9340,
        }
    elif status == "rejected":
        result["reasons"] = [
            {"code": "INCOME_BELOW_MINIMUM", "message": "Renda abaixo do mínimo."}
        ]
    else:
        result["error"] = {"code": "TIMEOUT", "message": "O banco não respondeu."}
    return result


@pytest.fixture
def response_data():
    return {
        "id": str(uuid4()),
        "created_at": "2026-10-24T03:00:00Z",
        "results": [_make_bank_result(), _make_bank_result("bank_b", "failed")],
    }


@pytest.fixture
def bank_result():
    return _make_bank_result
