"""Lightweight in-memory cache for market data and indicators."""
from __future__ import annotations
import hashlib
import os
import pickle
from collections.abc import Callable
from typing import Any

class MemoryCache:
    def __init__(self) -> None:
        self._values: dict[str, Any] = {}

    def get_or_calc(self, code: str, func: Callable[..., Any], *args: Any) -> Any:
        key = f"{code}:{func.__name__}"
        if key not in self._values:
            self._values[key] = func(*args)
        return self._values[key]

    def clear(self) -> None:
        self._values.clear()

class RedisCache:
    def __init__(self, url: str, ttl_seconds: int = 21_600) -> None:
        import redis
        self._client = redis.Redis.from_url(url, socket_connect_timeout=2)
        self._client.ping()
        self._ttl_seconds = ttl_seconds

    def _key(self, code: str, func: Callable[..., Any]) -> str:
        raw = f"{code}:{func.__module__}:{func.__name__}"
        digest = hashlib.sha256(raw.encode()).hexdigest()
        return f"selection-engine:{digest}"

    def get_or_calc(self, code: str, func: Callable[..., Any], *args: Any) -> Any:
        key = self._key(code, func)
        cached = self._client.get(key)
        if cached is not None:
            return pickle.loads(cached)
        value = func(*args)
        self._client.setex(key, self._ttl_seconds, pickle.dumps(value))
        return value

    def clear(self) -> None:
        for key in self._client.scan_iter(match="selection-engine:*"):
            self._client.delete(key)

def create_cache() -> MemoryCache | RedisCache:
    url = os.getenv("REDIS_URL", "").strip()
    if not url:
        return MemoryCache()
    try:
        return RedisCache(url)
    except Exception:
        return MemoryCache()

_default_cache = MemoryCache()

def get_or_calc(code: str, func: Callable[..., Any], *args: Any) -> Any:
    return _default_cache.get_or_calc(code, func, *args)

def clear() -> None:
    _default_cache.clear()
