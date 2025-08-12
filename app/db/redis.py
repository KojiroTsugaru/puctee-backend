import redis.asyncio as aioredis
from functools import lru_cache
from app.core.config import settings

class RedisClient:
    def __init__(self, url: str):
        self._url = url
        self._redis = None

    async def connect(self):
        if self._redis is None:
            self._redis = await aioredis.from_url(self._url, encoding="utf-8", decode_responses=True)
        return self._redis

    async def close(self):
        if self._redis:
            await self._redis.close()
            self._redis = None

@lru_cache()
def get_redis_client() -> RedisClient:
    # Get Redis URL from environment variables
    return RedisClient(url=settings.REDIS_URL)
    