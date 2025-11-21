# app/routers/ws_health.py
import asyncio
import json
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from fastapi import status, HTTPException
from app.core.config import settings
from app.auth.deps import websocket_user_authorize

router = APIRouter(prefix="/ws", tags=["ws"])


async def _get_last_heartbeat(redis):
    """Return last heartbeat payload from the Redis stream (or None)."""
    try:
        # Try xrevrange (redis-py async). Fallback to xrange -1 -1
        try:
            entries = await redis.xrevrange(settings.HEARTBEAT_REDIS_STREAM, count=1)
            # xrevrange returns list of (id, {field: value}) entries
            if entries:
                _, data = entries[0]
                # field key is "data"
                payload_json = data.get(b"data") if isinstance(data, dict) else data.get("data")
                if isinstance(payload_json, bytes):
                    payload_json = payload_json.decode()
                return json.loads(payload_json)
        except AttributeError:
            # redis client might not have xrevrange; try xrange
            entries = await redis.xrange(settings.HEARTBEAT_REDIS_STREAM, "-", "+", count=1)
            if entries:
                _, data = entries[-1]
                payload_json = data.get(b"data") if isinstance(data, dict) else data.get("data")
                if isinstance(payload_json, bytes):
                    payload_json = payload_json.decode()
                return json.loads(payload_json)
    except Exception:
        return None
    return None


async def _pubsub_listener(redis, websocket: WebSocket, stop_event: asyncio.Event, keyword_filter: Optional[str] = None):
    """
    Subscribe to Redis pubsub channel and forward messages to websocket.
    Works with redis-py `pubsub()` or with `subscribe()` patterns.
    """
    channel = settings.HEARTBEAT_PUBSUB_CHANNEL

    # Prefer the modern pubsub interface if available
    pub = None
    try:
        pub = redis.client.pubsub()
        await pub.subscribe(channel)
        while not stop_event.is_set():
            message = await pub.get_message(ignore_subscribe_messages=True, timeout=1.0)
            if not message:
                await asyncio.sleep(0.05)
                continue
            # message payload handling
            data = message.get("data")
            if isinstance(data, bytes):
                try:
                    payload = json.loads(data.decode())
                except Exception:
                    payload = {"raw": data.decode(errors="ignore")}
            else:
                # on some clients message['data'] is already string
                try:
                    payload = json.loads(data)
                except Exception:
                    payload = {"raw": data}
            # optional keyword filter
            if keyword_filter and keyword_filter.lower() not in json.dumps(payload).lower():
                continue
            await websocket.send_json(payload)
    except AttributeError:
        # Fallback to subscribe-style API (some aioredis libs)
        try:
            ch, = await redis.subscribe(channel)
            async for message in ch.iter():
                if stop_event.is_set():
                    break
                payload_json = message.decode() if isinstance(message, bytes) else message
                payload = json.loads(payload_json) if payload_json else {}
                if keyword_filter and keyword_filter.lower() not in json.dumps(payload).lower():
                    continue
                await websocket.send_json(payload)
        except Exception:
            # if fallback also fails, just return
            return
    finally:
        if pub is not None:
            try:
                await pub.unsubscribe(channel)
                await pub.close()
            except Exception:
                pass


@router.websocket("/health")
async def health_ws(
    websocket: WebSocket,
    replay: bool = Query(False, description="Replay last heartbeat on connect"),
    filter: Optional[str] = Query(None, description="Optional keyword filter (case-insensitive)")
):
    # 1. Extract Token
    auth_header = websocket.headers.get("authorization")
    if not auth_header or not auth_header.lower().startswith("bearer "):
        await websocket.close(code=4001)
        return

    token = auth_header.split(" ", 1)[1]

    # 2. Validate token using your existing user validator
    try:
        # Using your existing Azure/Cognito provider:
        user_claims = await websocket_user_authorize(token)

        # OR if you want universal detection:
        # identity = await validate_bearer_token(token)

    except Exception as e:
        await websocket.close(code=4003)
        return
    
    """
    WebSocket endpoint that streams heartbeat events in real-time.
    - query param : replay=true -> sends last heartbeat immediately (if present)
    - filter -> sends only messages that contain the filter (case-insensitive)
    """
    # 3. Accept WebSocket AFTER authentication
    await websocket.accept()
    app = websocket.app
    redis = getattr(app.state, "redis", None)
    stop_event = asyncio.Event()

    try:
        # Optionally replay last heartbeat
        if replay and redis:
            last = await _get_last_heartbeat(redis)
            if last:
                if filter and filter.lower() not in json.dumps(last).lower():
                    pass
                else:
                    await websocket.send_json(last)

        # Start pubsub listener that forwards to websocket
        listener_task = asyncio.create_task(_pubsub_listener(redis, websocket, stop_event, keyword_filter=filter))

        # Keep connection open; echo pings if needed
        try:
            while True:
                # wait for client messages to detect disconnects — but do not block
                try:
                    msg = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                    # You can support client ping commands here if desired
                    # For now, ignore incoming messages
                except asyncio.TimeoutError:
                    # send a ping as comment (optional) to keep connection alive
                    try:
                        await websocket.send_text("")  # noop to keep connection alive
                    except Exception:
                        break
        except WebSocketDisconnect:
            pass
        finally:
            stop_event.set()
            listener_task.cancel()
            try:
                await listener_task
            except asyncio.CancelledError:
                pass

    except Exception:
        # send close with error code and log
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except Exception:
            pass
