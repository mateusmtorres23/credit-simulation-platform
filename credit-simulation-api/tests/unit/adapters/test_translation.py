import json

import httpx
import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", ["normal", "slow", "unavailable"])
async def test_request_translation_and_endpoint_selection(
    bank_case, approval, adapter_factory, simulation_request, scenario
):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=approval)

    original = simulation_request.model_dump()
    client, adapter = adapter_factory(handler)
    async with client:
        result = await adapter.evaluate(simulation_request, scenario)
        assert not client.is_closed
    assert simulation_request.model_dump() == original
    assert len(calls) == 1
    assert calls[0].method == "POST"
    assert str(calls[0].url) == f"http://bank.test/api/evaluations/{scenario}"
    if bank_case == "a":
        expected = {
            "name": "Cliente Fictício",
            "email": "cliente@example.com",
            "cpf": "00000000000",
            "monthlyIncomeCents": 300000,
            "employerCnpj": "00000000000000",
            "requestedAmountCents": 100000,
            "termMonths": 12,
        }
    else:
        expected = {
            "applicant": {
                "full_name": "Cliente Fictício",
                "email_address": "cliente@example.com",
                "tax_id": "00000000000",
                "income_cents": 300000,
                "employer_tax_id": "00000000000000",
            },
            "loan": {"amount_cents": 100000, "installments": 12},
        }
    assert json.loads(calls[0].content) == expected
    assert result.bank == f"bank_{bank_case}"
    assert result.status == "approved"
    assert result.offer.model_dump() == {
        "amount_cents": 100000,
        "term_months": 12,
        "monthly_interest_rate_bps": 180 if bank_case == "a" else 210,
        "installment_cents": 9340 if bank_case == "a" else 9514,
    }


@pytest.mark.asyncio
async def test_all_rejection_codes_are_translated_in_original_order(
    adapter_factory, make_rejection, external_codes, simulation_request
):
    payload = make_rejection(external_codes[::-1])
    client, adapter = adapter_factory(lambda request: httpx.Response(200, json=payload))
    async with client:
        result = await adapter.evaluate(simulation_request, "normal")
    assert result.status == "rejected"
    assert [(reason.code, reason.message) for reason in result.reasons] == [
        (
            "INSTALLMENT_ABOVE_MARGIN",
            "A parcela estimada supera a margem de renda aceita pelo banco.",
        ),
        ("TERM_NOT_SUPPORTED", "O banco não oferece o prazo solicitado."),
        (
            "AMOUNT_ABOVE_LIMIT",
            "O valor solicitado supera o limite oferecido pelo banco.",
        ),
        (
            "INCOME_BELOW_MINIMUM",
            "A renda informada está abaixo do mínimo exigido pelo banco.",
        ),
    ]
