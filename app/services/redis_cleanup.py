# app/services/redis_cleanup.py
import asyncio
import redis.asyncio as aioredis
from app.core.config import settings

async def cleanup_old_audits():
    r = aioredis.from_url(settings.REDIS_URL, decode_responses=True)
    keys = await r.keys("audit:*")
    for k in keys:
        ttl = await r.ttl(k)
        if ttl == -1:
            await r.expire(k, settings.REDIS_STREAM_TTL_SEC)
    await r.close()

async def start_cleanup_scheduler():
    """Run periodic cleanup task in background."""
    while True:
        await cleanup_old_audits()
        await asyncio.sleep(3600)  # run every 1 hour
