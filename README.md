# protoface-sdk

Official Python SDK for the [Protoface](https://protoface.com) API. This is a
typed backend SDK for the public HTTP API, built on
[`httpx`](https://www.python-httpx.org/) and [Pydantic v2](https://docs.pydantic.dev/).

Install the `protoface-sdk` distribution and import the `protoface_sdk` package.

## Install

```sh
pip install protoface-sdk
```

## Quickstart

```python
import os

from protoface_sdk import ProtofaceClient

with ProtofaceClient(api_key=os.environ["PROTOFACE_API_KEY"]) as client:
    status = client.get_status()
    avatars = client.avatars.list(limit=10)

    print(status.status)
    print([avatar.id for avatar in avatars.data])
```

## Resources

```python
client.sessions.create(request, idempotency_key=...)
client.sessions.create_livekit(avatar_id=..., url=..., room_name=..., worker_token=...)
client.sessions.get(session_id)
client.sessions.list(status=[...], avatar_id=..., limit=...)   # -> Page[Session]
client.sessions.end(session_id)

client.avatars.list(limit=...)                                 # -> Page[Avatar]
client.avatars.get(avatar_id)
client.avatars.create(image=..., name=...)                     # multipart upload
client.avatars.delete(avatar_id)

client.pipecat.sessions.create(avatar_id=...)                  # Pipecat relay bootstrap

client.usage.summary(period="current_month")                   # or period_start/period_end

client.list_billing_plans()
client.get_status()
```

`Page` objects expose `.data`, `.has_more`, and `.next_cursor`. Pass
`.next_cursor` back as `starting_after` to fetch the next page.

## Starting sessions

`client.sessions.create_livekit(...)` starts the backend worker for a
customer-owned LiveKit room. Your application still owns the LiveKit room and
mints the worker token with its own LiveKit API key and secret; this SDK never
touches those credentials.

```python
session = client.sessions.create_livekit(
    avatar_id="av_stock_001",
    url=os.environ["LIVEKIT_URL"],
    room_name="demo-room",
    worker_token=worker_token,
)

session = session.wait_until_running(timeout=10)
print(session.id, session.status)
```

For framework-level realtime integrations, use the dedicated packages:

- `livekit-plugins-protoface` for LiveKit Agents.
- `pipecat-protoface` for Pipecat.

## Errors

Every non-2xx response raises a typed `ProtofaceError` subclass
(`AuthenticationError`, `RateLimitError`, `QuotaExceededError`, etc.). Switch on
the stable `error.code`, never on `error.message`:

```python
from protoface_sdk import ProtofaceError, QuotaExceededError, RateLimitError

try:
    session = client.sessions.create(request)
except RateLimitError as err:
    print("rate limited:", err.code, err.retry_after_seconds)
except QuotaExceededError as err:
    print("quota:", err.code)
except ProtofaceError as err:
    print(err.code, err.request_id, err.status)
```

The client automatically retries `429` and `503` responses (honoring
`Retry-After`) and transient network failures, up to `max_retries` (default 2).

## Configuration

| Option            | Default                       | Notes                              |
| ----------------- | ----------------------------- | ---------------------------------- |
| `api_key`         | required                      | `sk_live_...`                      |
| `base_url`        | `https://api.protoface.com`   | Override for staging/local.        |
| `timeout`         | `60.0`                        | Per-request timeout (seconds).     |
| `max_retries`     | `2`                           | Retries for 429/503/network.       |
| `default_headers` | `None`                        | Extra headers on every request.    |
| `transport`       | `None`                        | Inject an `httpx.BaseTransport`.   |

The client is a context manager and owns an `httpx.Client` connection pool:

```python
with ProtofaceClient(api_key=...) as client:
    ...
```

## Development

Wire models in `src/protoface_sdk/_generated.py` are generated from
`apispec/openapi.json`.

The canonical public OpenAPI spec is emitted from the private Protoface monorepo
at `apispec/openapi.json`. This repo vendors a copy so SDK builds are
reproducible. `protoface-docs/openapi.json` is downstream Mintlify input and
should not be used as the SDK source of truth.

```sh
make sync-openapi  # copy ../protoface/apispec/openapi.json and regenerate models
make openapi-check # compare the vendored spec with the sibling monorepo copy
make generate       # regenerate src/protoface_sdk/_generated.py from the spec
make lint           # ruff check + format --check
make type           # pyright (strict)
make test           # pytest
make build          # wheel/sdist build + twine check
```

`make generate` runs `datamodel-code-generator` and then normalizes the output
with `ruff format` and `ruff check --fix`.
