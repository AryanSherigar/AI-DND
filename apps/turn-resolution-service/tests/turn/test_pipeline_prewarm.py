"""Unit tests for the SSRF guard on _prewarm_replit_url (P0-SEC-2)."""

import pytest

from app.turn import pipeline

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def test_rejects_non_https_scheme() -> None:
    assert await pipeline._is_safe_prewarm_url("http://foo.replit.app/game") is False


async def test_rejects_non_whitelisted_domain() -> None:
    assert (
        await pipeline._is_safe_prewarm_url("https://metadata.google.internal/x")
        is False
    )


async def test_rejects_lookalike_domain_suffix() -> None:
    assert await pipeline._is_safe_prewarm_url("https://evil.com/replit.app") is False


async def test_rejects_private_ip_resolution(monkeypatch) -> None:
    def _fake_getaddrinfo(host, port):
        return [(None, None, None, None, ("169.254.169.254", 0))]

    monkeypatch.setattr(pipeline.socket, "getaddrinfo", _fake_getaddrinfo)
    assert await pipeline._is_safe_prewarm_url("https://foo.replit.app/game") is False


async def test_accepts_public_ip_resolution(monkeypatch) -> None:
    def _fake_getaddrinfo(host, port):
        return [(None, None, None, None, ("8.8.8.8", 0))]

    monkeypatch.setattr(pipeline.socket, "getaddrinfo", _fake_getaddrinfo)
    assert await pipeline._is_safe_prewarm_url("https://foo.replit.app/game") is True


async def test_prewarm_never_calls_httpx_for_unsafe_url(monkeypatch) -> None:
    called = {"n": 0}

    class _ExplodingClient:
        async def __aenter__(self):
            called["n"] += 1
            raise AssertionError("httpx.AsyncClient must not be constructed")

        async def __aexit__(self, *args):
            return False

    monkeypatch.setattr(
        pipeline.httpx, "AsyncClient", lambda **kwargs: _ExplodingClient()
    )

    await pipeline._prewarm_replit_url("http://169.254.169.254/latest/meta-data/")

    assert called["n"] == 0
