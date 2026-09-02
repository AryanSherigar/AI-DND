"""Gemini narration client for Turn Resolution Service.

Real Vertex AI wiring, via the google-genai SDK, authenticated with a Vertex
AI API key (Express Mode) rather than Application Default Credentials. The
only file `ai_orchestrator.py` is permitted to call (CLAUDE.md). The key
(`GEMINI_API_KEY`) is read only from `app.config`.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.config import settings
from app.exceptions.turn_exceptions import GeminiUnavailableError

_HARM_CATEGORIES: list[types.HarmCategory] = [
    types.HarmCategory.HARM_CATEGORY_HATE_SPEECH,
    types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
    types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
    types.HarmCategory.HARM_CATEGORY_HARASSMENT,
]

_SAFETY_SETTINGS: list[types.SafetySetting] = [
    types.SafetySetting(
        category=category, threshold=types.HarmBlockThreshold.BLOCK_ONLY_HIGH
    )
    for category in _HARM_CATEGORIES
]

_client: genai.Client | None = None

_RATE_LIMIT_STATUS_CODE = 429


def _get_client() -> genai.Client:
    """Build the Vertex AI (API key / Express Mode) client lazily and cache it.

    Constructing genai.Client(...) validates the key eagerly — doing that at
    import time would make importing this module fail in any environment
    without GEMINI_API_KEY set (tests, CI).
    """
    global _client
    if _client is None:
        _client = genai.Client(vertexai=True, api_key=settings.gemini_api_key)
    return _client


async def stream_narration(
    system_instruction: str, prompt: str, timeout_seconds: int
) -> AsyncIterator[str]:
    """Stream narration chunks for the given prompt from Gemini on Vertex AI."""
    config = _build_generation_config(system_instruction)
    try:
        async for chunk in _stream_within_timeout(prompt, config, timeout_seconds):
            if chunk.text:
                yield chunk.text
    except asyncio.TimeoutError as exc:
        raise GeminiUnavailableError() from exc
    except genai_errors.ServerError as exc:
        raise GeminiUnavailableError() from exc
    except genai_errors.ClientError as exc:
        if exc.code == _RATE_LIMIT_STATUS_CODE:
            raise GeminiUnavailableError() from exc
        raise


async def _stream_within_timeout(
    prompt: str, config: types.GenerateContentConfig, timeout_seconds: int
) -> AsyncIterator[types.GenerateContentResponse]:
    """Yield chunks as they arrive, bounding each chunk's wait (never buffers the stream)."""
    stream = await _get_client().aio.models.generate_content_stream(
        model=settings.gemini_model_name, contents=prompt, config=config
    )
    stream_iterator = stream.__aiter__()
    while True:
        try:
            chunk = await asyncio.wait_for(
                stream_iterator.__anext__(), timeout=timeout_seconds
            )
        except StopAsyncIteration:
            return
        yield chunk


def _build_generation_config(system_instruction: str) -> types.GenerateContentConfig:
    return types.GenerateContentConfig(
        system_instruction=system_instruction,
        temperature=settings.gemini_temperature,
        max_output_tokens=settings.gemini_max_output_tokens,
        top_p=settings.gemini_top_p,
        safety_settings=_SAFETY_SETTINGS,
    )
