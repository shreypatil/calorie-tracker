"""Application error hierarchy and its mapping to RFC 9457 problem responses.

Routes raise these; they never build an error body by hand. One handler per
exception type turns them into `application/problem+json`, so every error the
API emits has the same shape and carries the request ID for correlation.
"""

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import LogEvent, get_request_id, logger

PROBLEM_CONTENT_TYPE = "application/problem+json"


class AppError(Exception):
    """Base class for errors the application raises deliberately."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    title: str = "Internal Server Error"
    error_type: str = "about:blank"

    def __init__(self, detail: str, errors: list[dict[str, Any]] | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.errors = errors or []


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    title = "Not Found"
    error_type = "/errors/not-found"


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    title = "Forbidden"
    error_type = "/errors/forbidden"


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    title = "Unauthorized"
    error_type = "/errors/unauthorized"


class ValidationError(AppError):
    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    title = "Validation Failed"
    error_type = "/errors/validation-failed"


class ConflictError(AppError):
    status_code = status.HTTP_409_CONFLICT
    title = "Conflict"
    error_type = "/errors/conflict"


class ExternalServiceError(AppError):
    status_code = status.HTTP_502_BAD_GATEWAY
    title = "External Service Error"
    error_type = "/errors/external-service"


class UpstreamRateLimitError(AppError):
    """The AI provider refused because a quota or rate limit was reached.

    Distinct from a 502: nothing is broken and retrying later will work, which
    is a materially different thing to tell the user.
    """

    status_code = status.HTTP_429_TOO_MANY_REQUESTS
    title = "AI Provider Limit Reached"
    error_type = "/errors/upstream-rate-limit"


class PayloadTooLargeError(AppError):
    status_code = status.HTTP_413_CONTENT_TOO_LARGE
    title = "Payload Too Large"
    error_type = "/errors/payload-too-large"


def _problem(
    *,
    status_code: int,
    title: str,
    detail: str,
    error_type: str = "about:blank",
    errors: list[dict[str, Any]] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        media_type=PROBLEM_CONTENT_TYPE,
        content={
            "type": error_type,
            "title": title,
            "status": status_code,
            "detail": detail,
            "errors": errors or [],
            "request_id": get_request_id(),
        },
    )


def _log_failure(request: Request, *, status_code: int, **fields: Any) -> None:
    """Record an error response.

    Every error the API returns passes through one of these handlers, so logging here covers all of
    them without a single route knowing about it. Client errors are expected outcomes and log at
    WARNING; anything 5xx is a defect and logs at ERROR.

    The limitation worth remembering: an error that is *caught and handled* never reaches a handler
    and so is never logged here. Those call sites have to speak for themselves — see
    `services/chat/agent.py`, where a swallowed validation failure once left no trace at all.
    """
    logger.log(
        logging.WARNING if status_code < 500 else logging.ERROR,
        "request_failed",
        extra={
            "event": LogEvent.REQUEST_FAILED,
            "status_code": status_code,
            "method": request.method,
            "path": request.url.path,
            **fields,
        },
    )


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(request: Request, exc: AppError) -> JSONResponse:
        _log_failure(
            request,
            status_code=exc.status_code,
            error_type=exc.error_type,
            detail=exc.detail,
            errors=exc.errors or None,
        )
        return _problem(
            status_code=exc.status_code,
            title=exc.title,
            detail=exc.detail,
            error_type=exc.error_type,
            errors=exc.errors,
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_request_validation(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = [
            {
                "field": ".".join(str(part) for part in err["loc"][1:]) or str(err["loc"][0]),
                "message": err["msg"],
                "type": err["type"],
            }
            for err in exc.errors()
        ]
        # The field list is the whole story for a 422; without it the log says only "validation
        # failed", which is precisely as useful as the status code alone.
        _log_failure(
            request,
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            error_type="/errors/validation-failed",
            detail="The request body or parameters failed validation.",
            errors=errors,
        )
        return _problem(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            title="Validation Failed",
            detail="The request body or parameters failed validation.",
            error_type="/errors/validation-failed",
            errors=errors,
        )

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        _log_failure(request, status_code=exc.status_code, detail=str(exc.detail))
        return _problem(
            status_code=exc.status_code,
            title=str(exc.detail),
            detail=str(exc.detail),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        # Log the real cause, return a generic message: internals never leak.
        logger.exception("unhandled_exception", extra={"error": str(exc)})
        return _problem(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            title="Internal Server Error",
            detail="An unexpected error occurred. The request ID can be used to trace it.",
        )
