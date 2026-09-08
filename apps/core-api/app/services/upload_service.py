"""Upload domain service handling validation and storage delegation."""

import uuid
import wave
from io import BytesIO

from app.config import settings
from app.exceptions.upload_exceptions import UploadValidationError
from app.integrations import image_gen_client, storage_client
from app.models.image_generation import CoverImageGenerationRequest

MAX_COVER_IMAGE_BYTES = 5 * 1024 * 1024
MAX_SCENARIO_AUDIO_BYTES = 10 * 1024 * 1024
MAX_SCENARIO_AUDIO_SECONDS = 300

_GENERATED_COVER_IMAGE_CONTENT_TYPE = "image/png"

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

_IMAGE_MAGIC_BYTES: dict[str, tuple[bytes, ...]] = {
    "image/jpeg": (b"\xff\xd8\xff",),
    "image/png": (b"\x89PNG\r\n\x1a\n",),
    "image/webp": (b"RIFF",),
}


def _has_valid_image_signature(content: bytes, content_type: str) -> bool:
    """Check the file's leading bytes match its declared image content type,
    so a client can't upload arbitrary content (e.g. an HTML/SVG payload)
    behind a spoofed Content-Type header."""
    signatures = _IMAGE_MAGIC_BYTES.get(content_type, ())
    if not any(content.startswith(sig) for sig in signatures):
        return False
    if content_type == "image/webp":
        return content[8:12] == b"WEBP"
    return True


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
        if not _has_valid_image_signature(content, content_type):
            raise UploadValidationError(
                "File contents do not match the declared image format."
            )

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
            raise UploadValidationError(
                "Unsupported audio format. Allowed: MP3, OGG, WAV."
            )
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
                raise UploadValidationError(
                    "Audio duration exceeds the 5 minute limit."
                )
        object_key = f"scenario-audio/{uuid.uuid4()}{extension}"
        return await storage_client.upload_image(content, content_type, object_key)

    async def generate_and_upload_cover_image(
        self, request: CoverImageGenerationRequest
    ) -> str:
        """Generate a scenario cover image with AI and upload it, returning its public URL."""
        prompt = self._build_cover_prompt(request)
        image_bytes = await image_gen_client.generate_image(
            prompt, settings.imagen_timeout_seconds
        )
        return await self._upload_with_prefix(
            image_bytes, _GENERATED_COVER_IMAGE_CONTENT_TYPE, "scenario-covers"
        )

    def _build_cover_prompt(self, request: CoverImageGenerationRequest) -> str:
        """Compose a text-to-image prompt from scenario metadata."""
        parts = [
            f"A cinematic cover illustration for a tabletop RPG scenario titled '{request.title}'."
        ]
        if request.genre_tags:
            parts.append(f"Genre: {', '.join(request.genre_tags)}.")
        if request.opening_scene:
            parts.append(f"Opening scene: {request.opening_scene}")
        parts.append("No text or lettering in the image.")
        return " ".join(parts)
