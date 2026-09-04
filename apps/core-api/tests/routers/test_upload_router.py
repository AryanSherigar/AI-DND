"""Integration tests for the image upload REST endpoint."""

import uuid

import pytest
from httpx import AsyncClient

from app.integrations import storage_client


@pytest.fixture(autouse=True)
def mock_upload_image(monkeypatch):
    async def _fake_upload_image(
        content: bytes, content_type: str, object_key: str
    ) -> str:
        return f"https://storage.googleapis.com/fake-bucket/{object_key}"

    monkeypatch.setattr(storage_client, "upload_image", _fake_upload_image)


@pytest.mark.asyncio
async def test_upload_cover_image_success(async_client: AsyncClient):
    headers = {"x-dev-user-id": str(uuid.uuid4())}
    files = {"file": ("cover.png", b"\x89PNG\r\n\x1a\n" + b"0" * 100, "image/png")}

    resp = await async_client.post(
        "/v1/uploads/scenario-cover-image", headers=headers, files=files
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["url"].startswith("https://storage.googleapis.com/fake-bucket/")


@pytest.mark.asyncio
async def test_upload_cover_image_oversized(async_client: AsyncClient):
    headers = {"x-dev-user-id": str(uuid.uuid4())}
    oversized_content = b"0" * (5 * 1024 * 1024 + 1)
    files = {"file": ("cover.png", oversized_content, "image/png")}

    resp = await async_client.post(
        "/v1/uploads/scenario-cover-image", headers=headers, files=files
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_upload_cover_image_wrong_content_type(async_client: AsyncClient):
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
