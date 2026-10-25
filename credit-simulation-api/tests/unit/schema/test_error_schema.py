import pytest
from pydantic import ValidationError

from app.schemas.error_schema import (
    ApplicationError,
    ErrorResponse,
    FieldError,
    ValidationErrorDetail,
)


@pytest.mark.parametrize(
    "code",
    [
        "SIMULATION_SAVE_FAILED",
        "SIMULATION_NOT_FOUND",
        "HISTORY_UNAVAILABLE",
        "SIMULATION_DELETE_FAILED",
        "REQUEST_FORBIDDEN",
    ],
)
def test_application_errors_use_the_approved_envelope(code):
    data = {"error": {"code": code, "message": "Mensagem pública."}}
    response = ErrorResponse.model_validate(data)
    assert isinstance(response.error, ApplicationError)
    assert response.model_dump(mode="json") == data
    assert ErrorResponse.model_validate_json(response.model_dump_json()) == response


def test_validation_error_preserves_field_order_and_public_structure():
    fields = [
        {
            "field": "term_months",
            "code": "OUT_OF_RANGE",
            "message": "Informe um prazo entre 1 e 120 meses.",
        },
        {
            "field": "email",
            "code": "INVALID_FORMAT",
            "message": "Informe um e-mail válido.",
        },
    ]
    data = {
        "error": {
            "code": "VALIDATION_ERROR",
            "message": "Revise os campos informados.",
            "fields": fields,
        }
    }
    response = ErrorResponse.model_validate(data)
    assert isinstance(response.error, ValidationErrorDetail)
    assert response.model_dump(mode="json") == data


@pytest.mark.parametrize("fields", [None, []])
def test_validation_error_requires_nonempty_fields(fields):
    with pytest.raises(ValidationError):
        ValidationErrorDetail(
            code="VALIDATION_ERROR", message="Revise os campos.", fields=fields
        )


def test_validation_error_cannot_omit_fields():
    with pytest.raises(ValidationError):
        ErrorResponse(
            error={"code": "VALIDATION_ERROR", "message": "Revise os campos."}
        )


def test_application_error_cannot_include_validation_fields():
    with pytest.raises(ValidationError):
        ErrorResponse(
            error={
                "code": "SIMULATION_SAVE_FAILED",
                "message": "Falha ao salvar.",
                "fields": [],
            }
        )


@pytest.mark.parametrize("code", ["TIMEOUT", "UNKNOWN_ERROR", "", None])
def test_unknown_or_bank_error_codes_are_not_application_errors(code):
    with pytest.raises(ValidationError):
        ErrorResponse(error={"code": code, "message": "Mensagem fictícia."})


@pytest.mark.parametrize("field", ["field", "code", "message"])
@pytest.mark.parametrize("value", ["", " \t\r\n", "\u00a0", 123, None])
def test_field_error_requires_nonblank_strings(field, value):
    data = {
        "field": "term_months",
        "code": "OUT_OF_RANGE",
        "message": "Revise o prazo.",
    }
    with pytest.raises(ValidationError):
        FieldError(**(data | {field: value}))


@pytest.mark.parametrize("value", ["", " \t\n", None, 123])
def test_application_message_requires_nonblank_text(value):
    with pytest.raises(ValidationError):
        ApplicationError(code="HISTORY_UNAVAILABLE", message=value)


@pytest.mark.parametrize("field", ["field", "code", "message"])
def test_all_field_error_attributes_are_required(field):
    data = {"field": "email", "code": "INVALID_FORMAT", "message": "Revise o e-mail."}
    del data[field]
    with pytest.raises(ValidationError):
        FieldError(**data)


@pytest.mark.parametrize("extra", ["input", "ctx", "value"])
def test_field_errors_reject_raw_validation_data(extra):
    with pytest.raises(ValidationError) as error:
        FieldError(
            field="email",
            code="INVALID_FORMAT",
            message="Revise o e-mail.",
            **{extra: "private-test-value"},
        )
    assert error.value.errors()[0]["type"] == "extra_forbidden"
    assert "private-test-value" not in str(error.value)


def test_envelope_rejects_missing_error_or_extra_results():
    for data in (
        {},
        {
            "error": {"code": "SIMULATION_SAVE_FAILED", "message": "Falha ao salvar."},
            "results": [],
        },
    ):
        with pytest.raises(ValidationError):
            ErrorResponse.model_validate(data)
