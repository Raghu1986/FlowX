import time
from datetime import datetime, timezone
from sqlalchemy import text
from app.core.db import async_engine
from app.core.config import settings


async def collect_metrics(redis=None):
    """
    Collect system-level metrics for heartbeat.
    Returns a structured dict with DB and Redis health info.
    """
    metrics = {}
    metrics["timestamp"] = datetime.now(timezone.utc).isoformat()
    metrics["uptime_seconds"] = round(time.perf_counter(), 2)

    # ---- DB METRICS ----
    try:
        if async_engine:
            pool = async_engine.pool
            checked_out = pool.checkedout()
            pool_size = pool.size()

            metrics["db_connections"] = {
                "checked_out": checked_out,
                "checked_in": pool_size - checked_out,
                "overflow": pool.overflow(),
                "pool_size": pool_size,
            }

            # If we can acquire briefly, DB is UP
            async with async_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            metrics["db_status"] = "UP"

        else:
            metrics["db_status"] = "DOWN"
            metrics["db_connections"] = None

    except Exception as e:
        metrics["db_status"] = "DOWN"
        metrics["db_error"] = str(e)

    # ---- REDIS METRICS ----
    try:
        if redis:
            start = time.perf_counter()            
            pong = await redis.ping()
            latency = (time.perf_counter() - start) * 1000
            metrics["redis_latency_ms"] = round(latency, 2)
            metrics["redis_status"] = "UP" if pong else "DOWN"
        else:
            metrics["redis_status"] = "DOWN"
            metrics["redis_latency_ms"] = None
    except Exception as e:
        metrics["redis_status"] = "DOWN"
        metrics["redis_error"] = str(e)

    # ---- TASK QUEUE PLACEHOLDER ----
    metrics["task_queue_length"] = 0

    # ---- OVERALL HEALTH ----
    if metrics["db_status"] == "DOWN" and metrics["redis_status"] == "DOWN":
        metrics["status"] = "down"
    elif metrics["db_status"] == "DOWN" or metrics["redis_status"] == "DOWN":
        metrics["status"] = "degraded"
    else:
        metrics["status"] = "healthy"

    return metrics