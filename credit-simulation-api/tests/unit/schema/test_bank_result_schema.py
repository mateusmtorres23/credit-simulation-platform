import pytest
from pydantic import TypeAdapter, ValidationError

from app.models.enums import RejectionCode
from app.schemas.bank_result_schema import (
    ApprovedBankResult,
    BankError,
    BankOffer,
    BankResult,
    FailedBankResult,
    RejectedBankResult,
    RejectionReason,
)
from app.schemas.types import MAX_SAFE_INTEGER


@pytest.mark.parametrize(
    "field,low,high",
    [
        ("amount_cents", 1, MAX_SAFE_INTEGER),
        ("term_months", 1, 120),
        ("monthly_interest_rate_bps", 0, MAX_SAFE_INTEGER),
        ("installment_cents", 1, MAX_SAFE_INTEGER),
    ],
)
def test_offer_boundaries(offer_data, field, low, high):
    for valid in (low, high):
        assert getattr(BankOffer(**(offer_data | {field: valid})), field) == valid
    for invalid in (low - 1, high + 1):
        with pytest.raises(ValidationError):
            BankOffer(**(offer_data | {field: invalid}))


@pytest.mark.parametrize(
    "field",
    ["amount_cents", "term_months", "monthly_interest_rate_bps", "installment_cents"],
)
@pytest.mark.parametrize("value", ["12", 12.0, True, None])
def test_offer_numbers_reject_coercion(offer_data, field, value):
    with pytest.raises(ValidationError):
        BankOffer(**(offer_data | {field: value}))


@pytest.mark.parametrize(
    "status,expected",
    [
        ("approved", ApprovedBankResult),
        ("rejected", RejectedBankResult),
        ("failed", FailedBankResult),
    ],
)
def test_result_discriminator_preserves_only_state_fields(
    bank_result, status, expected
):
    data = bank_result(status=status)
    result = TypeAdapter(BankResult).validate_python(data)
    assert isinstance(result, expected)
    assert result.model_dump(mode="json") == data


@pytest.mark.parametrize(
    "status,extra",
    [
        ("approved", {"error": {"code": "TIMEOUT", "message": "Timeout"}}),
        ("approved", {"reasons": []}),
        ("rejected", {"offer": {}}),
        ("rejected", {"error": {}}),
        ("failed", {"offer": {}}),
        ("failed", {"reasons": []}),
    ],
)
def test_result_states_reject_incompatible_fields(bank_result, status, extra):
    with pytest.raises(ValidationError):
        TypeAdapter(BankResult).validate_python(bank_result(status=status) | extra)


@pytest.mark.parametrize(
    "status,required",
    [("approved", "offer"), ("rejected", "reasons"), ("failed", "error")],
)
def test_result_requires_its_state_payload(bank_result, status, required):
    data = bank_result(status=status)
    del data[required]
    with pytest.raises(ValidationError):
        TypeAdapter(BankResult).validate_python(data)


@pytest.mark.parametrize(
    "changes", [{"status": "pending"}, {"bank": "bank_c"}, {"status": None}]
)
def test_unknown_bank_or_status_is_rejected(bank_result, changes):
    with pytest.raises(ValidationError):
        TypeAdapter(BankResult).validate_python(bank_result() | changes)


@pytest.mark.parametrize(
    "schema,code", [(BankError, "TIMEOUT"), (RejectionReason, "TERM_NOT_SUPPORTED")]
)
@pytest.mark.parametrize("message", ["", " \t\r\n", "\u00a0", None, 123])
def test_messages_require_nonblank_text(schema, code, message):
    with pytest.raises(ValidationError):
        schema(code=code, message=message)


def test_rejection_reasons_are_required_unique_and_keep_order():
    first = {"code": "TERM_NOT_SUPPORTED", "message": "Prazo não oferecido."}
    second = {"code": "INCOME_BELOW_MINIMUM", "message": "Renda abaixo do mínimo."}
    data = {"bank": "bank_a", "status": "rejected"}
    for invalid in ([], [first, first]):
        with pytest.raises(ValidationError):
            RejectedBankResult(**data, reasons=invalid)
    saved = RejectedBankResult(**data, reasons=[first, second])
    assert [reason.code for reason in saved.reasons] == [
        RejectionCode.TERM_NOT_SUPPORTED,
        RejectionCode.INCOME_BELOW_MINIMUM,
    ]


@pytest.mark.parametrize(
    "schema,code", [(BankError, "LOW_INCOME"), (RejectionReason, "TIMEOUT")]
)
def test_rejection_and_error_codes_have_separate_domains(schema, code):
    with pytest.raises(ValidationError):
        schema(code=code, message="Mensagem fictícia.")
