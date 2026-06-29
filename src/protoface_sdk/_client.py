"""Synchronous ``httpx``-based client for the Protoface API.

The ergonomic layer is hand-written against the committed OpenAPI spec; the
wire models live in :mod:`protoface_sdk._generated`.
"""

from __future__ import annotations

import random
import time
from collections.abc import Mapping, Sequence
from typing import Any

import httpx

from protoface_sdk.errors import (
    ProtofaceConnectionError,
    RateLimitError,
    ServiceUnavailableError,
    error_from_response,
)
from protoface_sdk.models import (
    Avatar,
    Page,
    PipecatSessionView,
    PlanView,
    QualityTier,
    Session,
    SessionCreateRequest,
    StatusResponse,
    TransportConfig,
    UsageSummary,
)

#: Default base URL for the public API.
DEFAULT_BASE_URL = "https://api.protoface.com"

_RETRYABLE_STATUSES = frozenset({429, 503})

# Bytes-like image payloads accepted by ``avatars.create``.
ImageInput = bytes | bytearray | memoryview


def _clean_params(
    params: Mapping[str, str | int | Sequence[str] | None],
) -> dict[str, Any]:
    """Drop ``None`` values so they don't appear as empty query args."""
    return {key: value for key, value in params.items() if value is not None}


class ProtofaceClient:
    """Thin, typed client for the Protoface API.

    Example::

        from protoface_sdk import ProtofaceClient

        client = ProtofaceClient(api_key=os.environ["PROTOFACE_API_KEY"])
        session = client.sessions.create_livekit(
            avatar_id="av_stock_001",
            url=os.environ["LIVEKIT_URL"],
            room_name="demo-room",
            worker_token=worker_token,
        )
        session.wait_until_running(timeout=10)
    """

    sessions: SessionsResource
    avatars: AvatarsResource
    pipecat: PipecatResource
    usage: UsageResource

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 60.0,
        max_retries: int = 2,
        default_headers: Mapping[str, str] | None = None,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        if not api_key:
            raise ValueError("ProtofaceClient requires an `api_key`.")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._max_retries = max_retries
        headers = {
            "accept": "application/json",
            "authorization": f"Bearer {api_key}",
            "user-agent": "protoface-sdk/0.1.0",
        }
        if default_headers:
            headers.update(default_headers)
        self._http = httpx.Client(
            base_url=self._base_url,
            headers=headers,
            timeout=timeout,
            transport=transport,
        )

        self.sessions = SessionsResource(self)
        self.avatars = AvatarsResource(self)
        self.pipecat = PipecatResource(self)
        self.usage = UsageResource(self)

    # -- context management ------------------------------------------------

    def __enter__(self) -> ProtofaceClient:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()

    def close(self) -> None:
        """Close the underlying HTTP connection pool."""
        self._http.close()

    # -- public endpoints --------------------------------------------------

    def get_status(self) -> StatusResponse:
        """Public platform status roll-up (unauthenticated endpoint)."""
        return StatusResponse.model_validate(self.request("GET", "/v1/status"))

    def list_billing_plans(self) -> list[PlanView]:
        """Current public billing plan catalog."""
        payload = self.request("GET", "/v1/billing/plans")
        return [PlanView.model_validate(item) for item in payload]

    # -- transport ---------------------------------------------------------

    def _backoff_seconds(self, attempt: int) -> float:
        base = min(2.0**attempt, 8.0)
        return base + random.uniform(0, 0.25)

    def request(
        self,
        method: str,
        path: str,
        *,
        params: Mapping[str, str | int | Sequence[str] | None] | None = None,
        json_body: Any | None = None,
        files: Mapping[str, Any] | None = None,
        data: Mapping[str, str] | None = None,
        idempotency_key: str | None = None,
    ) -> Any:
        """Perform a single request with timeout + retry handling.

        Intended for internal use by the resource classes; returns the parsed
        JSON body, or ``None`` for ``204`` responses.
        """
        query = _clean_params(params) if params else None
        headers: dict[str, str] = {}
        if idempotency_key:
            headers["idempotency-key"] = idempotency_key

        attempt = 0
        while True:
            try:
                response = self._http.request(
                    method,
                    path,
                    params=query,
                    json=json_body,
                    files=files,
                    data=data,
                    headers=headers,
                )
            except httpx.RequestError as exc:
                if attempt < self._max_retries:
                    time.sleep(self._backoff_seconds(attempt))
                    attempt += 1
                    continue
                raise ProtofaceConnectionError(f"Request to {path} failed: {exc}", exc) from exc

            if response.is_success:
                if response.status_code == 204 or not response.content:
                    return None
                return response.json()

            body = self._safe_json(response)
            error = error_from_response(response.status_code, response.headers, body)

            if (
                response.status_code in _RETRYABLE_STATUSES
                and attempt < self._max_retries
                and isinstance(error, RateLimitError | ServiceUnavailableError)
            ):
                retry_after = error.retry_after_seconds
                wait = retry_after if retry_after is not None else self._backoff_seconds(attempt)
                time.sleep(wait)
                attempt += 1
                continue
            raise error

    @staticmethod
    def _safe_json(response: httpx.Response) -> object:
        try:
            return response.json()
        except ValueError:
            return None


class SessionsResource:
    """``client.sessions`` — create, retrieve, list, and end sessions."""

    def __init__(self, client: ProtofaceClient) -> None:
        self._client = client

    def _parse(self, payload: Any) -> Session:
        session = Session.model_validate(payload)
        session_id = session.id
        # `_bind` is the documented internal hook for wiring up the refresher.
        return session._bind(lambda: self.get(session_id))  # pyright: ignore[reportPrivateUsage]

    def create(
        self,
        request: SessionCreateRequest | Mapping[str, Any],
        *,
        idempotency_key: str | None = None,
    ) -> Session:
        """Create a session. Returns immediately with ``status: queued``."""
        body = (
            request.model_dump(mode="json", exclude_none=True)
            if isinstance(request, SessionCreateRequest)
            else dict(request)
        )
        return self._parse(
            self._client.request(
                "POST", "/v1/sessions", json_body=body, idempotency_key=idempotency_key
            )
        )

    def create_livekit(
        self,
        *,
        avatar_id: str,
        url: str,
        room_name: str,
        worker_token: str,
        audio_source: str | None = None,
        quality: QualityTier | str | None = None,
        max_duration_seconds: int | None = None,
        idle_timeout_seconds: int | None = None,
        metadata: Mapping[str, str | int | float | bool | None] | None = None,
        idempotency_key: str | None = None,
    ) -> Session:
        """Convenience wrapper for the LiveKit BYO-transport path.

        The customer mints ``worker_token`` with their own LiveKit API
        key/secret; the SDK never touches LiveKit credentials.
        """
        transport: dict[str, Any] = {
            "type": "livekit",
            "url": url,
            "room_name": room_name,
            "worker_token": worker_token,
        }
        if audio_source is not None:
            transport["audio_source"] = audio_source

        body: dict[str, Any] = {"avatar_id": avatar_id, "transport": transport}
        if quality is not None:
            body["quality"] = quality.value if isinstance(quality, QualityTier) else quality
        if max_duration_seconds is not None:
            body["max_duration_seconds"] = max_duration_seconds
        if idle_timeout_seconds is not None:
            body["idle_timeout_seconds"] = idle_timeout_seconds
        if metadata is not None:
            body["metadata"] = dict(metadata)

        return self.create(body, idempotency_key=idempotency_key)

    def get(self, session_id: str) -> Session:
        """Retrieve a session by id."""
        return self._parse(self._client.request("GET", f"/v1/sessions/{session_id}"))

    def list(
        self,
        *,
        status: Sequence[str] | None = None,
        avatar_id: str | None = None,
        created_after: str | None = None,
        created_before: str | None = None,
        limit: int | None = None,
        starting_after: str | None = None,
    ) -> Page[Session]:
        """List sessions for the calling org, newest first."""
        payload = self._client.request(
            "GET",
            "/v1/sessions",
            params={
                "status": list(status) if status is not None else None,
                "avatar_id": avatar_id,
                "created_after": created_after,
                "created_before": created_before,
                "limit": limit,
                "starting_after": starting_after,
            },
        )
        return Page[Session](
            data=[self._parse(item) for item in payload["data"]],
            has_more=bool(payload["has_more"]),
            next_cursor=payload.get("next_cursor"),
        )

    def end(self, session_id: str) -> Session:
        """Terminate a session immediately. Idempotent."""
        return self._parse(self._client.request("POST", f"/v1/sessions/{session_id}/end"))


class AvatarsResource:
    """``client.avatars`` — list, retrieve, and create avatars."""

    def __init__(self, client: ProtofaceClient) -> None:
        self._client = client

    def list(
        self,
        *,
        limit: int | None = None,
        starting_after: str | None = None,
    ) -> Page[Avatar]:
        """List avatars available to the calling org (incl. platform demos)."""
        payload = self._client.request(
            "GET",
            "/v1/avatars",
            params={"limit": limit, "starting_after": starting_after},
        )
        return Page[Avatar](
            data=[Avatar.model_validate(item) for item in payload["data"]],
            has_more=bool(payload["has_more"]),
            next_cursor=payload.get("next_cursor"),
        )

    def get(self, avatar_id: str) -> Avatar:
        """Retrieve a single avatar by id."""
        return Avatar.model_validate(self._client.request("GET", f"/v1/avatars/{avatar_id}"))

    def create(
        self,
        *,
        image: ImageInput,
        filename: str = "avatar.png",
        name: str | None = None,
        runtime_type: str | None = None,
    ) -> Avatar:
        """Upload a portrait image to build a custom avatar (``processing``)."""
        data: dict[str, str] = {}
        if name is not None:
            data["name"] = name
        if runtime_type is not None:
            data["runtime_type"] = runtime_type
        files = {"image": (filename, bytes(image), "application/octet-stream")}
        return Avatar.model_validate(
            self._client.request("POST", "/v1/avatars", files=files, data=data)
        )

    def delete(self, avatar_id: str) -> None:
        """Delete a custom avatar and purge its stored assets.

        Platform demo avatars cannot be deleted.
        """
        self._client.request("DELETE", f"/v1/avatars/{avatar_id}")


class PipecatResource:
    """``client.pipecat`` — Pipecat avatar media sessions."""

    sessions: PipecatSessionsResource

    def __init__(self, client: ProtofaceClient) -> None:
        self.sessions = PipecatSessionsResource(client)


class PipecatSessionsResource:
    """``client.pipecat.sessions`` — create Pipecat avatar media sessions."""

    def __init__(self, client: ProtofaceClient) -> None:
        self._client = client

    def create(
        self,
        *,
        avatar_id: str,
        quality: QualityTier | str | None = None,
        relay_mode: str | None = None,
        max_duration_seconds: int | None = None,
        idle_timeout_seconds: int | None = None,
        metadata: Mapping[str, str | int | float | bool | None] | None = None,
    ) -> PipecatSessionView:
        """Create a Pipecat avatar media session."""
        body: dict[str, Any] = {"avatar_id": avatar_id}
        if quality is not None:
            body["quality"] = quality.value if isinstance(quality, QualityTier) else quality
        if relay_mode is not None:
            body["relay_mode"] = relay_mode
        if max_duration_seconds is not None:
            body["max_duration_seconds"] = max_duration_seconds
        if idle_timeout_seconds is not None:
            body["idle_timeout_seconds"] = idle_timeout_seconds
        if metadata is not None:
            body["metadata"] = dict(metadata)

        return PipecatSessionView.model_validate(
            self._client.request(
                "POST",
                "/v1/pipecat/sessions",
                json_body=body,
            )
        )


class UsageResource:
    """``client.usage`` — aggregated usage for the calling org."""

    def __init__(self, client: ProtofaceClient) -> None:
        self._client = client

    def summary(
        self,
        *,
        period: str | None = None,
        period_start: str | None = None,
        period_end: str | None = None,
    ) -> UsageSummary:
        """Aggregated usage for the calling org over a time range."""
        return UsageSummary.model_validate(
            self._client.request(
                "GET",
                "/v1/usage",
                params={
                    "period": period,
                    "period_start": period_start,
                    "period_end": period_end,
                },
            )
        )


# Every OpenAPI ``operationId`` the SDK surfaces, mapped to its dotted client
# method path. The drift check (see ``tests/test_coverage.py``) asserts this
# set exactly matches the operationIds in ``apispec/openapi.json``.
OPERATION_COVERAGE: Mapping[str, str] = {
    "list_avatars": "avatars.list",
    "create_avatar": "avatars.create",
    "get_avatar": "avatars.get",
    "delete_avatar": "avatars.delete",
    "list_sessions": "sessions.list",
    "create_session": "sessions.create",
    "get_session": "sessions.get",
    "end_session": "sessions.end",
    "create_pipecat_session": "pipecat.sessions.create",
    "list_billing_plans": "list_billing_plans",
    "get_status": "get_status",
    "get_usage": "usage.summary",
}

__all__ = [
    "DEFAULT_BASE_URL",
    "OPERATION_COVERAGE",
    "AvatarsResource",
    "PipecatResource",
    "PipecatSessionsResource",
    "ProtofaceClient",
    "SessionsResource",
    "TransportConfig",
    "UsageResource",
]
