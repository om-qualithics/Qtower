import time

import redis

from apps.api.core.settings import settings

_redis = redis.from_url(settings.redis_url)


class RateLimitExceededError(Exception):
    pass


def check_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    """Fixed-window counter backed by the same Redis instance Celery
    already uses as its broker (no new infra dependency). Raises on the
    (limit+1)th hit within the window; the caller maps that to a 429.

    Fixed-window (not sliding/token-bucket) is a deliberate simplicity
    call - it can allow a short burst right at a window boundary, which is
    an acceptable trade for the two things this actually protects
    (login brute-forcing and unbounded real-money LLM spend), not a
    general-purpose API gateway."""
    bucket = f"ratelimit:{key}:{int(time.time()) // window_seconds}"
    count = _redis.incr(bucket)
    if count == 1:
        _redis.expire(bucket, window_seconds)
    if count > limit:
        raise RateLimitExceededError(f"Rate limit exceeded: {limit} per {window_seconds}s")
