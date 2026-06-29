"""Public, ergonomically-named re-exports of the OpenAPI-generated models.

The underlying models in :mod:`protoface_sdk._generated` are produced by
``datamodel-code-generator`` from ``apispec/openapi.json`` (run
``make generate``). Never edit the generated file by hand; edit the spec and
regenerate. This module gives those models stable public names, adds the
hand-written :class:`Page` pagination wrapper, and extends ``Session`` with
the Python-first :meth:`Session.wait_until_running` convenience.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Generic, TypeVar

from pydantic import BaseModel, PrivateAttr

from protoface_sdk._generated import (
    ApiError,
    ApiErrorEnvelope,
    Avatar,
    AvatarList,
    AvatarStatus,
    ErrorType,
    LiveKitAudioSource,
    LiveKitTransportConfig,
    PipecatSessionCreateRequest,
    PipecatSessionView,
    PipecatTransportConfig,
    PipecatWebSocketRelayView,
    PlanView,
    QualityTier,
    SessionCreateRequest,
    SessionFailure,
    SessionList,
    SessionStatus,
    SessionUsage,
    StatusComponent,
    StatusResponse,
    UsageSummary,
    WebSocketTransportConfig,
)
from protoface_sdk._generated import (
    Session as _GeneratedSession,
)

#: Transport configs accepted/echoed on the public API, keyed by ``type``.
TransportConfig = LiveKitTransportConfig | WebSocketTransportConfig | PipecatTransportConfig

#: Relay details returned by ``POST /v1/pipecat/sessions``.
PipecatRelayView = PipecatWebSocketRelayView

#: Terminal session statuses — no further transitions occur.
TERMINAL_SESSION_STATUSES: frozenset[SessionStatus] = frozenset(
    {SessionStatus.ended, SessionStatus.failed, SessionStatus.canceled}
)

T = TypeVar("T")


class Session(_GeneratedSession):
    """Public session resource with a polling convenience.

    Instances returned by the client carry a bound refresher so
    :meth:`wait_until_running` can re-fetch the session. Instances you
    construct yourself (e.g. in tests) won't have one until the client
    returns them.
    """

    _refresh: Callable[[], Session] | None = PrivateAttr(default=None)

    def _bind(self, refresh: Callable[[], Session]) -> Session:
        self._refresh = refresh
        return self

    def wait_until_running(
        self,
        *,
        timeout: float = 30.0,
        poll_interval: float = 1.0,
    ) -> Session:
        """Poll :meth:`SessionsResource.get` until the session is ``running``
        (or reaches a terminal state), then return the latest snapshot.

        Raises :class:`TimeoutError` if ``timeout`` seconds elapse first.
        """
        current: Session = self
        deadline = time.monotonic() + timeout
        while True:
            if current.status == SessionStatus.running:
                return current
            if current.status in TERMINAL_SESSION_STATUSES:
                return current
            if current._refresh is None:
                raise RuntimeError("wait_until_running requires a Session returned by the client.")
            if time.monotonic() >= deadline:
                raise TimeoutError(
                    f"Session {current.id} did not reach 'running' within {timeout}s "
                    f"(last status: {current.status.value})."
                )
            time.sleep(poll_interval)
            current = current._refresh()


class Page(BaseModel, Generic[T]):
    """A single cursor-paginated page of results."""

    #: Items on this page.
    data: list[T]
    #: True when another page exists.
    has_more: bool
    #: Opaque cursor; pass as ``starting_after`` to fetch the next page.
    next_cursor: str | None = None


__all__ = [
    "TERMINAL_SESSION_STATUSES",
    "ApiError",
    "ApiErrorEnvelope",
    "Avatar",
    "AvatarList",
    "AvatarStatus",
    "ErrorType",
    "LiveKitAudioSource",
    "LiveKitTransportConfig",
    "Page",
    "PipecatRelayView",
    "PipecatSessionCreateRequest",
    "PipecatSessionView",
    "PipecatTransportConfig",
    "PipecatWebSocketRelayView",
    "PlanView",
    "QualityTier",
    "Session",
    "SessionCreateRequest",
    "SessionFailure",
    "SessionList",
    "SessionStatus",
    "SessionUsage",
    "StatusComponent",
    "StatusResponse",
    "TransportConfig",
    "UsageSummary",
    "WebSocketTransportConfig",
]
