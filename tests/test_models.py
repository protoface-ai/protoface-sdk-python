from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import TypeVar

import pytest
from pydantic import BaseModel, ValidationError

from protoface_sdk import (
    ApiError,
    ApiErrorEnvelope,
    Avatar,
    AvatarStatus,
    ErrorType,
    LiveKitAudioSource,
    LiveKitTransportConfig,
    QualityTier,
    Session,
    SessionCreateRequest,
    SessionStatus,
    SessionUsage,
    UsageSummary,
)
from protoface_sdk._generated import AvatarList, SessionList

_SPEC_PATH = Path(__file__).resolve().parents[1] / "apispec" / "openapi.json"
T = TypeVar("T", bound=BaseModel)


def _roundtrip(model: T) -> T:
    dumped = model.model_dump(mode="json")
    reparsed = json.loads(json.dumps(dumped))
    return type(model).model_validate(reparsed)


def _livekit() -> LiveKitTransportConfig:
    return LiveKitTransportConfig(
        url="wss://my-app.livekit.cloud",
        room_name="demo-room",
        worker_token="eyJ.fake",
    )


def test_session_create_request_roundtrip() -> None:
    req = SessionCreateRequest(
        avatar_id="av_demo",
        transport=_livekit(),
        quality=QualityTier.standard,
        metadata={"k": "v", "n": 42, "b": True, "x": None},
    )
    assert _roundtrip(req) == req


def test_session_roundtrip() -> None:
    now = datetime(2026, 5, 25, 19, 0, 0, tzinfo=timezone.utc)
    session = Session(
        id="sess_01HXY",
        status=SessionStatus.running,
        avatar_id="av_demo",
        transport=_livekit(),
        quality=QualityTier.standard,
        max_duration_seconds=600,
        idle_timeout_seconds=30,
        metadata={"caller": "tests"},
        created_at=now,
        started_at=now,
        first_frame_at=now,
        usage=SessionUsage(billable_seconds=3, frames=75),
    )
    assert _roundtrip(session) == session


def test_usage_summary_roundtrip() -> None:
    now = datetime(2026, 5, 1, tzinfo=timezone.utc)
    summary = UsageSummary(
        period_start=now,
        period_end=now,
        billable_seconds=120,
        sessions=4,
        by_quality={QualityTier.standard: 60, QualityTier.pro: 60},
    )
    assert _roundtrip(summary) == summary


def test_api_error_envelope_roundtrip() -> None:
    env = ApiErrorEnvelope(
        error=ApiError(
            type=ErrorType.invalid_request,
            code="transport.unsupported",
            message="reserved",
            param="transport.type",
            request_id="req_01HXY",
        )
    )
    assert _roundtrip(env) == env


def test_livekit_audio_source_default() -> None:
    cfg = _livekit()
    assert cfg.audio_source == LiveKitAudioSource.data_stream


def test_naive_datetime_rejected() -> None:
    with pytest.raises(ValidationError):
        Avatar(
            id="av_demo",
            name="Demo",
            status=AvatarStatus.ready,
            runtime_type="mock",
            is_demo=True,
            created_at=datetime(2026, 5, 25, 19, 0, 0),  # intentionally naive
        )


def test_spec_examples_validate() -> None:
    spec = json.loads(_SPEC_PATH.read_text(encoding="utf-8"))
    schemas = spec["components"]["schemas"]
    models: dict[str, type[BaseModel]] = {
        "Avatar": Avatar,
        "AvatarList": AvatarList,
        "ApiError": ApiError,
        "ApiErrorEnvelope": ApiErrorEnvelope,
        "LiveKitTransportConfig": LiveKitTransportConfig,
        "SessionUsage": SessionUsage,
        "SessionCreateRequest": SessionCreateRequest,
        "SessionList": SessionList,
        "UsageSummary": UsageSummary,
    }
    checked = 0
    for name, model in models.items():
        for example in schemas[name].get("examples", []):
            model.model_validate(example)
            checked += 1
    assert checked > 0
