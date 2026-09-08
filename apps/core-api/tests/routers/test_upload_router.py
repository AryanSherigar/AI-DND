"""Integration tests for the image upload REST endpoint."""

import uuid
from pathlib import Path

import pytest
from httpx import AsyncClient

from app.config import settings
from app.integrations import storage_client


@pytest.fixture
def mock_upload_image(monkeypatch):
    async def _fake_upload_image(
        content: bytes, content_type: str, object_key: str
    ) -> str:
        return f"https://storage.googleapis.com/fake-bucket/{object_key}"

    monkeypatch.setattr(storage_client, "upload_image", _fake_upload_image)


@pytest.mark.asyncio
async def test_upload_cover_image_success(async_client: AsyncClient, mock_upload_image):
    headers = {"x-dev-user-id": str(uuid.uuid4())}
    files = {"file": ("cover.png", b"\x89PNG\r\n\x1a\n" + b"0" * 100, "image/png")}

    resp = await async_client.post(
        "/v1/uploads/scenario-cover-image", headers=headers, files=files
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["url"].startswith("https://storage.googleapis.com/fake-bucket/")


@pytest.mark.asyncio
async def test_upload_map_image_success(async_client: AsyncClient, mock_upload_image):
    headers = {"x-dev-user-id": str(uuid.uuid4())}
    files = {"file": ("map.png", b"\x89PNG\r\n\x1a\n" + b"0" * 100, "image/png")}

    resp = await async_client.post(
        "/v1/uploads/scenario-map-image", headers=headers, files=files
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["url"].startswith(
        "https://storage.googleapis.com/fake-bucket/scenario-maps/"
    )


@pytest.mark.asyncio
async def test_upload_scenario_audio_success(async_client: AsyncClient, mock_upload_image):
    headers = {"x-dev-user-id": str(uuid.uuid4())}
    files = {"file": ("ashfall.ogg", b"OggS" + b"0" * 100, "audio/ogg")}

    resp = await async_client.post(
        "/v1/uploads/scenario-audio", headers=headers, files=files
    )

    assert resp.status_code == 200
    assert resp.json()["url"].startswith(
        "https://storage.googleapis.com/fake-bucket/scenario-audio/"
    )


@pytest.mark.asyncio
async def test_upload_scenario_audio_rejects_non_audio(
    async_client: AsyncClient, mock_upload_image
):
    headers = {"x-dev-user-id": str(uuid.uuid4())}
    resp = await async_client.post(
        "/v1/uploads/scenario-audio",
        headers=headers,
        files={"file": ("not-audio.txt", b"text", "text/plain")},
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_local_dev_upload_saves_to_disk(
    async_client: AsyncClient, monkeypatch, tmp_path
):
    monkeypatch.setattr(settings, "environment", "development")
    monkeypatch.setattr(settings, "gcs_bucket_name", "")
    monkeypatch.setattr(settings, "local_upload_dir", str(tmp_path))
    monkeypatch.setattr(settings, "core_api_public_url", "http://localhost:8000")

    png_bytes = b"\x89PNG\r\n\x1a\n" + b"1" * 50
    headers = {"x-dev-user-id": str(uuid.uuid4())}
    files = {"file": ("cover.png", png_bytes, "image/png")}

    resp = await async_client.post(
        "/v1/uploads/scenario-cover-image", headers=headers, files=files
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["url"].startswith("http://localhost:8000/uploads/scenario-covers/")

    # Verify file was written to disk
    relative_path = data["url"].replace("http://localhost:8000/uploads/", "")
    saved_file = Path(tmp_path) / relative_path
    assert saved_file.exists()
    assert saved_file.read_bytes() == png_bytes


@pytest.mark.asyncio
async def test_upload_cover_image_oversized(
    async_client: AsyncClient, mock_upload_image
):
    headers = {"x-dev-user-id": str(uuid.uuid4())}
    oversized_content = b"0" * (5 * 1024 * 1024 + 1)
    files = {"file": ("cover.png", oversized_content, "image/png")}

    resp = await async_client.post(
        "/v1/uploads/scenario-cover-image", headers=headers, files=files
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_upload_cover_image_wrong_content_type(
    async_client: AsyncClient, mock_upload_image
):
    headers = {"x-dev-user-id": str(uuid.uuid4())}
    files = {"file": ("cover.pdf", b"%PDF-1.4", "application/pdf")}

    resp = await async_client.post(
        "/v1/uploads/scenario-cover-image", headers=headers, files=files
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_upload_cover_image_requires_auth(async_client: AsyncClient):
    files = {"file": ("cover.png", b"fake-png-bytes", "image/png")}

    resp = await async_client.post("/v1/uploads/scenario-cover-image", files=files)
    assert resp.status_code == 401
