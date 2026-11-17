# SPDX-License-Identifier: AGPL-3.0-or-later
"""Rate limiting per IP and per user (memory for dev, Redis in production)."""

from functools import lru_cache

from fastapi import HTTPException, Request, status
from limits import parse
from limits.storage import storage_from_string
from limits.strategies import MovingWindowRateLimiter

from app.config import get_settings


@lru_cache
def _limiter() -> MovingWindowRateLimiter:
    return MovingWindowRateLimiter(storage_from_string(get_settings().rate_limit_storage))


def reset_limits() -> None:
    _limiter().storage.reset()


def client_ip(request: Request) -> str:
    # Behind a proxy run uvicorn with --proxy-headers --forwarded-allow-ips=<proxy ip>
    # so request.client reflects the real client. We never trust X-Forwarded-For directly.
    return request.client.host if request.client else "unknown"


def hit(scope: str, key: str, rate: str) -> None:
    if not _limiter().hit(parse(rate), scope, key):
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "rate_limited"},
            headers={"Retry-After": "60"},
        )


def limit_ip(scope: str, rate: str):
    def dependency(request: Request) -> None:
        hit(scope, f"ip:{client_ip(request)}", rate)

    return dependency
