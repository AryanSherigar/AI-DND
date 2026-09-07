"""Cloud storage client for Core API.

Only module that talks to Google Cloud Storage — nowhere else in the
codebase should instantiate a storage client directly.
"""

from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError

from app.config import settings
from app.exceptions.upload_exceptions import UploadFailedError

logger = logging.getLogger(__name__)

_storage_client: storage.Client | None = None


def _get_client() -> storage.Client:
    global _storage_client
    if _storage_client is not None:
        return _storage_client

    cred_path = settings.firebase_credentials_path
    if cred_path and os.path.isfile(cred_path):
        _storage_client = storage.Client.from_service_account_json(cred_path)
    else:
        _storage_client = storage.Client()
    return _storage_client


def _save_local_sync(content: bytes, object_key: str) -> str:
    dest_path = Path(settings.local_upload_dir) / object_key
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_bytes(content)
    base_url = settings.core_api_public_url.rstrip("/")
    return f"{base_url}/uploads/{object_key}"


def _upload_blob_sync(content: bytes, content_type: str, object_key: str) -> str:
    bucket = _get_client().bucket(settings.gcs_bucket_name)
    blob = bucket.blob(object_key)
    blob.upload_from_string(content, content_type=content_type)
    try:
        blob.make_public()
    except GoogleCloudError as exc:
        # Uniform bucket-level access (UBLA) prohibits object ACLs; bucket IAM governs read.
        logger.debug("Skipping blob.make_public() (UBLA may be active): %s", exc)
    return (
        blob.public_url
        or f"https://storage.googleapis.com/{settings.gcs_bucket_name}/{object_key}"
    )


async def upload_image(content: bytes, content_type: str, object_key: str) -> str:
    """Upload bytes to local storage in dev or GCS in production; return public URL."""
    loop = asyncio.get_running_loop()
    should_use_local = (
        settings.environment == "development" or not settings.gcs_bucket_name
    )
    target_func = _save_local_sync if should_use_local else _upload_blob_sync
    args = (
        (content, object_key)
        if should_use_local
        else (content, content_type, object_key)
    )

    try:
        return await loop.run_in_executor(None, target_func, *args)
    except Exception as exc:
        raise UploadFailedError(f"Failed to upload image: {exc}") from exc
