from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

ErrorText = Annotated[str, StringConstraints(strict=True, min_length=1, pattern=r"\S")]
ApplicationErrorCode = Literal[
    "SIMULATION_SAVE_FAILED",
    "SIMULATION_NOT_FOUND",
    "HISTORY_UNAVAILABLE",
    "SIMULATION_DELETE_FAILED",
]


class ErrorSchema(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class FieldError(ErrorSchema):
    field: ErrorText
    code: ErrorText
    message: ErrorText


class ApplicationError(ErrorSchema):
    code: ApplicationErrorCode
    message: ErrorText


class ValidationErrorDetail(ErrorSchema):
    code: Literal["VALIDATION_ERROR"]
    message: ErrorText
    fields: Annotated[list[FieldError], Field(min_length=1)]


class ErrorResponse(ErrorSchema):
    error: Annotated[
        ApplicationError | ValidationErrorDetail, Field(discriminator="code")
    ]
