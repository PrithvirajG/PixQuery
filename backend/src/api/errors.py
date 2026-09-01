"""Standardized API error responses.

Every failed request — whether raised deliberately as an ``HTTPException``,
produced by request validation, or an unexpected crash — is rendered as the
same four-key JSON envelope so the frontend can rely on one shape:

    {
        "error":   true,                       # always true; lets clients branch on it
        "code":    "not_found",                # machine-readable, derived from status
        "message": "Workspace not found",      # user-facing text, propagated from the backend
        "status":  404                         # HTTP status code, mirrored in the body
    }

The ``message`` is what gets shown to the user, so route/service code should
raise ``HTTPException`` (or :class:`APIError`) with a clear, human sentence in
``detail``. Unexpected 500s never leak internals — they log server-side and
return a generic message.
"""
from __future__ import annotations

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.logging_config import get_logger

logger = get_logger(__name__)

# Machine-readable code for each HTTP status we emit.
_STATUS_CODES: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    413: "payload_too_large",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
    502: "upstream_error",
    503: "service_unavailable",
}

# User-facing fallback when a raiser didn't supply its own message.
_DEFAULT_MESSAGES: dict[int, str] = {
    400: "The request was invalid.",
    401: "You need to sign in to do that.",
    403: "You don't have permission to do that.",
    404: "We couldn't find what you were looking for.",
    409: "That conflicts with something that already exists.",
    422: "Some of the information you provided is invalid.",
    500: "Something went wrong on our end. Please try again.",
}


class APIError(Exception):
    """Raise this for a deliberate error with an explicit machine code.

    ``HTTPException(status_code=…, detail="…")`` is still the common path and is
    normalized into the same envelope; reach for ``APIError`` only when you want
    to pin the ``code`` (e.g. ``"workspace_no_pipelines"``) rather than let it be
    derived from the status.
    """

    def __init__(self, status_code: int, message: str, code: str | None = None):
        self.status_code = status_code
        self.message = message
        self.code = code or _code_for(status_code)
        super().__init__(message)


def _code_for(status_code: int) -> str:
    return _STATUS_CODES.get(status_code, "error")


def _envelope(
    status_code: int,
    message: str,
    code: str | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        headers=headers,
        content={
            "error": True,
            "code": code or _code_for(status_code),
            "message": message,
            "status": status_code,
        },
    )


def _validation_message(errors: list[dict]) -> str:
    """Turn Pydantic's error list into one readable sentence."""
    if not errors:
        return _DEFAULT_MESSAGES[422]
    first = errors[0]
    # Drop the request-part prefix ("body"/"query"/"path") from the field path.
    loc = [str(p) for p in first.get("loc", []) if p not in ("body", "query", "path")]
    field = ".".join(loc) if loc else "input"
    msg = first.get("msg", "is invalid")
    suffix = f" (and {len(errors) - 1} more)" if len(errors) > 1 else ""
    return f"{field}: {msg}{suffix}"


async def _http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    detail = exc.detail
    code: str | None = None
    if isinstance(detail, dict):
        # Supports HTTPException(detail={"code": ..., "message": ...}).
        message = detail.get("message") or _DEFAULT_MESSAGES.get(exc.status_code, "Request failed.")
        code = detail.get("code")
    elif isinstance(detail, str) and detail.strip():
        message = detail
    else:
        message = _DEFAULT_MESSAGES.get(exc.status_code, "Request failed.")
    return _envelope(exc.status_code, message, code, headers=getattr(exc, "headers", None))


async def _api_error_handler(request: Request, exc: APIError) -> JSONResponse:
    return _envelope(exc.status_code, exc.message, exc.code)


async def _validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return _envelope(
        status.HTTP_422_UNPROCESSABLE_ENTITY,
        _validation_message(exc.errors()),
        "validation_error",
    )


async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Never surface internal details to the client; log the real cause instead.
    logger.exception("Unhandled error on %s %s", request.method, request.url.path)
    return _envelope(
        status.HTTP_500_INTERNAL_SERVER_ERROR,
        _DEFAULT_MESSAGES[500],
        "internal_error",
    )


def register_error_handlers(app: FastAPI) -> None:
    """Wire the standardized handlers onto the app.

    ``fastapi.HTTPException`` subclasses the Starlette one, so a single handler
    covers both deliberate raises and framework-raised HTTP errors.
    """
    app.add_exception_handler(APIError, _api_error_handler)
    app.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    app.add_exception_handler(RequestValidationError, _validation_exception_handler)
    app.add_exception_handler(Exception, _unhandled_exception_handler)
