# app/core/redis_client.py
import redis.asyncio as aioredis
from app.core.config import settings
import json

class RedisClient:
    """Async Redis Streams client with auto-trim and expiry."""
    def __init__(self, url: str):
        self.url = url
        self.client: aioredis.Redis | None = None

    async def connect(self):
        if self.client is None:
            self.client = aioredis.from_url(self.url, decode_responses=True)
        return self.client

    async def close(self):
        if self.client:
            await self.client.close()
            self.client = None

    async def xadd(self, stream: str, data: dict, maxlen: int = 1000):
        """
        Direct low-level stream add (for heartbeat, etc.)
        """
        r = await self.connect()
        return await r.xadd(stream, data, maxlen=maxlen)

    async def publish(self, channel: str, message: str):
        """
        Publish a message to a Redis pub/sub channel
        """
        r = await self.connect()
        return await r.publish(channel, message)
    
    async def ping(self):
        """
        Ping Redis to verify connectivity.
        """
        r = await self.connect()
        try:
            pong = await r.ping()
            return pong
        except Exception:
            return False

    async def xrevrange(self, stream: str, count: int = 1):
        r = await self.connect()
        return await r.xrevrange(stream, count=count)

    async def expire(self, key: str, seconds: int):
        r = await self.connect()
        return await r.expire(key, seconds)


    async def stream_add(self, stream: str, payload: str):
        """
        Append message to stream, trim length, and refresh TTL.
        """
        r = await self.connect()
        # Add entry
        msg_id = await r.xadd(stream, {"data": payload})

        # Trim stream to maxlen (approximate)
        if settings.REDIS_STREAM_MAXLEN > 0:
            await r.xtrim(stream, maxlen=settings.REDIS_STREAM_MAXLEN, approximate=True)

        # Refresh expiry TTL
        if settings.REDIS_STREAM_TTL_SEC > 0:
            await r.expire(stream, settings.REDIS_STREAM_TTL_SEC)

        return msg_id

    async def stream_read(self, stream: str, last_id: str = "$", block: int = 5000, count: int = 10):
        r = await self.connect()
        return await r.xread({stream: last_id}, block=block, count=count)
