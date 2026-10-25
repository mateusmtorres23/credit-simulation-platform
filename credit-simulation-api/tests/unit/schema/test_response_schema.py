from copy import deepcopy
from datetime import UTC, datetime, timedelta, timezone
from itertools import product

import pytest
from pydantic import ValidationError

from app.schemas.response_schema import (
    SimulationCreatedResponse,
    SimulationDetailResponse,
    SimulationHistoryResponse,
    SimulationRequestSummary,
    SimulationSummary,
)


@pytest.mark.parametrize(
    "a,b", list(product(["approved", "rejected", "failed"], repeat=2))
)
def test_creation_supports_every_bank_status_combination(
    bank_result, response_data, a, b
):
    response_data["results"] = [bank_result("bank_a", a), bank_result("bank_b", b)]
    response = SimulationCreatedResponse(**response_data)
    assert [result.status.value for result in response.results] == [a, b]


@pytest.mark.parametrize(
    "banks",
    [
        [],
        ["bank_a"],
        ["bank_b", "bank_a"],
        ["bank_a", "bank_a"],
        ["bank_a", "bank_b", "bank_b"],
    ],
)
def test_response_requires_exactly_one_result_per_bank_in_order(
    bank_result, response_data, banks
):
    with pytest.raises(ValidationError):
        SimulationCreatedResponse(
            **(response_data | {"results": [bank_result(bank) for bank in banks]})
        )


def test_response_uuid_and_utc_json_round_trip(response_data):
    response_data["created_at"] = datetime(
        2026, 10, 24, tzinfo=timezone(timedelta(hours=-3))
    )
    response = SimulationCreatedResponse(**response_data)
    assert response.created_at == datetime(2026, 10, 24, 3, tzinfo=UTC)
    assert response.model_dump(mode="json")["created_at"] == "2026-10-24T03:00:00Z"
    assert (
        SimulationCreatedResponse.model_validate_json(response.model_dump_json())
        == response
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"id": "invalid"},
        {"created_at": "2026-10-24T00:00:00"},
        {"created_at": datetime(2026, 10, 24)},
    ],
)
def test_response_requires_uuid_and_timezone(response_data, changes):
    with pytest.raises(ValidationError):
        SimulationCreatedResponse(**(response_data | changes))


def test_detail_preserves_only_approved_request_fields(response_data, request_data):
    request = {
        key: request_data[key]
        for key in ("monthly_income_cents", "requested_amount_cents", "term_months")
    }
    detail = SimulationDetailResponse(**response_data, request=request)
    assert detail.model_dump(mode="json")["request"] == request
    for personal in ("name", "email", "cpf", "employer_cnpj"):
        with pytest.raises(ValidationError):
            SimulationRequestSummary(**(request | {personal: request_data[personal]}))
    with pytest.raises(ValidationError):
        SimulationDetailResponse(**response_data)


def test_history_summary_excludes_full_results(response_data):
    data = deepcopy(response_data)
    data.update(requested_amount_cents=100000, term_months=12)
    with pytest.raises(ValidationError):
        SimulationSummary(**data)
    data["results"] = [
        {"bank": "bank_a", "status": "approved"},
        {"bank": "bank_b", "status": "failed"},
    ]
    item = SimulationSummary(**data)
    history = SimulationHistoryResponse(items=[item], page=1, page_size=10, total=1)
    assert history.model_dump(mode="json")["items"][0] == data
    assert SimulationHistoryResponse(items=[], total=0).items == []


def test_history_results_also_require_bank_order(response_data):
    with pytest.raises(ValidationError):
        SimulationSummary(
            id=response_data["id"],
            created_at=response_data["created_at"],
            requested_amount_cents=100000,
            term_months=12,
            results=[
                {"bank": "bank_b", "status": "approved"},
                {"bank": "bank_a", "status": "failed"},
            ],
        )


@pytest.mark.parametrize("total", [-1, "1", True])
def test_history_total_is_a_nonnegative_integer(total):
    with pytest.raises(ValidationError):
        SimulationHistoryResponse(items=[], total=total)
