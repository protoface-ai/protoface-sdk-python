"""Unit tests for ``ProtofaceClient`` using ``httpx.MockTransport``."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from protoface_sdk import (
    AuthenticationError,
    InternalError,
    ProtofaceClient,
    ProtofaceConnectionError,
    QuotaExceededError,
    RateLimitError,
    Session,
    SessionStatus,
    __version__,
)

Handler = Callable[[httpx.Request], httpx.Response]


def _client(handler: Handler, *, max_retries: int = 2) -> ProtofaceClient:
    return ProtofaceClient(
        api_key="sk_live_test",
        transport=httpx.MockTransport(handler),
        max_retries=max_retries,
    )


def _session_body(status: str = "queued", session_id: str = "sess_01HXY") -> dict[str, object]:
    return {
        "object": "session",
        "id": session_id,
        "status": status,
        "avatar_id": "av_demo",
        "transport": {
            "type": "livekit",
            "url": "wss://my-app.livekit.cloud",
            "room_name": "demo-room",
            "worker_token": "[redacted]",
        },
        "quality": "standard",
        "max_duration_seconds": 600,
        "idle_timeout_seconds": 30,
        "metadata": {"customer_session_id": "abc123"},
        "created_at": "2026-05-25T19:00:00Z",
    }


def _error_body(error_type: str, code: str, message: str = "boom") -> dict[str, object]:
    return {
        "error": {
            "type": error_type,
            "code": code,
            "message": message,
            "param": None,
            "request_id": "req_01HXY",
        }
    }


def _avatar_body(avatar_id: str = "av_demo") -> dict[str, object]:
    return {
        "object": "avatar",
        "id": avatar_id,
        "name": "Demo Avatar",
        "status": "ready",
        "runtime_type": "avtr1",
        "is_demo": True,
        "created_at": "2026-05-25T19:00:00Z",
    }


def test_create_session_success() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/sessions"
        assert request.headers["authorization"] == "Bearer sk_live_test"
        assert request.headers["user-agent"] == f"protoface-sdk/{__version__}"
        captured["body"] = json.loads(request.content)
        return httpx.Response(201, json=_session_body())

    client = _client(handler)
    session = client.sessions.create(
        {
            "avatar_id": "av_demo",
            "transport": {
                "type": "livekit",
                "url": "wss://x.livekit.cloud",
                "room_name": "r",
                "worker_token": "tok",
            },
        }
    )

    assert isinstance(session, Session)
    assert session.id == "sess_01HXY"
    assert session.status is SessionStatus.queued
    assert captured["body"]["avatar_id"] == "av_demo"


def test_create_livekit_builds_transport_and_sends_idempotency_key() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        captured["idempotency_key"] = request.headers.get("idempotency-key")
        return httpx.Response(201, json=_session_body())

    client = _client(handler)
    client.sessions.create_livekit(
        avatar_id="av_demo",
        url="wss://my-app.livekit.cloud",
        room_name="demo-room",
        worker_token="eyJ.fake",
        audio_source="data_stream",
        max_duration_seconds=120,
        metadata={"k": "v"},
        idempotency_key="idem-123",
    )

    body = captured["body"]
    assert body["avatar_id"] == "av_demo"
    assert body["transport"] == {
        "type": "livekit",
        "url": "wss://my-app.livekit.cloud",
        "room_name": "demo-room",
        "worker_token": "eyJ.fake",
        "audio_source": "data_stream",
    }
    assert body["max_duration_seconds"] == 120
    assert body["metadata"] == {"k": "v"}
    assert captured["idempotency_key"] == "idem-123"


def test_create_pipecat_session_success() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/pipecat/sessions"
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            201,
            json={
                "object": "pipecat.session",
                "session": _session_body(),
                "relay": {
                    "type": "websocket",
                    "protocol": "protoface.pipecat.media.v1",
                    "media_url": "wss://api.test/v1/pipecat/sessions/sess_test/media",
                    "media_token": "pfm_test",
                    "audio_sample_rate": 16000,
                    "video_encoding": "jpeg",
                    "decoded_video_format": "RGB",
                    "supports_audio_output": True,
                },
            },
        )

    client = _client(handler)
    result = client.pipecat.sessions.create(
        avatar_id="av_demo",
        relay_mode="websocket",
        max_duration_seconds=120,
        metadata={"customer_session_id": "pc_123"},
    )

    assert captured["body"] == {
        "avatar_id": "av_demo",
        "relay_mode": "websocket",
        "max_duration_seconds": 120,
        "metadata": {"customer_session_id": "pc_123"},
    }
    assert result.object == "pipecat.session"
    assert result.session.id == "sess_01HXY"
    assert result.relay.type == "websocket"
    assert "/v1/pipecat/sessions/sess_test/media" in result.relay.media_url


def test_get_session_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1/sessions/sess_01HXY"
        return httpx.Response(200, json=_session_body(session_id="sess_01HXY"))

    session = _client(handler).sessions.get("sess_01HXY")
    assert session.id == "sess_01HXY"
    assert session.avatar_id == "av_demo"


def test_end_session_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/sessions/sess_01HXY/end"
        return httpx.Response(200, json=_session_body(status="ending", session_id="sess_01HXY"))

    session = _client(handler).sessions.end("sess_01HXY")
    assert session.id == "sess_01HXY"
    assert session.status is SessionStatus.ending


def test_get_status_shape() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/status"
        return httpx.Response(
            200,
            json={
                "status": "operational",
                "components": [{"name": "api", "status": "operational"}],
                "updated_at": "2026-05-25T19:00:00Z",
            },
        )

    status = _client(handler).get_status()
    assert status.status.value == "operational"
    assert status.components[0].name == "api"


def test_list_billing_plans_shape() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1/billing/plans"
        return httpx.Response(
            200,
            json=[
                {
                    "key": "free",
                    "name": "Free",
                    "monthly_price_cents": 0,
                    "included_credits": 50,
                    "extra_credit_unit_micros": None,
                    "max_concurrency": 1,
                    "custom_avatar_slots": 1,
                    "extra_avatar_slot_cents": None,
                    "session_time_limit_seconds": 120,
                }
            ],
        )

    plans = _client(handler).list_billing_plans()
    assert plans[0].key == "free"
    assert plans[0].included_credits == 50


def test_avatars_create_multipart_upload() -> None:
    captured: dict[str, Any] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "POST"
        assert request.url.path == "/v1/avatars"
        captured["content_type"] = request.headers["content-type"]
        captured["raw"] = request.content
        return httpx.Response(
            202,
            json={
                "object": "avatar",
                "id": "av_new",
                "name": "My Avatar",
                "status": "processing",
                "runtime_type": "avtr1",
                "is_demo": False,
                "created_at": "2026-05-25T19:00:00Z",
            },
        )

    avatar = _client(handler).avatars.create(
        image=b"\x89PNG\r\n", filename="face.png", name="My Avatar"
    )
    assert avatar.id == "av_new"
    assert avatar.status.value == "processing"
    assert "multipart/form-data" in str(captured["content_type"])
    assert b"My Avatar" in captured["raw"]


def test_avatars_get_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1/avatars/av_demo"
        return httpx.Response(200, json=_avatar_body())

    avatar = _client(handler).avatars.get("av_demo")
    assert avatar.id == "av_demo"
    assert avatar.status.value == "ready"


def test_avatars_delete_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "DELETE"
        assert request.url.path == "/v1/avatars/av_demo"
        return httpx.Response(204)

    assert _client(handler).avatars.delete("av_demo") is None


def test_list_sessions_pagination_shape() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params.get_list("status") == ["running", "queued"]
        assert request.url.params["limit"] == "2"
        return httpx.Response(
            200,
            json={
                "object": "list",
                "data": [_session_body(session_id="sess_a"), _session_body(session_id="sess_b")],
                "has_more": True,
                "next_cursor": "sess_b",
            },
        )

    page = _client(handler).sessions.list(status=["running", "queued"], limit=2)
    assert [s.id for s in page.data] == ["sess_a", "sess_b"]
    assert page.has_more is True
    assert page.next_cursor == "sess_b"


def test_list_avatars_empty_page() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"object": "list", "data": [], "has_more": False})

    page = _client(handler).avatars.list()
    assert page.data == []
    assert page.has_more is False
    assert page.next_cursor is None


def test_usage_summary_success() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v1/usage"
        assert request.url.params["period"] == "current_month"
        return httpx.Response(
            200,
            json={
                "period_start": "2026-05-01T00:00:00Z",
                "period_end": "2026-06-01T00:00:00Z",
                "billable_seconds": 120,
                "sessions": 3,
                "by_quality": {"standard": 120},
            },
        )

    usage = _client(handler).usage.summary(period="current_month")
    assert usage.billable_seconds == 120
    assert usage.sessions == 3


def test_401_maps_to_authentication_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            401,
            json=_error_body("authentication", "invalid_api_key", "bad key"),
            headers={"x-request-id": "req_hdr"},
        )

    with pytest.raises(AuthenticationError) as exc_info:
        _client(handler).avatars.get("av_demo")

    err = exc_info.value
    assert err.status == 401
    assert err.type == "authentication"
    assert err.code == "invalid_api_key"
    assert err.request_id == "req_01HXY"
    assert err.message == "bad key"


def test_429_retries_then_succeeds_honoring_retry_after() -> None:
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        if calls["n"] == 1:
            return httpx.Response(
                429,
                json=_error_body("rate_limit", "too_many_requests"),
                headers={"retry-after": "0"},
            )
        return httpx.Response(201, json=_session_body())

    session = _client(handler, max_retries=2).sessions.create(
        {
            "avatar_id": "av_demo",
            "transport": {"type": "livekit", "url": "u", "room_name": "r", "worker_token": "t"},
        }
    )
    assert calls["n"] == 2
    assert session.status is SessionStatus.queued


def test_429_exhausted_raises_with_retry_after_seconds() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            json=_error_body("rate_limit", "too_many_requests"),
            headers={"retry-after": "0"},
        )

    with pytest.raises(RateLimitError) as exc_info:
        _client(handler, max_retries=0).avatars.get("av_demo")
    assert exc_info.value.retry_after_seconds == 0.0


def test_quota_exceeded_maps_by_type() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(402, json=_error_body("quota_exceeded", "credits_exhausted"))

    with pytest.raises(QuotaExceededError):
        _client(handler).avatars.get("av_demo")


def test_network_error_maps_to_connection_error() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("dns boom", request=request)

    with pytest.raises(ProtofaceConnectionError):
        _client(handler, max_retries=0).avatars.get("av_demo")


def test_non_json_error_body_falls_back() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="<html>gateway</html>")

    with pytest.raises(InternalError) as exc_info:
        _client(handler, max_retries=0).avatars.get("av_demo")
    err = exc_info.value
    assert err.code == "unexpected_response"
    assert err.status == 500


def test_wait_until_running_polls_until_running() -> None:
    statuses = iter(["queued", "starting", "running"])

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(201, json=_session_body(status="queued"))
        return httpx.Response(200, json=_session_body(status=next(statuses)))

    client = _client(handler)
    session = client.sessions.create(
        {
            "avatar_id": "av_demo",
            "transport": {"type": "livekit", "url": "u", "room_name": "r", "worker_token": "t"},
        }
    )
    settled = session.wait_until_running(timeout=5, poll_interval=0.0)
    assert settled.status is SessionStatus.running


def test_wait_until_running_times_out() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            return httpx.Response(201, json=_session_body(status="queued"))
        return httpx.Response(200, json=_session_body(status="queued"))

    client = _client(handler)
    session = client.sessions.create(
        {
            "avatar_id": "av_demo",
            "transport": {"type": "livekit", "url": "u", "room_name": "r", "worker_token": "t"},
        }
    )
    with pytest.raises(TimeoutError):
        session.wait_until_running(timeout=0.05, poll_interval=0.01)
