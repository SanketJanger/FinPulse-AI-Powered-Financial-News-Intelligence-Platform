"""
Cache-aside helper for read endpoints.

Pattern: look in Redis first; on a miss, call the loader, store the JSON
result with a TTL, and return it. A Redis outage must never take the API
down, so every Redis call is wrapped — on error we log and fall back to
the loader (i.e. straight to Postgres).
"""
import json
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from redis.asyncio import Redis
from redis.exceptions import RedisError

logger = logging.getLogger("finpulse.cache")


async def cache_aside(
    redis: Redis,
    key: str,
    ttl_seconds: int,
    loader: Callable[[], Awaitable[Any]],
) -> tuple[Any, bool]:
    """Return (value, cache_hit). `value` is always a JSON-serialisable
    structure (dict/list/scalars) — the same thing `loader` returns."""
    try:
        cached = await redis.get(key)
        if cached is not None:
            return json.loads(cached), True
    except (RedisError, OSError) as exc:
        logger.warning("cache read failed for %s: %s", key, exc)

    value = await loader()

    try:
        await redis.set(key, json.dumps(value, default=str), ex=ttl_seconds)
    except (RedisError, OSError) as exc:
        logger.warning("cache write failed for %s: %s", key, exc)

    return value, False
