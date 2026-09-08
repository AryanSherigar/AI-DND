"""Imagen (Vertex AI) image generation client for Core API.

CLAUDE.md restricts AI calls to the turn resolution service, but cover
image generation is a Studio-only, synchronous, user-initiated action with
no relation to the turn pipeline — routing it through TRS would add a
needless service hop. Core API and TRS therefore each own an independent
image_gen_client.py; this is an intentional, approved exception, not an
oversight. The only file permitted to call this module is
app/services/upload_service.py.

Authenticated with a Vertex AI API key (Express Mode), the same pattern
apps/turn-resolution-service/app/integrations/gemini_client.py uses.
"""

from __future__ import annotations

import asyncio

import structlog
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.config import settings
from app.exceptions.upload_exceptions import ImageGenerationError

logger = structlog.get_logger()

# NOTE: only ever log image generation call metadata here (model, duration,
# prompt length) — never the prompt text itself, per the same redaction
# discipline gemini_client.py documents in TRS.
EVENT_IMAGE_GENERATION_STARTED = "image_generation_started"
EVENT_IMAGE_GENERATION_ERROR = "image_generation_error"

_client: genai.Client | None = None

_RATE_LIMIT_STATUS_CODE = 429


def _get_client() -> genai.Client:
    """Build the Vertex AI (API key / Express Mode) client lazily and cache it."""
    global _client
    if _client is None:
        _client = genai.Client(vertexai=True, api_key=settings.gemini_api_key)
    return _client


async def generate_image(prompt: str, timeout_seconds: int) -> bytes:
    """Generate a single image from a text prompt via Imagen on Vertex AI."""
    logger.info(
        EVENT_IMAGE_GENERATION_STARTED,
        model=settings.imagen_model_name,
        prompt_length=len(prompt),
    )
    try:
        response = await asyncio.wait_for(
            _get_client().aio.models.generate_images(
                model=settings.imagen_model_name,
                prompt=prompt,
                config=types.GenerateImagesConfig(number_of_images=1),
            ),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError as exc:
        logger.warning(EVENT_IMAGE_GENERATION_ERROR, error_type="TimeoutError")
        raise ImageGenerationError() from exc
    except genai_errors.ServerError as exc:
        logger.warning(EVENT_IMAGE_GENERATION_ERROR, error_type="ServerError")
        raise ImageGenerationError() from exc
    except genai_errors.ClientError as exc:
        if exc.code == _RATE_LIMIT_STATUS_CODE:
            logger.warning(EVENT_IMAGE_GENERATION_ERROR, error_type="RateLimitError")
            raise ImageGenerationError() from exc
        raise

    if not response.generated_images:
        raise ImageGenerationError("Image generation returned no results")
    image_bytes = response.generated_images[0].image.image_bytes
    if image_bytes is None:
        raise ImageGenerationError("Image generation returned no image bytes")
    return image_bytes
