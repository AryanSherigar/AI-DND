"""Lyria (Vertex AI) music generation client for Core API.

Same approved exception as image_gen_client.py: CLAUDE.md restricts AI calls
to the turn resolution service, but music generation is a Studio-only,
async-job, user-initiated authoring action with no relation to the turn
pipeline. The only file permitted to call this module is
app/services/music_service.py.

Crossfade guardrail: every generated track is forced into the same key (D
minor) and the mood's own target BPM range, with the requested duration
rounded to a whole number of bars at that BPM. Key alone does not prevent an
audible seam at the loop point — bar-alignment does; cross-mood tempo
differences are tolerated and masked by the frontend's ~4s gain crossfade,
not solved here.

NOTE: the exact google-genai SDK method/param names for Lyria music
generation must be confirmed against the pinned SDK version before this
goes live — the shape below mirrors image_gen_client.py's
generate_images call as the closest known-working pattern.
"""

from __future__ import annotations

import asyncio

import structlog
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.config import settings
from app.exceptions.music_exceptions import MusicGenerationError

logger = structlog.get_logger()

GENERATION_KEY = "D minor"

BEATS_PER_BAR = 4
SECONDS_PER_MINUTE = 60

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


class GeneratedTrackMetadata:
    """Metadata about a generated track, alongside its audio bytes."""

    def __init__(self, key: str, bpm: int, duration_seconds: float) -> None:
        self.key = key
        self.bpm = bpm
        self.duration_seconds = duration_seconds


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


def _bar_aligned_duration(requested_seconds: int, bpm: int) -> float:
    """Round a requested duration to the nearest whole number of 4-beat bars.

    A partial bar at the loop point is what causes an audible click/pop on
    crossfade-loop; rounding to a bar boundary at the track's own tempo
    removes that seam regardless of key.
    """
    seconds_per_bar = BEATS_PER_BAR * SECONDS_PER_MINUTE / bpm
    bars = max(1, round(requested_seconds / seconds_per_bar))
    return round(bars * seconds_per_bar, 2)


def _build_prompt(prompt: str, mood: str, bpm: int) -> str:
    """Append the fixed crossfade constraints to the creator's free-text prompt."""
    return (
        f"{prompt} Key: {GENERATION_KEY}. Tempo: {bpm} BPM. "
        "Seamlessly loopable ambient game music, no fade-in or fade-out at "
        "the start or end of the audio."
    )


async def generate_music(
    prompt: str, mood: str, duration_seconds: int, timeout_seconds: int
) -> tuple[bytes, GeneratedTrackMetadata]:
    """Generate a single loopable track from a text prompt via Lyria on Vertex AI."""
    bpm = _target_bpm(mood)
    aligned_duration = _bar_aligned_duration(duration_seconds, bpm)
    full_prompt = _build_prompt(prompt, mood, bpm)

    logger.info(
        EVENT_MUSIC_GENERATION_STARTED,
        model=settings.lyria_model_name,
        mood=mood,
        bpm=bpm,
        duration_seconds=aligned_duration,
        prompt_length=len(prompt),
    )
    try:
        response = await asyncio.wait_for(
            _get_client().aio.models.generate_music(
                model=settings.lyria_model_name,
                prompt=full_prompt,
                config=types.GenerateMusicConfig(
                    duration_seconds=aligned_duration,
                ),
            ),
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

    if not response.generated_tracks:
        raise MusicGenerationError("Music generation returned no results")
    audio_bytes = response.generated_tracks[0].audio.audio_bytes
    if audio_bytes is None:
        raise MusicGenerationError("Music generation returned no audio bytes")

    return audio_bytes, GeneratedTrackMetadata(
        key=GENERATION_KEY, bpm=bpm, duration_seconds=aligned_duration
    )
