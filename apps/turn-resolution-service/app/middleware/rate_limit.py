"""Per-IP fixed-window rate limiting.

Two independent windows are enforced per client: a short burst window and a
much longer daily cap. Both counters increment on every non-exempt request,
regardless of which one (if either) rejects it, so retries against a tripped
burst limit still count against the daily budget.

In-memory and per-instance by design: no Redis/Postgres-backed store, matching
this project's rejection of new broker/cache infra (see ADR-010). On Cloud Run
this means the effective limit scales with instance count, and the daily
counter resets whenever an instance is replaced -- a soft deterrent against
casual abuse, not a hard guarantee.

NOTE: keys on X-Real-IP (set by the frontend's nginx proxy) rather than
request.client.host, since every browser request reaches this service through
that proxy and would otherwise all appear to come from one IP.
"""

import time
from collections.abc import Callable
from dataclasses import dataclass

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.datastructures import Address

from app.config import settings

HEADER_X_REAL_IP = "X-Real-IP"
HEADER_RETRY_AFTER = "Retry-After"
UNKNOWN_CLIENT_KEY = "unknown"
EXEMPT_PATHS = frozenset({"/health"})
RATE_LIMIT_EXCEEDED_DETAIL = "Rate limit exceeded"


@dataclass(frozen=True)
class RateLimitResult:
    is_allowed: bool
    retry_after_seconds: int


class FixedWindowRateLimiter:
    """Tracks a (window_start, count) counter per key.

    No lock: a single uvicorn worker runs one event loop, and check() never
    awaits between reading and writing a counter, so each call is atomic.
    """

    def __init__(self, limit: int, window_seconds: int) -> None:
        self._limit = limit
        self._window_seconds = window_seconds
        self._counters: dict[str, tuple[float, int]] = {}

    def check(self, key: str, now: float) -> RateLimitResult:
        window_start, count = self._counters.get(key, (now, 0))
        elapsed = now - window_start
        if elapsed >= self._window_seconds:
            window_start, count = now, 0
            elapsed = 0.0

        count += 1
        self._counters[key] = (window_start, count)

        if count > self._limit:
            retry_after = round(self._window_seconds - elapsed)
            return RateLimitResult(is_allowed=False, retry_after_seconds=retry_after)
        return RateLimitResult(is_allowed=True, retry_after_seconds=0)


def _get_client_key(request: Request) -> str:
    real_ip = request.headers.get(HEADER_X_REAL_IP)
    if real_ip:
        return real_ip
    client: Address | None = request.client
    return client.host if client else UNKNOWN_CLIENT_KEY


def _build_rate_limit_response(retry_after_seconds: int) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": RATE_LIMIT_EXCEEDED_DETAIL},
        headers={HEADER_RETRY_AFTER: str(retry_after_seconds)},
    )


_limiter = FixedWindowRateLimiter(
    limit=settings.rate_limit_requests_per_window,
    window_seconds=settings.rate_limit_window_seconds,
)
_daily_limiter = FixedWindowRateLimiter(
    limit=settings.rate_limit_daily_requests,
    window_seconds=settings.rate_limit_daily_window_seconds,
)


def _check_limits(key: str, now: float) -> RateLimitResult:
    burst_result = _limiter.check(key, now)
    daily_result = _daily_limiter.check(key, now)
    if burst_result.is_allowed and daily_result.is_allowed:
        return RateLimitResult(is_allowed=True, retry_after_seconds=0)

    retry_after = max(
        burst_result.retry_after_seconds, daily_result.retry_after_seconds
    )
    return RateLimitResult(is_allowed=False, retry_after_seconds=retry_after)


async def rate_limit_middleware(request: Request, call_next: Callable) -> Response:
    if not settings.is_rate_limit_enabled or request.url.path in EXEMPT_PATHS:
        return await call_next(request)

    result = _check_limits(_get_client_key(request), time.monotonic())
    if not result.is_allowed:
        return _build_rate_limit_response(result.retry_after_seconds)

    return await call_next(request)
