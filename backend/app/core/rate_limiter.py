import asyncio
from collections import defaultdict
import logging
import os
import time
from typing import Dict, List, Optional, Tuple
import uuid

logger = logging.getLogger(__name__)

# Try to import redis.asyncio
try:
    import redis.asyncio as aioredis
except ImportError:
    aioredis = None


class TenantRateLimiter:
    """
    Sliding window rate limiter using Redis sorted sets (ZADD/ZCARD),
    with automatic in-memory sliding window fallback if Redis is unreachable.
    """

    def __init__(self, redis_url: Optional[str] = None):
        self.redis_url = redis_url or os.getenv("REDIS_URL", "redis://localhost:6380/0")
        self._redis_client = None
        self._redis_loop = None
        
        # In-memory sliding window fallback: key -> list of float timestamps
        self._mem_store: Dict[str, List[float]] = defaultdict(list)

    async def get_redis(self):
        if aioredis is None:
            return None

        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        # If redis client belongs to a different or closed event loop, reset it
        if self._redis_client is not None and self._redis_loop != current_loop:
            try:
                await self._redis_client.aclose()
            except Exception:
                pass
            self._redis_client = None
            self._redis_loop = None

        if self._redis_client is None and current_loop is not None:
            try:
                client = aioredis.from_url(
                    self.redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_connect_timeout=0.5,
                )
                await client.ping()
                self._redis_client = client
                self._redis_loop = current_loop
            except Exception as e:
                logger.debug(f"Redis not available for rate limiter ({e}). Using in-memory fallback.")
                self._redis_client = None
                self._redis_loop = None

        return self._redis_client

    async def check_rate_limit(
        self,
        identifier: str,
        limit: int = 60,
        window_seconds: int = 60,
    ) -> Tuple[bool, int, int]:
        """
        Evaluates whether the identifier has exceeded the request quota in the rolling window.
        Returns:
            (is_allowed: bool, remaining_quota: int, reset_in_seconds: int)
        """
        now = time.time()
        window_start = now - window_seconds
        redis = await self.get_redis()

        if redis is not None:
            try:
                key = f"ratelimit:{identifier}"
                pipe = redis.pipeline()
                # 1. Remove timestamps older than rolling window
                pipe.zremrangebyscore(key, 0, window_start)
                # 2. Count active requests in current window
                pipe.zcard(key)
                # 3. Add current request
                member_id = f"{now}-{uuid.uuid4().hex[:6]}"
                pipe.zadd(key, {member_id: now})
                # 4. Set expiry
                pipe.expire(key, window_seconds + 5)
                
                results = await pipe.execute()
                current_count = results[1]

                if current_count >= limit:
                    # Over quota: remove the element we just added
                    await redis.zrem(key, member_id)
                    remaining = 0
                    reset_time = window_seconds
                    return False, remaining, reset_time

                remaining = max(0, limit - current_count - 1)
                return True, remaining, window_seconds
            except Exception as e:
                logger.warning(f"Redis rate limit check error ({e}). Falling back to memory.")
                self._redis_client = None

        # In-memory sliding window fallback
        timestamps = self._mem_store[identifier]
        valid_timestamps = [t for t in timestamps if t > window_start]
        self._mem_store[identifier] = valid_timestamps

        if len(valid_timestamps) >= limit:
            remaining = 0
            reset_time = int(window_seconds - (now - valid_timestamps[0])) if valid_timestamps else window_seconds
            return False, remaining, max(1, reset_time)

        self._mem_store[identifier].append(now)
        remaining = max(0, limit - len(self._mem_store[identifier]))
        return True, remaining, window_seconds

    def reset_memory(self):
        """Helper for unit tests to clear in-memory rate limits."""
        self._mem_store.clear()


# Global rate limiter instance
rate_limiter = TenantRateLimiter()
