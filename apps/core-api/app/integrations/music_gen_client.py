"""Lyria (Vertex AI) music generation client for Core API.

Same approved exception as image_gen_client.py: CLAUDE.md restricts AI calls
to the turn resolution service, but music generation is a Studio-only,
async-job, user-initiated authoring action with no relation to the turn
pipeline. The only file permitted to call this module is
app/services/music_service.py.

Crossfade guardrail: every generated track is forced into the same key (D
minor) and the mood's own target BPM, via the text prompt. Cross-mood tempo
differences are tolerated and masked by the frontend's ~4s gain crossfade.

NOTE: Lyria on Vertex AI has no batch/offline endpoint in the google-genai
SDK (only a WebSocket-based Live Music session, which the SDK itself
refuses to open in Vertex AI mode). The real integration is a raw
`publishers/google/models/{model}:predict` REST call, confirmed against
Google's Lyria API reference. This module issues that call through
`genai.Client`'s own internal `_api_client.async_request`, the same
authenticated transport `image_gen_client.py` already uses, rather than
reimplementing auth from scratch.

NOTE: Lyria-002 has no duration parameter — every call returns a fixed clip
(up to ~32.8s). The caller cannot request a specific length.
"""

from __future__ import annotations

import asyncio
import base64
import json

import structlog
from google import genai
from google.genai import errors as genai_errors

from app.config import settings
from app.exceptions.music_exceptions import MusicGenerationError

logger = structlog.get_logger()

GENERATION_KEY = "D minor"

MOOD_BPM_RANGES: dict[str, tuple[int, int]] = {
    "peaceful": (55, 70),
    "melancholy": (55, 70),
    "mystery": (70, 85),
    "tension": (90, 105),
    "triumph": (100, 120),
    "combat": (110, 130),
}

EVENT_MUSIC_GENERATION_STARTED = "music_generation_started"
EVENT_MUSIC_GENERATION_ERROR = "music_generation_error"

_client: genai.Client | None = None

_RATE_LIMIT_STATUS_CODE = 429
_PREDICT_SAMPLE_COUNT = 1


class GeneratedTrackMetadata:
    """Metadata about a generated track, alongside its audio bytes."""

    def __init__(self, key: str, bpm: int) -> None:
        self.key = key
        self.bpm = bpm


def _get_client() -> genai.Client:
    """Build the Vertex AI (API key / Express Mode) client lazily and cache it."""
    global _client
    if _client is None:
        _client = genai.Client(vertexai=True, api_key=settings.gemini_api_key)
    return _client


def _target_bpm(mood: str) -> int:
    """Pick the midpoint of the mood's target BPM range."""
    low, high = MOOD_BPM_RANGES[mood]
    return (low + high) // 2


def _build_prompt(prompt: str, mood: str, bpm: int) -> str:
    """Append the fixed crossfade constraints to the creator's free-text prompt."""
    return (
        f"{prompt} Key: {GENERATION_KEY}. Tempo: {bpm} BPM. "
        "Seamlessly loopable ambient game music, no fade-in or fade-out at "
        "the start or end of the audio."
    )


async def generate_music(
    prompt: str, mood: str, timeout_seconds: int
) -> tuple[bytes, GeneratedTrackMetadata]:
    """Generate a single loopable track from a text prompt via Lyria on Vertex AI."""
    bpm = _target_bpm(mood)
    full_prompt = _build_prompt(prompt, mood, bpm)
    path = f"publishers/google/models/{settings.lyria_model_name}:predict"
    request_dict = {
        "instances": [{"prompt": full_prompt}],
        "parameters": {"sample_count": _PREDICT_SAMPLE_COUNT},
    }

    logger.info(
        EVENT_MUSIC_GENERATION_STARTED,
        model=settings.lyria_model_name,
        mood=mood,
        bpm=bpm,
        prompt_length=len(prompt),
    )
    try:
        response = await asyncio.wait_for(
            _get_client()._api_client.async_request("post", path, request_dict),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError as exc:
        logger.warning(EVENT_MUSIC_GENERATION_ERROR, error_type="TimeoutError")
        raise MusicGenerationError() from exc
    except genai_errors.ServerError as exc:
        logger.warning(EVENT_MUSIC_GENERATION_ERROR, error_type="ServerError")
        raise MusicGenerationError() from exc
    except genai_errors.ClientError as exc:
        if exc.code == _RATE_LIMIT_STATUS_CODE:
            logger.warning(EVENT_MUSIC_GENERATION_ERROR, error_type="RateLimitError")
            raise MusicGenerationError() from exc
        raise

    audio_bytes = _extract_audio_bytes(response.body)
    return audio_bytes, GeneratedTrackMetadata(key=GENERATION_KEY, bpm=bpm)


def _extract_audio_bytes(response_body: str) -> bytes:
    """Pull the first prediction's base64-encoded WAV audio out of a predict response."""
    predictions = (
        json.loads(response_body).get("predictions") if response_body else None
    )
    if not predictions:
        raise MusicGenerationError("Music generation returned no results")
    audio_content = predictions[0].get("bytesBase64Encoded")
    if not audio_content:
        raise MusicGenerationError("Music generation returned no audio bytes")
    return base64.b64decode(audio_content)
