import httpx
import pytest


@pytest.mark.asyncio
@pytest.mark.parametrize("reasons", [[], ["UNKNOWN"], None, "LOW_INCOME"])
async def test_invalid_rejection_contract_is_a_technical_failure(
    adapter_factory, make_rejection, simulation_request, reasons
):
    client, adapter = adapter_factory(
        lambda request: httpx.Response(200, json=make_rejection(reasons))
    )
    async with client:
        result = await adapter.evaluate(simulation_request, "normal")
    assert result.status == "failed"
    assert result.error.code == "INVALID_BANK_RESPONSE"


@pytest.mark.asyncio
async def test_duplicate_reasons_are_invalid(
    adapter_factory, make_rejection, external_codes, simulation_request
):
    payload = make_rejection([external_codes[0], external_codes[0]])
    client, adapter = adapter_factory(lambda request: httpx.Response(200, json=payload))
    async with client:
        result = await adapter.evaluate(simulation_request, "normal")
    assert result.error.code == "INVALID_BANK_RESPONSE"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "field_index,value",
    [
        (0, 0),
        (0, 9007199254740992),
        (0, "100000"),
        (0, True),
        (1, 0),
        (1, 121),
        (1, 12.5),
        (2, -1),
        (2, 9007199254740992),
        (3, 0),
    ],
)
async def test_invalid_offer_values_are_not_coerced_or_persisted(
    bank_case, approval, adapter_factory, simulation_request, field_index, value
):
    offer = (
        approval["offer"] if bank_case == "a" else approval["decision"]["conditions"]
    )
    offer[list(offer)[field_index]] = value
    client, adapter = adapter_factory(
        lambda request: httpx.Response(200, json=approval)
    )
    async with client:
        result = await adapter.evaluate(simulation_request, "normal")
    assert result.status == "failed"
    assert result.error.code == "INVALID_BANK_RESPONSE"


@pytest.mark.asyncio
@pytest.mark.parametrize("payload", [b"not-json", b"null", b"[]", b"{}"])
async def test_malformed_or_missing_contract_is_invalid(
    adapter_factory, simulation_request, payload
):
    client, adapter = adapter_factory(
        lambda request: httpx.Response(200, content=payload)
    )
    async with client:
        result = await adapter.evaluate(simulation_request, "normal")
    assert result.error.code == "INVALID_BANK_RESPONSE"


@pytest.mark.asyncio
@pytest.mark.parametrize("mutation", ["extra", "missing", "wrong_decision", "mixed"])
async def test_response_structure_must_match_exactly(
    bank_case, approval, adapter_factory, simulation_request, mutation
):
    envelope = approval if bank_case == "a" else approval["decision"]
    if mutation == "extra":
        envelope["private-field"] = "private-data"
    elif mutation == "missing":
        del envelope["offer" if bank_case == "a" else "conditions"]
    elif mutation == "wrong_decision":
        envelope["approved" if bank_case == "a" else "code"] = 1
    else:
        envelope["reasons"] = ["INCOME_BELOW_MINIMUM"]
    client, adapter = adapter_factory(
        lambda request: httpx.Response(200, json=approval)
    )
    async with client:
        result = await adapter.evaluate(simulation_request, "normal")
    assert result.error.code == "INVALID_BANK_RESPONSE"
    assert "private-" not in result.model_dump_json()


@pytest.mark.asyncio
@pytest.mark.parametrize("rate", [0, 9007199254740991])
async def test_rate_boundaries_are_accepted(
    bank_case, approval, adapter_factory, simulation_request, rate
):
    offer = (
        approval["offer"] if bank_case == "a" else approval["decision"]["conditions"]
    )
    offer["monthlyInterestRateBps" if bank_case == "a" else "monthly_rate_bps"] = rate
    client, adapter = adapter_factory(
        lambda request: httpx.Response(200, json=approval)
    )
    async with client:
        result = await adapter.evaluate(simulation_request, "normal")
    assert result.offer.monthly_interest_rate_bps == rate
