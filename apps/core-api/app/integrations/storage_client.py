"""Cloud storage client for Core API.

Only module that talks to Google Cloud Storage — nowhere else in the
codebase should instantiate a storage client directly.
"""

from __future__ import annotations

import asyncio

from google.cloud import storage

from app.config import settings
from app.exceptions.upload_exceptions import UploadFailedError

_storage_client: storage.Client | None = None


def _get_client() -> storage.Client:
    global _storage_client
    if _storage_client is None:
        _storage_client = storage.Client()
    return _storage_client


def _upload_blob_sync(content: bytes, content_type: str, object_key: str) -> str:
    bucket = _get_client().bucket(settings.gcs_bucket_name)
    blob = bucket.blob(object_key)
    blob.upload_from_string(content, content_type=content_type)
    blob.make_public()
    return blob.public_url


async def upload_image(content: bytes, content_type: str, object_key: str) -> str:
    """Upload bytes to the configured GCS bucket as public-read; return the public URL."""
    loop = asyncio.get_running_loop()
    try:
        return await loop.run_in_executor(
            None, _upload_blob_sync, content, content_type, object_key
        )
    except Exception as exc:
        raise UploadFailedError(f"Failed to upload image: {exc}") from exc
