"""Public model exports and lightweight SDK helpers."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import Generic, Literal, TypeVar

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, PrivateAttr

from protoface_sdk._generated import (
    ApiError,
    ApiErrorEnvelope,
    Avatar,
    AvatarList,
    AvatarStatus,
    ErrorType,
    LiveKitAudioSource,
    LiveKitSessionTransportConfig,
    LiveKitTransportConfig,
    PipecatSessionCreateRequest,
    PipecatTransportConfig,
    PipecatWebSocketRelayView,
    PlanView,
    QualityTier,
    SessionCreateRequest,
    SessionFailure,
    SessionStatus,
    SessionUsage,
    StatusComponent,
    StatusResponse,
    UsageSummary,
    WebSocketTransportConfig,
)

TransportConfig = LiveKitTransportConfig | WebSocketTransportConfig | PipecatTransportConfig
SessionTransportConfig = (
    LiveKitSessionTransportConfig | WebSocketTransportConfig | PipecatTransportConfig
)

PipecatRelayView = PipecatWebSocketRelayView

TERMINAL_SESSION_STATUSES: frozenset[SessionStatus] = frozenset(
    {SessionStatus.ended, SessionStatus.failed, SessionStatus.canceled}
)

T = TypeVar("T")


class Session(BaseModel):
    """Session resource with polling support for client-returned instances."""

    model_config = ConfigDict(extra="forbid")

    avatar_id: str
    created_at: AwareDatetime
    ended_at: AwareDatetime | None = None
    failed_at: AwareDatetime | None = None
    failure: SessionFailure | None = None
    first_frame_at: AwareDatetime | None = None
    id: str
    idle_timeout_seconds: int
    max_duration_seconds: int
    metadata: dict[str, str | int | float | bool | None]
    object: Literal["session"] = "session"
    quality: QualityTier
    started_at: AwareDatetime | None = None
    status: SessionStatus
    transport: SessionTransportConfig = Field(..., discriminator="type")
    usage: SessionUsage | None = None

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
        first_refresh = True
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
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(
                    f"Session {current.id} did not reach 'running' within {timeout}s "
                    f"(last status: {current.status.value})."
                )
            if first_refresh:
                first_refresh = False
            else:
                time.sleep(max(0.0, min(poll_interval, remaining)))
                if time.monotonic() >= deadline:
                    raise TimeoutError(
                        f"Session {current.id} did not reach 'running' within {timeout}s "
                        f"(last status: {current.status.value})."
                    )
            current = current._refresh()


class PipecatSessionView(BaseModel):
    model_config = ConfigDict(extra="forbid")

    object: Literal["pipecat.session"] = "pipecat.session"
    relay: PipecatWebSocketRelayView
    session: Session


class SessionList(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data: list[Session]
    has_more: bool
    next_cursor: str | None = None
    object: Literal["list"] = "list"


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
    "LiveKitSessionTransportConfig",
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
    "SessionTransportConfig",
    "SessionUsage",
    "StatusComponent",
    "StatusResponse",
    "TransportConfig",
    "UsageSummary",
    "WebSocketTransportConfig",
]
