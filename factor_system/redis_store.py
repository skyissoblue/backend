"""Redis hash persistence for precomputed factors."""
from __future__ import annotations

import math
from typing import Any

import redis

from .config import BATCH_SIZE, REDIS_URL
from .logger import get_logger

logger = get_logger(__name__)
_pool = redis.ConnectionPool.from_url(REDIS_URL, decode_responses=True)


def client() -> redis.Redis:
    return redis.Redis(connection_pool=_pool)


def _clean(values: dict[str, Any]) -> dict[str, str | int | float]:
    result = {}
    for key, value in values.items():
        if value is None or (isinstance(value, float) and not math.isfinite(value)):
            continue
        result[key] = int(value) if isinstance(value, bool) else value
    return result


def batch_set_hash(prefix: str, data_dict: dict[str, dict[str, Any]]) -> int:
    items = list(data_dict.items())
    written = 0
    for start in range(0, len(items), BATCH_SIZE):
        batch = items[start:start + BATCH_SIZE]
        for attempt in range(2):
            try:
                pipe = client().pipeline(transaction=False)
                for code, values in batch:
                    cleaned = _clean(values)
                    if cleaned:
                        pipe.hset(f"{prefix}:{code}", mapping=cleaned)
                pipe.execute()
                written += len(batch)
                break
            except redis.RedisError:
                if attempt:
                    raise
                logger.exception("Redis pipeline failed; retrying")
    return written


def batch_get_hash(code: str, fields: list[str]) -> dict[str, float | bool | None]:
    pipe = client().pipeline(transaction=False)
    for field in fields:
        pipe.hget(f"stock:{code}", field)
    values = pipe.execute()
    return {field: _decode(value) for field, value in zip(fields, values)}


def _decode(value: str | None) -> float | bool | None:
    if value is None:
        return None
    try:
        return float(value)
    except ValueError:
        return value.lower() == "true" if value.lower() in {"true", "false"} else None


def get_factor(code: str, factor_name: str) -> float | bool | None:
    return _decode(client().hget(f"stock:{str(code).zfill(6)}", factor_name))


def batch_get_factor(codes: list[str], factor_name: str) -> dict[str, float | bool | None]:
    """Fetch one factor for a universe using bounded Redis pipelines."""
    result: dict[str, float | bool | None] = {}
    for start in range(0, len(codes), BATCH_SIZE):
        batch = codes[start:start + BATCH_SIZE]
        pipe = client().pipeline(transaction=False)
        for code in batch:
            pipe.hget(f"stock:{str(code).zfill(6)}", factor_name)
        result.update({code: _decode(value) for code, value in zip(batch, pipe.execute())})
    return result


def health_check() -> bool:
    try:
        return bool(client().ping())
    except redis.RedisError:
        return False


def clear_factor_prefix(prefix: str) -> int:
    deleted, batch = 0, []
    for key in client().scan_iter(match=f"{prefix}:*"):
        batch.append(key)
        if len(batch) >= BATCH_SIZE:
            deleted += client().delete(*batch)
            batch.clear()
    return deleted + (client().delete(*batch) if batch else 0)


def get_memory_usage() -> dict[str, Any]:
    info = client().info("memory")
    return {key: info.get(key) for key in ("used_memory", "used_memory_human", "used_memory_peak_human")}
