# app/services/notification_service.py
import json
from datetime import datetime, timezone
from typing import AsyncIterator

def _utc_timestamp() -> str:
    """Generate an ISO8601 UTC timestamp with 'Z' suffix."""
    return datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


async def publish(app, audit_id: str, payload: dict):
    """Publish a message with a UTC timestamp to Redis Stream."""
    redis = app.state.redis
    key = f"audit:{audit_id}"

    # Automatically inject timestamp
    payload["timestamp"] = _utc_timestamp()

    # Store JSON payload
    await redis.stream_add(key, json.dumps(payload))


async def subscribe(app, audit_id: str, last_id: str = "$") -> AsyncIterator[str]:
    """
    Subscribe to Redis Stream with replay + live streaming.

    1️⃣ On first connection → replay full stream (XRANGE)
    2️⃣ Then → switch to continuous live listening (XREAD)
    """
    redis = app.state.redis
    key = f"audit:{audit_id}"

    # 1️⃣ Replay existing messages (history)
    try:
        history = await redis.client.xrange(key, "-", "+")
        for msg_id, fields in history:
            yield fields["data"]
    except Exception as e:
        print(f"[Redis] No history found for {key}: {e}")

    # 2️⃣ Live listen for new messages
    last_id = "$"
    while True:
        messages = await redis.stream_read(key, last_id=last_id)
        if not messages:
            continue
        for _, entries in messages:
            for msg_id, fields in entries:
                last_id = msg_id
                yield fields["data"]
