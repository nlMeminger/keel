from __future__ import annotations

import redis

from app.config import settings
from app.core.errors import AppError

# SPEC.md §6 starting numbers — tune based on real usage, not load-tested.
LOGIN_LIMIT = (5, 900)  # 5 attempts / 15 min, per IP+username
REGISTER_LIMIT = (10, 3600)  # 10 / hour, per IP
REFRESH_LIMIT = (30, 3600)  # 30 / hour, per user
# API_SPEC.md §18 starting point — independent of the Plaid monthly-call cap, which
# throttles Plaid cost rather than external API usage.
API_TOKEN_LIMIT = (60, 60)  # 60 requests / minute, per token

_clients: dict[str, redis.Redis[str]] = {}


def get_redis() -> redis.Redis[str]:
    """Cached per distinct URL so tests can point at a different logical DB and get isolation."""
    url = settings.redis_url
    if url not in _clients:
        _clients[url] = redis.from_url(url, decode_responses=True)
    return _clients[url]


def enforce_rate_limit(key: str, limit: int, window_seconds: int) -> None:
    """Fixed-window counter backed by Redis. Raises AppError(429) once `limit` is exceeded."""
    client = get_redis()
    count = client.incr(key)
    if count == 1:
        client.expire(key, window_seconds)
    if count > limit:
        raise AppError(429, "rate_limited", "Too many requests. Please try again later.")
