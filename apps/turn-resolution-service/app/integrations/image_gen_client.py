"""Imagen (Vertex AI) image generation client for Turn Resolution Service.

CLAUDE.md restricts AI calls to this service, but the equivalent client in
Core API (used for Studio cover image generation) is an intentional, approved
exception documented there — Studio cover generation is a synchronous,
user-initiated action unrelated to the turn pipeline. TRS's own client below
follows the standard rule: only app/turn/steps/scene_image_generator.py is
permitted to call this module.

Authenticated with a Vertex AI API key (Express Mode), the same pattern
gemini_client.py in this service uses.
"""

from __future__ import annotations

import asyncio

import structlog
from app.config import settings
from app.exceptions.turn_exceptions import SceneImageGenerationError
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

logger = structlog.get_logger()

# NOTE: only ever log image generation call metadata here (model, duration,
# prompt length) — never the prompt text itself, per the redaction policy
# gemini_client.py documents for narration.
EVENT_IMAGE_GENERATION_STARTED = "scene_image_generation_started"
EVENT_IMAGE_GENERATION_ERROR = "scene_image_generation_error"

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
        raise SceneImageGenerationError() from exc
    except genai_errors.ServerError as exc:
        logger.warning(EVENT_IMAGE_GENERATION_ERROR, error_type="ServerError")
        raise SceneImageGenerationError() from exc
    except genai_errors.ClientError as exc:
        if exc.code == _RATE_LIMIT_STATUS_CODE:
            logger.warning(EVENT_IMAGE_GENERATION_ERROR, error_type="RateLimitError")
            raise SceneImageGenerationError() from exc
        raise

    if not response.generated_images:
        raise SceneImageGenerationError("Image generation returned no results")
    image_bytes = response.generated_images[0].image.image_bytes
    if image_bytes is None:
        raise SceneImageGenerationError("Image generation returned no image bytes")
    return image_bytes
