import json
import logging
from typing import Any, Optional
import redis.asyncio as redis
from app.core.config import settings

logger = logging.getLogger("sakra.cache")

class RedisCache:
    def __init__(self):
        self.client = None
        if settings.REDIS_URL:
            try:
                # Use standard configuration with decode_responses=True for strings
                self.client = redis.from_url(settings.REDIS_URL, decode_responses=True, socket_timeout=3.0)
                logger.info("Successfully initialized async Redis client.")
            except Exception as e:
                logger.error(f"Redis initialization failed: {e}")
        else:
            logger.info("Redis cache disabled: REDIS_URL not configured.")

    async def ping(self) -> bool:
        if not self.client:
            return False
        try:
            await self.client.ping()
            return True
        except Exception as e:
            logger.error(f"Redis ping failed: {e}")
            return False

    async def get(self, key: str) -> Optional[Any]:
        if not self.client:
            return None
        try:
            val = await self.client.get(key)
            if val:
                return json.loads(val)
        except Exception as e:
            logger.error(f"Redis GET failed for key '{key}': {e}")
        return None

    async def set(self, key: str, value: Any, expire_seconds: int = 300) -> bool:
        if not self.client:
            return False
        try:
            await self.client.set(key, json.dumps(value), ex=expire_seconds)
            return True
        except Exception as e:
            logger.error(f"Redis SET failed for key '{key}': {e}")
            return False

    async def delete(self, key: str) -> bool:
        if not self.client:
            return False
        try:
            await self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis DELETE failed for key '{key}': {e}")
            return False

    async def invalidate_pattern(self, pattern: str) -> bool:
        """Invalidate keys matching a pattern, useful for bulk invalidations."""
        if not self.client:
            return False
        try:
            keys = await self.client.keys(pattern)
            if keys:
                await self.client.delete(*keys)
                logger.info(f"Invalidated {len(keys)} keys matching pattern: {pattern}")
            return True
        except Exception as e:
            logger.error(f"Redis delete keys by pattern failed: {e}")
            return False

    async def invalidate_all(self) -> bool:
        if not self.client:
            return False
        try:
            await self.client.flushdb()
            logger.info("Redis flushdb completed: cache cleared completely.")
            return True
        except Exception as e:
            logger.error(f"Redis FLUSHDB failed: {e}")
            return False

# Export a single global cache instance
cache = RedisCache()
