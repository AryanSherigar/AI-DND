"""Upload domain service handling validation and storage delegation."""

import uuid
import wave
from io import BytesIO

from app.exceptions.upload_exceptions import UploadValidationError
from app.integrations import storage_client

MAX_COVER_IMAGE_BYTES = 5 * 1024 * 1024
MAX_SCENARIO_AUDIO_BYTES = 10 * 1024 * 1024
MAX_SCENARIO_AUDIO_SECONDS = 300

ALLOWED_COVER_IMAGE_CONTENT_TYPES: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
}
ALLOWED_SCENARIO_AUDIO_CONTENT_TYPES: dict[str, str] = {
    "audio/mpeg": ".mp3",
    "audio/ogg": ".ogg",
    "audio/wav": ".wav",
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

    async def upload_map_image(self, content: bytes, content_type: str) -> str:
        """Validate and upload a scenario map image, returning its public URL."""
        return await self._upload_with_prefix(content, content_type, "scenario-maps")

    async def upload_scenario_audio(self, content: bytes, content_type: str) -> str:
        """Validate and upload a bounded, creator-selected Dodge audio track."""
        extension = ALLOWED_SCENARIO_AUDIO_CONTENT_TYPES.get(content_type)
        if extension is None:
            raise UploadValidationError("Unsupported audio format. Allowed: MP3, OGG, WAV.")
        if len(content) > MAX_SCENARIO_AUDIO_BYTES:
            raise UploadValidationError("Audio exceeds the 10MB size limit.")
        # WAV duration can be verified with the standard library. MP3/Ogg
        # duration metadata is codec-specific; their strict byte cap prevents
        # unbounded processing without adding a media transcoding dependency.
        if content_type == "audio/wav":
            try:
                with wave.open(BytesIO(content)) as audio:
                    duration = audio.getnframes() / audio.getframerate()
            except (wave.Error, EOFError, ZeroDivisionError) as exc:
                raise UploadValidationError("Invalid WAV audio file.") from exc
            if duration > MAX_SCENARIO_AUDIO_SECONDS:
                raise UploadValidationError("Audio duration exceeds the 5 minute limit.")
        object_key = f"scenario-audio/{uuid.uuid4()}{extension}"
        return await storage_client.upload_image(content, content_type, object_key)
