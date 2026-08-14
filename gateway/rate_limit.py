"""Redis sliding-window RPM limiter (per tenant)."""

from __future__ import annotations

import os
import time
import uuid

import redis

_CLIENT: redis.Redis | None = None


def _client() -> redis.Redis | None:
    global _CLIENT
    url = os.environ.get("REDIS_URL", "").strip()
    if not url:
        return None
    if _CLIENT is None:
        _CLIENT = redis.Redis.from_url(url, decode_responses=True)
    return _CLIENT


def get_redis() -> redis.Redis | None:
    return _client()


def check_rpm(tenant_id: str, limit: int, window_seconds: int = 60) -> tuple[bool, int]:
    """
    Sliding window via Redis ZSET of request timestamps.
    Key: af:rpm:{tenant_id}
    Returns (allowed, remaining). If Redis unavailable, allow (fail-open for local prototype).
    """
    if limit <= 0:
        return False, 0
    r = _client()
    if r is None:
        return True, limit

    key = f"af:rpm:{tenant_id}"
    now = time.time()
    window_start = now - window_seconds
    member = f"{now}:{uuid.uuid4().hex}"

    pipe = r.pipeline()
    pipe.zremrangebyscore(key, 0, window_start)
    pipe.zcard(key)
    results = pipe.execute()
    count = int(results[1])
    if count >= limit:
        r.expire(key, window_seconds + 5)
        return False, 0

    pipe = r.pipeline()
    pipe.zadd(key, {member: now})
    pipe.expire(key, window_seconds + 5)
    pipe.execute()
    return True, max(0, limit - count - 1)


def reset_client_for_tests() -> None:
    global _CLIENT
    _CLIENT = None
