"""Unit tests for the real gemini_client.py, with the genai SDK client mocked."""

import asyncio

import pytest
from google.genai import errors as genai_errors
from google.genai import types

from app.exceptions.turn_exceptions import GeminiUnavailableError
from app.integrations import gemini_client


def _chunk(text: str | None) -> types.GenerateContentResponse:
    if text is None:
        return types.GenerateContentResponse()
    return types.GenerateContentResponse(
        candidates=[
            types.Candidate(content=types.Content(parts=[types.Part(text=text)]))
        ]
    )


class _FakeAioModels:
    def __init__(self, generate_content_stream) -> None:
        self.generate_content_stream = generate_content_stream


class _FakeAio:
    def __init__(self, generate_content_stream) -> None:
        self.models = _FakeAioModels(generate_content_stream)


class _FakeClient:
    """Stands in for genai.Client without ever resolving real ADC credentials."""

    def __init__(self, generate_content_stream) -> None:
        self.aio = _FakeAio(generate_content_stream)


def _install_fake_client(monkeypatch, generate_content_stream) -> None:
    monkeypatch.setattr(gemini_client, "_client", _FakeClient(generate_content_stream))


def _fake_stream(monkeypatch, chunks) -> None:
    async def fake_generate_content_stream(*, model, contents, config):
        async def _iterator():
            for item in chunks:
                if isinstance(item, Exception):
                    raise item
                yield item

        return _iterator()

    _install_fake_client(monkeypatch, fake_generate_content_stream)


async def test_stream_narration_yields_chunk_text(monkeypatch) -> None:
    _fake_stream(monkeypatch, [_chunk("Hello, "), _chunk("adventurer.")])

    chunks = [
        chunk async for chunk in gemini_client.stream_narration("persona", "prompt", 5)
    ]

    assert chunks == ["Hello, ", "adventurer."]


async def test_stream_narration_skips_empty_text_chunks(monkeypatch) -> None:
    _fake_stream(monkeypatch, [_chunk(None), _chunk("Only real text.")])

    chunks = [
        chunk async for chunk in gemini_client.stream_narration("persona", "prompt", 5)
    ]

    assert chunks == ["Only real text."]


async def test_stream_narration_timeout_raises_gemini_unavailable(monkeypatch) -> None:
    async def fake_generate_content_stream(*, model, contents, config):
        async def _iterator():
            await asyncio.sleep(10)
            yield _chunk("too slow")

        return _iterator()

    _install_fake_client(monkeypatch, fake_generate_content_stream)

    with pytest.raises(GeminiUnavailableError):
        async for _ in gemini_client.stream_narration("persona", "prompt", 0.01):
            pass


async def test_stream_narration_server_error_raises_gemini_unavailable(
    monkeypatch,
) -> None:
    server_error = genai_errors.ServerError(503, {"error": {"message": "unavailable"}})
    _fake_stream(monkeypatch, [_chunk("partial"), server_error])

    with pytest.raises(GeminiUnavailableError):
        async for _ in gemini_client.stream_narration("persona", "prompt", 5):
            pass


async def test_stream_narration_rate_limit_raises_gemini_unavailable(
    monkeypatch,
) -> None:
    rate_limit_error = genai_errors.ClientError(
        429, {"error": {"message": "slow down"}}
    )
    _fake_stream(monkeypatch, [rate_limit_error])

    with pytest.raises(GeminiUnavailableError):
        async for _ in gemini_client.stream_narration("persona", "prompt", 5):
            pass


async def test_stream_narration_other_client_error_propagates(monkeypatch) -> None:
    bad_request_error = genai_errors.ClientError(
        400, {"error": {"message": "bad request"}}
    )
    _fake_stream(monkeypatch, [bad_request_error])

    with pytest.raises(genai_errors.ClientError):
        async for _ in gemini_client.stream_narration("persona", "prompt", 5):
            pass
