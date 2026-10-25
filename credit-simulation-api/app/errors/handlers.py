from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.errors.exceptions import ApplicationException
from app.errors.validation import sanitize_field_error
from app.schemas.error_schema import (
    ApplicationError,
    ErrorResponse,
    FieldError,
    ValidationErrorDetail,
)


async def application_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    if not isinstance(exc, ApplicationException):
        raise exc
    response = ErrorResponse(error=ApplicationError(code=exc.code, message=exc.message))
    return JSONResponse(
        status_code=exc.status_code, content=response.model_dump(mode="json")
    )


async def request_validation_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc
    fields = [sanitize_field_error(error) for error in exc.errors()]
    if not fields:
        fields = [
            FieldError(
                field="request",
                code="INVALID_VALUE",
                message="Envie uma solicitação válida.",
            )
        ]
    response = ErrorResponse(
        error=ValidationErrorDetail(
            code="VALIDATION_ERROR",
            message="Revise os campos informados.",
            fields=fields,
        )
    )
    return JSONResponse(status_code=422, content=response.model_dump(mode="json"))


def register_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(ApplicationException, application_exception_handler)
    app.add_exception_handler(
        RequestValidationError, request_validation_exception_handler
    )
