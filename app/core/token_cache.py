import time
import hashlib
import json
from typing import Any, Dict, Optional
import redis.asyncio as aioredis

class TokenCache:
    """Hybrid in-memory + Redis cache for validated JWT tokens."""

    def __init__(self, redis_url: Optional[str] = None):
        self.memory_cache: Dict[str, Dict[str, Any]] = {}
        self.redis = aioredis.from_url(redis_url, decode_responses=True) if redis_url else None

    @staticmethod
    def token_key(token: str) -> str:
        """Use SHA256 hash as cache key."""
        return hashlib.sha256(token.encode()).hexdigest()

    async def get(self, token: str) -> Optional[Dict[str, Any]]:
        key = self.token_key(token)

        # Check memory first
        item = self.memory_cache.get(key)
        if item and item["expires_at"] > time.time():
            return item["value"]

        # Check Redis
        if self.redis:
            cached = await self.redis.get(f"jwt:{key}")
            if cached:
                data = json.loads(cached)
                if data["expires_at"] > time.time():
                    # Repopulate memory cache
                    self.memory_cache[key] = data
                    return data["value"]

        return None

    async def set(self, token: str, value: Dict[str, Any], expires_in: int):
        key = self.token_key(token)
        item = {
            "value": value,
            "expires_at": time.time() + expires_in
        }

        # Memory cache
        self.memory_cache[key] = item

        # Redis cache
        if self.redis:
            await self.redis.set(
                f"jwt:{key}",
                json.dumps(item),
                ex=expires_in
            )
token_cache = TokenCache()