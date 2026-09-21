import redis.asyncio as aioredis

from api.core.config import get_settings

_redis: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    """Shared async Redis client. Used for cache, rate limits and the ARQ broker."""
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            get_settings().redis_url, encoding="utf-8", decode_responses=True
        )
    return _redis


async def close_redis() -> None:
    global _redis
    if _redis is not None:
        await _redis.aclose()
    _redis = None
