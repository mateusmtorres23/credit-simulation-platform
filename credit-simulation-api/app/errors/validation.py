from collections.abc import Mapping

from app.schemas.error_schema import FieldError

PUBLIC_FIELDS = frozenset(
    {
        "name",
        "email",
        "cpf",
        "employer_cnpj",
        "monthly_income_cents",
        "requested_amount_cents",
        "term_months",
        "bank_a_scenario",
        "bank_b_scenario",
        "page",
        "page_size",
        "id",
    }
)

VALIDATION_MESSAGES = {
    "missing": ("REQUIRED", "Informe este campo obrigatório."),
    "extra_forbidden": ("EXTRA_FIELD", "Remova os campos não permitidos."),
    "json_invalid": ("INVALID_JSON", "Envie um corpo JSON válido."),
    "int_type": ("INVALID_TYPE", "Informe um número inteiro."),
    "int_parsing": ("INVALID_TYPE", "Informe um número inteiro."),
    "int_from_float": ("INVALID_TYPE", "Informe um número inteiro."),
    "string_type": ("INVALID_TYPE", "Informe um texto."),
    "model_attributes_type": ("INVALID_TYPE", "Envie um objeto JSON."),
    "model_type": ("INVALID_TYPE", "Envie um objeto JSON."),
    "string_too_short": ("TOO_SHORT", "Informe um texto com conteúdo válido."),
    "string_too_long": ("TOO_LONG", "O texto excede o tamanho permitido."),
    "string_pattern_mismatch": ("INVALID_FORMAT", "Informe o formato esperado."),
    "literal_error": ("INVALID_CHOICE", "Escolha normal, slow ou unavailable."),
    "greater_than_equal": (
        "OUT_OF_RANGE",
        "Informe um valor dentro dos limites permitidos.",
    ),
    "less_than_equal": (
        "OUT_OF_RANGE",
        "Informe um valor dentro dos limites permitidos.",
    ),
    "uuid_parsing": ("INVALID_FORMAT", "Informe um identificador UUID válido."),
    "uuid_type": ("INVALID_TYPE", "Informe um identificador UUID válido."),
}


def sanitize_field_error(error: Mapping[str, object]) -> FieldError:
    # Extra keys may contain secrets; only known field names can be returned.
    location = error.get("loc", ())
    field = "request"
    if isinstance(location, (tuple, list)) and location:
        root = location[0]
        if isinstance(root, str) and root in ("body", "query", "path"):
            field = root
            if (
                len(location) == 2
                and isinstance(location[1], str)
                and location[1] in PUBLIC_FIELDS
            ):
                field = location[1]

    error_type = error.get("type")
    code, message = VALIDATION_MESSAGES.get(
        error_type if isinstance(error_type, str) else "",
        ("INVALID_VALUE", "Informe um valor válido para este campo."),
    )
    if field == "email" and error_type == "value_error":
        message = "Informe um e-mail válido com até 254 caracteres."
    return FieldError(field=field, code=code, message=message)
