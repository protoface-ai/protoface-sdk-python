# Protoface Python SDK

Official Python SDK for the [Protoface](https://protoface.com) API.

Install `protoface-sdk` and import `protoface_sdk`.

## About Protoface

Protoface adds a real-time avatar to your AI app or agent.

Get a **free** API key at [protoface.com](https://protoface.com/?utm_source=github&utm_medium=referral&utm_campaign=github_docs&utm_content=TODO-INSERT-REPO-NAME).

Read the docs at [docs.protoface.com](https://docs.protoface.com/?utm_source=github&utm_medium=referral&utm_campaign=github_docs&utm_content=TODO-INSERT-REPO-NAME).

To see quickstarts for other platforms, visit the [quickstart repo](https://github.com/protoface-ai/protoface-quickstart).

## Installation

```sh
pip install protoface-sdk
```

Or with uv:

```sh
uv add protoface-sdk
```

Requires Python 3.10+ and a Protoface API key.

## Quickstart

```python
import os

from protoface_sdk import ProtofaceClient

with ProtofaceClient(api_key=os.environ["PROTOFACE_API_KEY"]) as client:
    status = client.get_status()
    avatars = client.avatars.list(limit=10)

    print(status.status.value)
    print([avatar.id for avatar in avatars.data])
```

## Resources

```python
client.sessions.create(session_request, idempotency_key=...)
client.sessions.create_livekit(avatar_id=..., url=..., room_name=..., worker_token=...)
client.sessions.get(session_id)
client.sessions.list(status=["running"], avatar_id=..., limit=...)  # -> Page[Session]
client.sessions.end(session_id)

client.avatars.list(scope="platform", q="stock", limit=...)    # -> Page[Avatar]
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

## LiveKit sessions

`client.sessions.create_livekit(...)` starts the backend worker for a
customer-owned LiveKit room. Your application still owns the room and mints a
short-lived worker token with its own LiveKit API key and secret.

```python
session = client.sessions.create_livekit(
    avatar_id="av_stock_001",
    url=livekit_url,
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
    client.sessions.create(session_request)
except RateLimitError as err:
    print("rate limited:", err.code, err.retry_after_seconds)
except QuotaExceededError as err:
    print("quota:", err.code)
except ProtofaceError as err:
    print(err.code, err.request_id, err.status)
```

The client retries `429`, `503`, and transient network failures for safe
requests, and for writes that include an `Idempotency-Key`.

## Protoface: More Quickstarts

Protoface integrates with popular voice AI platforms.

Clone a starter repo, add your keys to the environment file, and run.

If an SDK or plugin is available separately, we've linked to it instead.

| Platform | Link |
| --- | --- |
| LiveKit | [Plugin](https://github.com/livekit/agents/tree/main/livekit-plugins/livekit-plugins-protoface) |
| Pipecat | [Plugin](https://github.com/protoface-ai/protoface-plugin-pipecat) |
| Agora | [Starter Repo](https://github.com/protoface-ai/protoface-quickstart-agora) |
| Vapi | [Starter Repo](https://github.com/protoface-ai/protoface-quickstart-vapi) |
| ElevenLabs Agents | [Starter Repo](https://github.com/protoface-ai/protoface-quickstart-elevenlabs-agents) |
| OpenAI Realtime | [Starter Repo](https://github.com/protoface-ai/protoface-quickstart-openai-realtime) |
| VideoSDK | [Starter Repo](https://github.com/protoface-ai/protoface-quickstart-videosdk) |
| Python | [SDK](https://github.com/protoface-ai/protoface-sdk-python) |
| Node.js | [SDK](https://github.com/protoface-ai/protoface-sdk-node) |

## License

Apache-2.0 - see [LICENSE](LICENSE).
