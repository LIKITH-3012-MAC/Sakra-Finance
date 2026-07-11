import json
import logging
from typing import Any, Optional
import redis
from app.core.config import settings

logger = logging.getLogger("sakra.cache")

class RedisCache:
    def __init__(self):
        self.client = None
        if settings.REDIS_URL:
            try:
                # Use standard configuration with decode_responses=True for strings
                self.client = redis.Redis.from_url(settings.REDIS_URL, decode_responses=True, socket_timeout=3.0)
                # Test connection
                self.client.ping()
                logger.info("Successfully connected to Redis instance.")
            except Exception as e:
                logger.error(f"Redis connection fallback: could not establish connection. Details: {e}")
                self.client = None
        else:
            logger.info("Redis cache disabled: REDIS_URL not configured.")

    def get(self, key: str) -> Optional[Any]:
        if not self.client:
            return None
        try:
            val = self.client.get(key)
            if val:
                return json.loads(val)
        except Exception as e:
            logger.error(f"Redis GET failed for key '{key}': {e}")
        return None

    def set(self, key: str, value: Any, expire_seconds: int = 300) -> bool:
        if not self.client:
            return False
        try:
            self.client.set(key, json.dumps(value), ex=expire_seconds)
            return True
        except Exception as e:
            logger.error(f"Redis SET failed for key '{key}': {e}")
            return False

    def delete(self, key: str) -> bool:
        if not self.client:
            return False
        try:
            self.client.delete(key)
            return True
        except Exception as e:
            logger.error(f"Redis DELETE failed for key '{key}': {e}")
            return False

    def invalidate_pattern(self, pattern: str) -> bool:
        """Invalidate keys matching a pattern, useful for bulk invalidations."""
        if not self.client:
            return False
        try:
            keys = self.client.keys(pattern)
            if keys:
                self.client.delete(*keys)
                logger.info(f"Invalidated {len(keys)} keys matching pattern: {pattern}")
            return True
        except Exception as e:
            logger.error(f"Redis delete keys by pattern failed: {e}")
            return False

    def invalidate_all(self) -> bool:
        if not self.client:
            return False
        try:
            self.client.flushdb()
            logger.info("Redis flushdb completed: cache cleared completely.")
            return True
        except Exception as e:
            logger.error(f"Redis FLUSHDB failed: {e}")
            return False

# Export a single global cache instance
cache = RedisCache()
