import json
import socket
from datetime import datetime, timezone
from app.core.config import settings
from app.core.metrics import collect_metrics


async def emit_heartbeat(redis, logger):
    """
    Emit structured heartbeat with metrics to logs and optionally Redis.
    """
    hostname = socket.gethostname()
    timestamp = datetime.now(timezone.utc).isoformat()

    metrics = await collect_metrics(redis)

    payload = {
        "type": "service_heartbeat",
        "app_name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "hostname": hostname,
        "timestamp": timestamp,
        **metrics,  # include metrics fields
    }

    # Log it locally
    logger.info("💓 Service heartbeat emitted", extra={"event": "heartbeat", **payload})

    # Push to Redis stream
    if settings.HEARTBEAT_ENABLED and redis:
        payload_json = json.dumps(payload)
        # 1) push to Redis Stream
        try:
            await redis.xadd(
                settings.HEARTBEAT_REDIS_STREAM,
                {"data": payload_json},
                maxlen=1000,
            )
            await redis.expire(settings.HEARTBEAT_REDIS_STREAM, settings.HEARTBEAT_TTL_SECONDS)
            logger.debug(
                "✅ Heartbeat with metrics pushed to Redis",
                extra={"event": "heartbeat_publish", "stream": settings.HEARTBEAT_REDIS_STREAM},
            )
        except Exception as e:
            logger.error(
                "❌ Failed to publish heartbeat",
                extra={"event": "heartbeat_publish_error", "error": str(e)},
            )

        # 2) publish on Pub/Sub channel for realtime watchers
        try:
            await redis.publish(settings.HEARTBEAT_PUBSUB_CHANNEL, payload_json)
            logger.debug("✅ Heartbeat published to pubsub", extra={"event": "heartbeat_pubsub", "channel": settings.HEARTBEAT_PUBSUB_CHANNEL})
        except Exception as e:
            logger.error("❌ Failed to publish heartbeat on pubsub", extra={"event": "heartbeat_pubsub_error", "error": str(e)})