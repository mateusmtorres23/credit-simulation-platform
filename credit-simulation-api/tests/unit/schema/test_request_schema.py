import pytest
from pydantic import ValidationError

from app.schemas.request_schema import (
    SimulationCreate,
)
from app.schemas.types import MAX_SAFE_INTEGER


def test_create_trims_name_and_email_without_changing_documents(request_data):
    request_data.update(name=" \tCliente Fictício\n", email=" cliente@example.com ")
    request = SimulationCreate(**request_data)
    assert request.name == "Cliente Fictício"
    assert request.email == "cliente@example.com"
    assert request.cpf == "00000000000"
    assert request.employer_cnpj == "00000000000000"


@pytest.mark.parametrize(
    "field",
    [
        "name",
        "email",
        "cpf",
        "monthly_income_cents",
        "employer_cnpj",
        "requested_amount_cents",
        "term_months",
    ],
)
def test_every_creation_field_is_required(request_data, field):
    del request_data[field]
    with pytest.raises(ValidationError) as error:
        SimulationCreate(**request_data)
    assert error.value.errors()[0]["loc"] == (field,)


@pytest.mark.parametrize(
    "field,value",
    [
        ("name", " \t\n"),
        ("name", "a" * 151),
        ("name", 123),
        ("email", "invalid"),
        ("email", "a" * 243 + "@example.com"),
        ("email", 123),
        ("cpf", "000.000.000-00"),
        ("cpf", "0" * 10),
        ("cpf", "0" * 12),
        ("cpf", "０" * 11),
        ("cpf", "00000000000\n"),
        ("cpf", 12345678901),
        ("employer_cnpj", "00.000.000/0000-00"),
        ("employer_cnpj", "0" * 13),
        ("employer_cnpj", "0" * 15),
        ("employer_cnpj", "٠" * 14),
        ("employer_cnpj", " 00000000000000"),
        ("monthly_income_cents", 0),
        ("monthly_income_cents", MAX_SAFE_INTEGER + 1),
        ("requested_amount_cents", 99),
        ("requested_amount_cents", MAX_SAFE_INTEGER + 1),
        ("term_months", 0),
        ("term_months", 121),
    ],
)
def test_invalid_creation_fields(request_data, field, value):
    with pytest.raises(ValidationError):
        SimulationCreate(**(request_data | {field: value}))


@pytest.mark.parametrize(
    "field", ["monthly_income_cents", "requested_amount_cents", "term_months"]
)
@pytest.mark.parametrize("value", ["12", 12.0, 12.5, True, False, None])
def test_creation_numbers_are_strict_integers(request_data, field, value):
    with pytest.raises(ValidationError):
        SimulationCreate(**(request_data | {field: value}))


@pytest.mark.parametrize(
    "income,amount,term",
    [(1, 100, 1), (MAX_SAFE_INTEGER, MAX_SAFE_INTEGER, 120), (100, 100, 5)],
)
def test_creation_accepts_public_boundaries_without_bank_policy(
    request_data, income, amount, term
):
    request = SimulationCreate(
        **(
            request_data
            | {
                "monthly_income_cents": income,
                "requested_amount_cents": amount,
                "term_months": term,
            }
        )
    )
    assert (
        request.monthly_income_cents,
        request.requested_amount_cents,
        request.term_months,
    ) == (income, amount, term)


def test_name_limit_is_checked_after_trimming(request_data):
    assert (
        len(SimulationCreate(**(request_data | {"name": " " + "a" * 150 + " "})).name)
        == 150
    )


def test_extra_fields_are_rejected_and_text_errors_hide_personal_input(request_data):
    with pytest.raises(ValidationError) as error:
        SimulationCreate(**(request_data | {"unexpected": "private-test-value"}))
    assert error.value.errors()[0]["type"] == "extra_forbidden"
    assert "private-test-value" not in str(error.value)
