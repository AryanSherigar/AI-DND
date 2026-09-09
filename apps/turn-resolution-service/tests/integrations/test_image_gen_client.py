"""Unit tests for the real image_gen_client.py, with the genai SDK client mocked."""

import asyncio

import pytest
from google.genai import errors as genai_errors
from google.genai import types

from app.exceptions.turn_exceptions import SceneImageGenerationError
from app.integrations import image_gen_client


class _FakeAioModels:
    def __init__(self, generate_content) -> None:
        self.generate_content = generate_content


class _FakeAio:
    def __init__(self, generate_content) -> None:
        self.models = _FakeAioModels(generate_content)


class _FakeClient:
    """Stands in for genai.Client without ever resolving real ADC credentials."""

    def __init__(self, generate_content) -> None:
        self.aio = _FakeAio(generate_content)


def _install_fake_client(monkeypatch, generate_content) -> None:
    monkeypatch.setattr(image_gen_client, "_client", _FakeClient(generate_content))


def _response(image_bytes: bytes | None) -> types.GenerateContentResponse:
    parts = []
    if image_bytes is not None:
        parts = [
            types.Part(inline_data=types.Blob(data=image_bytes, mime_type="image/png"))
        ]
    return types.GenerateContentResponse(
        candidates=[types.Candidate(content=types.Content(parts=parts))]
    )


async def test_generate_image_returns_bytes(monkeypatch) -> None:
    async def fake_generate_content(*, model, contents):
        return _response(b"fake-png-bytes")

    _install_fake_client(monkeypatch, fake_generate_content)

    result = await image_gen_client.generate_image("a scene", 5)

    assert result == b"fake-png-bytes"


async def test_generate_image_no_results_raises(monkeypatch) -> None:
    async def fake_generate_content(*, model, contents):
        return _response(None)

    _install_fake_client(monkeypatch, fake_generate_content)

    with pytest.raises(SceneImageGenerationError):
        await image_gen_client.generate_image("a scene", 5)


async def test_generate_image_timeout_raises(monkeypatch) -> None:
    async def fake_generate_content(*, model, contents):
        await asyncio.sleep(10)
        return _response(b"too-slow")

    _install_fake_client(monkeypatch, fake_generate_content)

    with pytest.raises(SceneImageGenerationError):
        await image_gen_client.generate_image("a scene", 0.01)


async def test_generate_image_server_error_raises(monkeypatch) -> None:
    async def fake_generate_content(*, model, contents):
        raise genai_errors.ServerError(503, {"error": {"message": "unavailable"}})

    _install_fake_client(monkeypatch, fake_generate_content)

    with pytest.raises(SceneImageGenerationError):
        await image_gen_client.generate_image("a scene", 5)
