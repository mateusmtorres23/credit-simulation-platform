import pytest

from app.errors.validation import sanitize_field_error


@pytest.mark.parametrize(
    "error_type,code",
    [
        ("missing", "REQUIRED"),
        ("extra_forbidden", "EXTRA_FIELD"),
        ("json_invalid", "INVALID_JSON"),
        ("int_type", "INVALID_TYPE"),
        ("int_parsing", "INVALID_TYPE"),
        ("int_from_float", "INVALID_TYPE"),
        ("string_type", "INVALID_TYPE"),
        ("model_type", "INVALID_TYPE"),
        ("model_attributes_type", "INVALID_TYPE"),
        ("string_too_short", "TOO_SHORT"),
        ("string_too_long", "TOO_LONG"),
        ("string_pattern_mismatch", "INVALID_FORMAT"),
        ("literal_error", "INVALID_CHOICE"),
        ("greater_than_equal", "OUT_OF_RANGE"),
        ("less_than_equal", "OUT_OF_RANGE"),
        ("uuid_parsing", "INVALID_FORMAT"),
        ("uuid_type", "INVALID_TYPE"),
        ("future_validation_error", "INVALID_VALUE"),
        (None, "INVALID_VALUE"),
    ],
)
def test_validation_codes_do_not_expose_raw_error_details(error_type, code):
    result = sanitize_field_error(
        {
            "loc": ("body", "name"),
            "type": error_type,
            "input": "private-input",
            "msg": "private-message",
            "ctx": {"error": ValueError("private-context")},
        }
    )
    assert result.field == "name"
    assert result.code == code
    assert set(result.model_dump()) == {"field", "code", "message"}
    assert "private-" not in result.model_dump_json()


@pytest.mark.parametrize(
    "location,field",
    [
        (("body", "cpf"), "cpf"),
        (("query", "page"), "page"),
        (("path", "id"), "id"),
        (["query", "bank_a_scenario"], "bank_a_scenario"),
        (("body", "private-extra-key"), "body"),
        (("body", "email", "private-nested-key"), "body"),
        (("body", 7), "body"),
        (("body",), "body"),
        (("query", "private-extra-key"), "query"),
        (("header", "authorization"), "request"),
        ((), "request"),
        (None, "request"),
        ("private-location", "request"),
    ],
)
def test_locations_expose_only_known_top_level_fields(location, field):
    result = sanitize_field_error({"loc": location, "type": "missing"})
    assert result.field == field
    assert "private-" not in result.model_dump_json()


def test_email_custom_validator_uses_controlled_message():
    result = sanitize_field_error(
        {
            "loc": ("body", "email"),
            "type": "value_error",
            "msg": "private-email@example.com",
        }
    )
    assert result.message == "Informe um e-mail válido com até 254 caracteres."
    assert "private-email" not in result.model_dump_json()


def test_unknown_validation_error_has_safe_fallback():
    assert sanitize_field_error({}).model_dump() == {
        "field": "request",
        "code": "INVALID_VALUE",
        "message": "Informe um valor válido para este campo.",
    }
