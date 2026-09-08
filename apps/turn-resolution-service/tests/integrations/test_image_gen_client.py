"""Unit tests for the real image_gen_client.py, with the genai SDK client mocked."""

import asyncio

import pytest
from app.exceptions.turn_exceptions import SceneImageGenerationError
from app.integrations import image_gen_client
from google.genai import errors as genai_errors
from google.genai import types


class _FakeAioModels:
    def __init__(self, generate_images) -> None:
        self.generate_images = generate_images


class _FakeAio:
    def __init__(self, generate_images) -> None:
        self.models = _FakeAioModels(generate_images)


class _FakeClient:
    """Stands in for genai.Client without ever resolving real ADC credentials."""

    def __init__(self, generate_images) -> None:
        self.aio = _FakeAio(generate_images)


def _install_fake_client(monkeypatch, generate_images) -> None:
    monkeypatch.setattr(image_gen_client, "_client", _FakeClient(generate_images))


def _response(image_bytes: bytes | None) -> types.GenerateImagesResponse:
    if image_bytes is None:
        return types.GenerateImagesResponse(generated_images=[])
    return types.GenerateImagesResponse(
        generated_images=[
            types.GeneratedImage(image=types.Image(image_bytes=image_bytes))
        ]
    )


async def test_generate_image_returns_bytes(monkeypatch) -> None:
    async def fake_generate_images(*, model, prompt, config):
        return _response(b"fake-png-bytes")

    _install_fake_client(monkeypatch, fake_generate_images)

    result = await image_gen_client.generate_image("a scene", 5)

    assert result == b"fake-png-bytes"


async def test_generate_image_no_results_raises(monkeypatch) -> None:
    async def fake_generate_images(*, model, prompt, config):
        return _response(None)

    _install_fake_client(monkeypatch, fake_generate_images)

    with pytest.raises(SceneImageGenerationError):
        await image_gen_client.generate_image("a scene", 5)


async def test_generate_image_timeout_raises(monkeypatch) -> None:
    async def fake_generate_images(*, model, prompt, config):
        await asyncio.sleep(10)
        return _response(b"too-slow")

    _install_fake_client(monkeypatch, fake_generate_images)

    with pytest.raises(SceneImageGenerationError):
        await image_gen_client.generate_image("a scene", 0.01)


async def test_generate_image_server_error_raises(monkeypatch) -> None:
    async def fake_generate_images(*, model, prompt, config):
        raise genai_errors.ServerError(503, {"error": {"message": "unavailable"}})

    _install_fake_client(monkeypatch, fake_generate_images)

    with pytest.raises(SceneImageGenerationError):
        await image_gen_client.generate_image("a scene", 5)
