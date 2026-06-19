import json
import os
from typing import Any

import redis


class RecommendationCacheClient:
    def __init__(self) -> None:
        self.url = os.getenv("REDIS_URL", "redis://redis:6379/0")
        self.ttl_seconds = int(os.getenv("RECOMMENDATION_CACHE_TTL", "1800"))
        self._client: redis.Redis | None = None
        self.hits = 0
        self.misses = 0

    @property
    def client(self) -> redis.Redis:
        if self._client is None:
            self._client = redis.from_url(self.url, decode_responses=True)
        return self._client

    def get_json(self, key: str) -> Any | None:
        try:
            raw = self.client.get(key)
        except redis.RedisError:
            self.misses += 1
            return None
        if raw is None:
            self.misses += 1
            return None
        self.hits += 1
        return json.loads(raw)

    def set_json(self, key: str, value: Any) -> None:
        try:
            self.client.setex(key, self.ttl_seconds, json.dumps(value))
        except redis.RedisError:
            return

    def stats(self) -> dict[str, int | float | str]:
        total = self.hits + self.misses
        hit_rate = self.hits / total if total else 0.0
        return {
            "redis_url": self.url,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(hit_rate, 4),
        }


cache_client = RecommendationCacheClient()
