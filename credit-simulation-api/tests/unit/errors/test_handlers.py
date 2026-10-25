import json

import pytest
from fastapi import Request
from fastapi.exceptions import RequestValidationError

from app.errors.handlers import (
    application_exception_handler,
    request_validation_exception_handler,
)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kind,status,code",
    [
        ("save", 503, "SIMULATION_SAVE_FAILED"),
        ("missing", 404, "SIMULATION_NOT_FOUND"),
        ("history", 503, "HISTORY_UNAVAILABLE"),
        ("delete", 503, "SIMULATION_DELETE_FAILED"),
    ],
)
async def test_registered_application_errors_return_public_envelope(
    error_client, kind, status, code
):
    response = await error_client.get(f"/errors/{kind}")
    assert response.status_code == status
    assert response.headers["content-type"] == "application/json"
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message"}
    assert body["error"]["code"] == code
    assert body["error"]["message"].strip()
    assert "private-" not in response.text


@pytest.mark.asyncio
async def test_actual_pydantic_errors_are_sanitized_and_preserve_order(error_client):
    response = await error_client.post(
        "/validate",
        json={
            "name": "private-name",
            "email": "private-email",
            "cpf": "private-cpf",
            "monthly_income_cents": "private-income",
            "employer_cnpj": "private-cnpj",
            "requested_amount_cents": 99,
            "term_months": 121,
            "private-extra-key": "private-extra-value",
        },
    )
    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "VALIDATION_ERROR"
    assert error["message"] == "Revise os campos informados."
    assert [field["field"] for field in error["fields"]] == [
        "email",
        "cpf",
        "monthly_income_cents",
        "employer_cnpj",
        "requested_amount_cents",
        "term_months",
        "body",
    ]
    assert "private-" not in response.text
    assert all(set(field) == {"field", "code", "message"} for field in error["fields"])


@pytest.mark.asyncio
async def test_malformed_json_does_not_expose_body_or_parser_context(error_client):
    response = await error_client.post(
        "/validate",
        content='{"email": "private-email",',
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["fields"][0]["code"] == "INVALID_JSON"
    assert "private-email" not in response.text


@pytest.mark.asyncio
async def test_query_validation_uses_the_same_envelope(error_client):
    response = await error_client.get("/query", params={"page": "private-value"})
    assert response.status_code == 422
    assert response.json()["error"]["fields"] == [
        {
            "field": "page",
            "code": "INVALID_TYPE",
            "message": "Informe um número inteiro.",
        }
    ]
    assert "private-value" not in response.text


@pytest.mark.asyncio
async def test_empty_validation_details_receive_public_fallback():
    response = await request_validation_exception_handler(
        Request({"type": "http"}), RequestValidationError([])
    )
    assert response.status_code == 422
    assert json.loads(response.body)["error"]["fields"] == [
        {
            "field": "request",
            "code": "INVALID_VALUE",
            "message": "Envie uma solicitação válida.",
        }
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "handler", [application_exception_handler, request_validation_exception_handler]
)
async def test_handlers_do_not_disguise_unrelated_exceptions(handler):
    exc = RuntimeError("unrelated failure")
    with pytest.raises(RuntimeError) as raised:
        await handler(Request({"type": "http"}), exc)
    assert raised.value is exc
