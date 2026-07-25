"""Standardized error responses.

Every error the API returns has the shape:
    {"error": {"type": "...", "message": "..."}}

Internal details (stack traces, raw upstream response bodies/exception
text) are never included in a response body -- they are logged
server-side only.
"""
import logging

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("hermes.backend")


class BackendError(Exception):
    """Base class for errors that map directly to a clean client response."""

    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
    error_type = "internal_error"
    default_message = "An unexpected error occurred."

    def __init__(self, message: str | None = None):
        self.message = message or self.default_message
        super().__init__(self.message)


class UpstreamTimeoutError(BackendError):
    status_code = status.HTTP_504_GATEWAY_TIMEOUT
    error_type = "upstream_timeout"
    default_message = "Timed out waiting for a response from LM Studio."


class UpstreamUnavailableError(BackendError):
    status_code = status.HTTP_502_BAD_GATEWAY
    error_type = "upstream_unavailable"
    default_message = "LM Studio is unreachable."


class UpstreamError(BackendError):
    """LM Studio responded, but with a non-2xx status or an unparseable body."""

    status_code = status.HTTP_502_BAD_GATEWAY
    error_type = "upstream_error"
    default_message = "LM Studio returned an error."


def _error_body(error_type: str, message: str) -> dict:
    return {"error": {"type": error_type, "message": message}}


async def backend_error_handler(request: Request, exc: BackendError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(exc.error_type, exc.message),
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_error_body("invalid_request", "The request payload is invalid."),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    logger.exception("Unhandled exception (request_id=%s)", request_id)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_body("internal_error", "An unexpected error occurred."),
    )
