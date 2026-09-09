"""Tests for the per-IP fixed-window rate limiter middleware."""

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.middleware.rate_limit import (
    EXEMPT_PATHS,
    HEADER_X_REAL_IP,
    FixedWindowRateLimiter,
    rate_limit_middleware,
)

_GENEROUS_LIMIT = 1000
_GENEROUS_WINDOW_SECONDS = 60


def _patch_limiters(
    monkeypatch,
    *,
    burst_limit: int = _GENEROUS_LIMIT,
    burst_window_seconds: int = _GENEROUS_WINDOW_SECONDS,
    daily_limit: int = _GENEROUS_LIMIT,
    daily_window_seconds: int = _GENEROUS_WINDOW_SECONDS,
) -> None:
    import app.middleware.rate_limit as rate_limit_module

    monkeypatch.setattr(
        rate_limit_module,
        "_limiter",
        FixedWindowRateLimiter(limit=burst_limit, window_seconds=burst_window_seconds),
    )
    monkeypatch.setattr(
        rate_limit_module,
        "_daily_limiter",
        FixedWindowRateLimiter(limit=daily_limit, window_seconds=daily_window_seconds),
    )


def _build_app() -> FastAPI:
    app = FastAPI()
    app.middleware("http")(rate_limit_middleware)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/ping")
    async def ping() -> dict[str, str]:
        return {"status": "pong"}

    return app


async def _client_for(app: FastAPI) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver")


async def test_requests_under_limit_pass_through(monkeypatch) -> None:
    _patch_limiters(monkeypatch, burst_limit=3)
    async with await _client_for(_build_app()) as client:
        for _ in range(3):
            response = await client.get(
                "/v1/ping", headers={HEADER_X_REAL_IP: "203.0.113.5"}
            )
            assert response.status_code == 200


async def test_request_over_burst_limit_returns_429_with_retry_after(
    monkeypatch,
) -> None:
    _patch_limiters(monkeypatch, burst_limit=2)
    async with await _client_for(_build_app()) as client:
        headers = {HEADER_X_REAL_IP: "203.0.113.6"}
        await client.get("/v1/ping", headers=headers)
        await client.get("/v1/ping", headers=headers)
        response = await client.get("/v1/ping", headers=headers)

        assert response.status_code == 429
        assert "Retry-After" in response.headers
        assert int(response.headers["Retry-After"]) > 0


async def test_request_over_daily_limit_returns_429_even_within_burst_limit(
    monkeypatch,
) -> None:
    _patch_limiters(monkeypatch, daily_limit=2)
    async with await _client_for(_build_app()) as client:
        headers = {HEADER_X_REAL_IP: "203.0.113.20"}
        first = await client.get("/v1/ping", headers=headers)
        second = await client.get("/v1/ping", headers=headers)
        third = await client.get("/v1/ping", headers=headers)

        assert first.status_code == 200
        assert second.status_code == 200
        assert third.status_code == 429
        assert "Retry-After" in third.headers


async def test_health_is_exempt_from_rate_limiting(monkeypatch) -> None:
    _patch_limiters(monkeypatch, burst_limit=1, daily_limit=1)
    assert "/health" in EXEMPT_PATHS
    async with await _client_for(_build_app()) as client:
        headers = {HEADER_X_REAL_IP: "203.0.113.7"}
        for _ in range(5):
            response = await client.get("/health", headers=headers)
            assert response.status_code == 200


async def test_different_client_keys_tracked_independently(monkeypatch) -> None:
    _patch_limiters(monkeypatch, burst_limit=1, daily_limit=1)
    async with await _client_for(_build_app()) as client:
        response_a = await client.get(
            "/v1/ping", headers={HEADER_X_REAL_IP: "203.0.113.8"}
        )
        response_b = await client.get(
            "/v1/ping", headers={HEADER_X_REAL_IP: "203.0.113.9"}
        )
        assert response_a.status_code == 200
        assert response_b.status_code == 200


async def test_burst_window_resets_after_it_elapses(monkeypatch) -> None:
    import app.middleware.rate_limit as rate_limit_module

    fake_clock = {"now": 1000.0}
    monkeypatch.setattr(rate_limit_module.time, "monotonic", lambda: fake_clock["now"])
    _patch_limiters(monkeypatch, burst_limit=1, burst_window_seconds=60)
    async with await _client_for(_build_app()) as client:
        headers = {HEADER_X_REAL_IP: "203.0.113.10"}
        first = await client.get("/v1/ping", headers=headers)
        blocked = await client.get("/v1/ping", headers=headers)
        fake_clock["now"] += 61
        after_reset = await client.get("/v1/ping", headers=headers)

        assert first.status_code == 200
        assert blocked.status_code == 429
        assert after_reset.status_code == 200


async def test_disabled_flag_bypasses_both_limiters(monkeypatch) -> None:
    from app.config import settings

    _patch_limiters(monkeypatch, burst_limit=1, daily_limit=1)
    monkeypatch.setattr(settings, "is_rate_limit_enabled", False)
    async with await _client_for(_build_app()) as client:
        headers = {HEADER_X_REAL_IP: "203.0.113.11"}
        for _ in range(5):
            response = await client.get("/v1/ping", headers=headers)
            assert response.status_code == 200
