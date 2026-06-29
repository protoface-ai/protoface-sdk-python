"""Spec-vs-SDK drift check.

Mirror of the TypeScript SDK's ``test/coverage.test.ts``: every
``operationId`` in the committed OpenAPI spec must have a matching SDK method,
and every SDK method must reference an operationId that exists in the spec.
"""

from __future__ import annotations

import json
from pathlib import Path

from protoface_sdk import OPERATION_COVERAGE

_SPEC_PATH = Path(__file__).resolve().parents[1] / "apispec" / "openapi.json"


def _spec_operation_ids() -> set[str]:
    spec = json.loads(_SPEC_PATH.read_text(encoding="utf-8"))
    ids: set[str] = set()
    for methods in spec["paths"].values():
        for operation in methods.values():
            if isinstance(operation, dict) and isinstance(operation.get("operationId"), str):
                ids.add(operation["operationId"])
    return ids


def test_sdk_implements_exactly_the_spec_operations() -> None:
    in_spec = _spec_operation_ids()
    in_sdk = set(OPERATION_COVERAGE)

    missing_from_sdk = sorted(in_spec - in_sdk)
    stale_in_sdk = sorted(in_sdk - in_spec)

    assert missing_from_sdk == [], (
        f"operationIds in the spec with no SDK method: {missing_from_sdk}"
    )
    assert stale_in_sdk == [], f"SDK methods referencing unknown operationIds: {stale_in_sdk}"
