"""Cloud storage client for Turn Resolution Service.

Only module in this service that talks to Google Cloud Storage. TRS gets its
own copy of core-api's storage_client.py rather than calling core-api's
upload endpoint mid-turn — that would add a blocking inter-service HTTP hop
to an already-synchronous pipeline. Both services write into the same
physical bucket (same GCS_BUCKET_NAME) in production; object storage isn't a
per-service-owned boundary the way the database is.
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import structlog
from app.config import settings
from app.exceptions.turn_exceptions import SceneImageGenerationError
from google.cloud import storage
from google.cloud.exceptions import GoogleCloudError

logger = structlog.get_logger()

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
    return f"/uploads/{object_key}"


def _upload_blob_sync(content: bytes, content_type: str, object_key: str) -> str:
    bucket = _get_client().bucket(settings.gcs_bucket_name)
    blob = bucket.blob(object_key)
    blob.upload_from_string(content, content_type=content_type)
    try:
        blob.make_public()
    except GoogleCloudError as exc:
        # Uniform bucket-level access (UBLA) prohibits object ACLs; bucket IAM governs read.
        logger.debug(
            "skipping_make_public", reason="UBLA may be active", error=str(exc)
        )
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
        raise SceneImageGenerationError(f"Failed to upload scene image: {exc}") from exc
