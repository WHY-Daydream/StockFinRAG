import hashlib
import json
from config import Config
from db import get_redis


class ResultCache:
    """高频问题缓存，TTL=300s"""

    def __init__(self):
        self.redis = get_redis()

    def _key(self, query: str) -> str:
        return f"finrag:q:{hashlib.md5(query.encode()).hexdigest()}"

    def get(self, query: str):
        data = self.redis.get(self._key(query))
        return json.loads(data) if data else None

    def set(self, query: str, result, ttl: int = Config.CACHE_TTL):
        self.redis.setex(self._key(query), ttl, json.dumps(result, ensure_ascii=False))

    def clear(self, query: str = None):
        if query:
            self.redis.delete(self._key(query))
        else:
            for key in self.redis.scan_iter("finrag:q:*"):
                self.redis.delete(key)
