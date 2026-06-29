"""Typed error hierarchy for the Protoface SDK.

Mirrors the TypeScript SDK's ``errors.ts``: a base :class:`ProtofaceError`
carrying the stable wire fields (``type``, ``code``, ``param``,
``request_id``, ``status``) plus one subclass per HTTP/error category. Switch
on :attr:`ProtofaceError.code` (a stable ``lower_snake_case`` string), never
on :attr:`ProtofaceError.message` (human-readable, not stable).
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

__all__ = [
    "AuthenticationError",
    "ConflictError",
    "InternalError",
    "InvalidRequestError",
    "NotFoundError",
    "PermissionError",
    "ProtofaceConnectionError",
    "ProtofaceError",
    "QuotaExceededError",
    "RateLimitError",
    "ServiceUnavailableError",
    "UnprocessableError",
    "error_from_response",
]


class ProtofaceError(Exception):
    """Base class for every error raised after a request reaches the API.

    Switch on :attr:`code` (a stable ``lower_snake_case`` string), never on
    the human-readable :attr:`message`.
    """

    #: Broad error category, e.g. ``invalid_request``, ``rate_limit``.
    type: str
    #: Stable machine-readable subcode. Switch on this.
    code: str
    #: Offending request field (dot-path), when applicable.
    param: str | None
    #: Echo of the ``X-Request-Id`` response header. Quote this to support.
    request_id: str | None
    #: HTTP status code of the response.
    status: int

    def __init__(
        self,
        message: str,
        *,
        type: str,
        code: str,
        status: int,
        param: str | None = None,
        request_id: str | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.type = type
        self.code = code
        self.param = param
        self.request_id = request_id
        self.status = status


class AuthenticationError(ProtofaceError):
    """401 — missing or invalid API key."""


class PermissionError(ProtofaceError):
    """403 — authenticated but not permitted."""


class InvalidRequestError(ProtofaceError):
    """400 — malformed request."""


class NotFoundError(ProtofaceError):
    """404 — no such resource."""


class ConflictError(ProtofaceError):
    """409 — conflicting state (e.g. avatar not ready)."""


class UnprocessableError(ProtofaceError):
    """422 — request failed validation."""


class RateLimitError(ProtofaceError):
    """429 — rate limited. Inspect :attr:`retry_after_seconds`."""

    #: Seconds to wait before retrying, from the ``Retry-After`` header.
    retry_after_seconds: float | None

    def __init__(
        self,
        message: str,
        *,
        type: str,
        code: str,
        status: int,
        param: str | None = None,
        request_id: str | None = None,
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(
            message,
            type=type,
            code=code,
            status=status,
            param=param,
            request_id=request_id,
        )
        self.retry_after_seconds = retry_after_seconds


class QuotaExceededError(ProtofaceError):
    """Quota or credit exhausted (error ``type == quota_exceeded``)."""


class InternalError(ProtofaceError):
    """5xx — server-side error."""


class ServiceUnavailableError(ProtofaceError):
    """503 — no worker capacity / temporarily unavailable.

    Honor :attr:`retry_after_seconds`.
    """

    #: Seconds to wait before retrying, from the ``Retry-After`` header.
    retry_after_seconds: float | None

    def __init__(
        self,
        message: str,
        *,
        type: str,
        code: str,
        status: int,
        param: str | None = None,
        request_id: str | None = None,
        retry_after_seconds: float | None = None,
    ) -> None:
        super().__init__(
            message,
            type=type,
            code=code,
            status=status,
            param=param,
            request_id=request_id,
        )
        self.retry_after_seconds = retry_after_seconds


class ProtofaceConnectionError(Exception):
    """Raised when a request never produced a parseable API response.

    Covers network failures, timeouts, and aborted requests — anything that
    happens before the server returns an HTTP status.
    """

    def __init__(self, message: str, cause: BaseException | None = None) -> None:
        super().__init__(message)
        self.message = message
        self.__cause__ = cause


def _is_error_envelope(body: object) -> bool:
    return isinstance(body, Mapping) and "error" in body and isinstance(body["error"], Mapping)


def _parse_retry_after(headers: Mapping[str, str]) -> float | None:
    raw = headers.get("retry-after") or headers.get("Retry-After")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def error_from_response(
    status: int,
    headers: Mapping[str, str],
    body: object,
) -> ProtofaceError:
    """Build the appropriate :class:`ProtofaceError` subclass from a non-2xx
    response. Falls back to a synthetic error when the body isn't a
    recognizable error envelope (e.g. a gateway returned HTML).
    """
    if _is_error_envelope(body):
        error: Mapping[str, Any] = body["error"]  # type: ignore[index]
        err_type = str(error.get("type", "internal" if status >= 500 else "invalid_request"))
        code = str(error.get("code", "unexpected_response"))
        message = str(error.get("message", f"Unexpected {status} response from the Protoface API."))
        param = error.get("param")
        request_id = error.get("request_id")
    else:
        err_type = "internal" if status >= 500 else "invalid_request"
        code = "unexpected_response"
        message = f"Unexpected {status} response from the Protoface API."
        param = None
        request_id = None

    param = str(param) if param is not None else None
    request_id = str(request_id) if request_id else headers.get("x-request-id") or None

    common: dict[str, Any] = {
        "type": err_type,
        "code": code,
        "status": status,
        "param": param,
        "request_id": request_id,
    }

    if status == 401:
        return AuthenticationError(message, **common)
    if status == 403:
        return PermissionError(message, **common)
    if status == 400:
        return InvalidRequestError(message, **common)
    if status == 404:
        return NotFoundError(message, **common)
    if status == 409:
        return ConflictError(message, **common)
    if status == 422:
        return UnprocessableError(message, **common)
    if status == 429:
        return RateLimitError(message, retry_after_seconds=_parse_retry_after(headers), **common)
    if status == 503:
        return ServiceUnavailableError(
            message, retry_after_seconds=_parse_retry_after(headers), **common
        )

    if err_type == "quota_exceeded":
        return QuotaExceededError(message, **common)
    if status >= 500:
        return InternalError(message, **common)
    return ProtofaceError(message, **common)
