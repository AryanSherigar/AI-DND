"""Upload domain service handling validation and storage delegation."""

import uuid

from app.exceptions.upload_exceptions import UploadValidationError
from app.integrations import storage_client

MAX_COVER_IMAGE_BYTES = 5 * 1024 * 1024

ALLOWED_COVER_IMAGE_CONTENT_TYPES: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}


class UploadService:
    """Service handling file upload validation and object key generation."""

    async def _upload_with_prefix(
        self, content: bytes, content_type: str, prefix: str
    ) -> str:
        """Validate and upload an image under the specified prefix directory."""
        extension = ALLOWED_COVER_IMAGE_CONTENT_TYPES.get(content_type)
        if extension is None:
            raise UploadValidationError(
                "Unsupported image format. Allowed: JPEG, PNG, WebP."
            )
        if len(content) > MAX_COVER_IMAGE_BYTES:
            raise UploadValidationError("Image exceeds the 5MB size limit.")

        object_key = f"{prefix}/{uuid.uuid4()}{extension}"
        return await storage_client.upload_image(content, content_type, object_key)

    async def upload_cover_image(self, content: bytes, content_type: str) -> str:
        """Validate and upload a scenario cover image, returning its public URL."""
        return await self._upload_with_prefix(content, content_type, "scenario-covers")

    async def upload_avatar(self, content: bytes, content_type: str) -> str:
        """Validate and upload a user avatar image, returning its public URL."""
        return await self._upload_with_prefix(content, content_type, "avatars")

    async def upload_banner(self, content: bytes, content_type: str) -> str:
        """Validate and upload a user profile banner image, returning its public URL."""
        return await self._upload_with_prefix(content, content_type, "banners")
