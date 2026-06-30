"""Public model exports and lightweight SDK helpers."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, PrivateAttr

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

TransportConfig = LiveKitTransportConfig | WebSocketTransportConfig | PipecatTransportConfig

PipecatRelayView = PipecatWebSocketRelayView

TERMINAL_SESSION_STATUSES: frozenset[SessionStatus] = frozenset(
    {SessionStatus.ended, SessionStatus.failed, SessionStatus.canceled}
)

T = TypeVar("T")


class Session(_GeneratedSession):
    """Session resource with polling support for client-returned instances."""

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
        """Poll until the session is ``running`` or no longer starting.

        Raises :class:`TimeoutError` if ``timeout`` seconds elapse first.
        """
        current: Session = self
        deadline = time.monotonic() + timeout
        while True:
            if current.status == SessionStatus.running:
                return current
            if (
                current.status == SessionStatus.ending
                or current.status in TERMINAL_SESSION_STATUSES
            ):
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


class PipecatSessionView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object: Literal["pipecat.session"] = "pipecat.session"
    relay: PipecatWebSocketRelayView
    session: Session


class Page(BaseModel, Generic[T]):
    """A single cursor-paginated page of results."""

    data: list[T]
    has_more: bool
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
