"""Gemini narration client for Turn Resolution Service.

Real Vertex AI wiring, via the google-genai SDK, authenticated with a Vertex
AI API key (Express Mode) rather than Application Default Credentials. The
only file `ai_orchestrator.py` is permitted to call (CLAUDE.md). The key
(`GEMINI_API_KEY`) is read only from `app.config`.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

import structlog
from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from app.config import settings
from app.exceptions.turn_exceptions import GeminiUnavailableError

logger = structlog.get_logger()

# NOTE: only ever log Gemini call metadata here (model, error type) — never
# the prompt or generated narration text, per the redaction policy in
# docs/logging.md. This is the one place in the codebase handling raw model
# output, so the discipline has to hold here specifically.
EVENT_GEMINI_STREAM_OPENED = "gemini_stream_opened"
EVENT_GEMINI_STREAM_ERROR = "gemini_stream_error"

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


async def generate_with_tools(
    system_instruction: str,
    contents: list[types.Content],
    timeout_seconds: int,
    tools: list[types.Tool] | None,
) -> types.GenerateContentResponse:
    """Single non-streaming turn of a master-mode function-calling loop.

    Non-streaming (not `generate_content_stream`) because the caller
    (ai_orchestrator's tool-calling loop) must inspect `.function_calls`
    before it can decide whether to continue the loop or finish — token-level
    streaming and multi-turn function calling don't compose simply with this
    SDK, so this call returns a complete response each round-trip. The
    fixed generic tools are passed in by the caller (tool_definitions.py) —
    this module stays generic, exactly like stream_narration above.

    Manual function calling only (automatic_function_calling.disable=True):
    the caller — not the SDK — decides whether each proposed mutation is
    valid before continuing the conversation (ADR-4).
    """
    config = _build_generation_config(system_instruction)
    if tools:
        config.tools = tools
        config.automatic_function_calling = types.AutomaticFunctionCallingConfig(
            disable=True
        )
    logger.info(EVENT_GEMINI_STREAM_OPENED, model=settings.gemini_model_name)
    try:
        return await asyncio.wait_for(
            _get_client().aio.models.generate_content(
                model=settings.gemini_model_name, contents=contents, config=config
            ),
            timeout=timeout_seconds,
        )
    except asyncio.TimeoutError as exc:
        logger.warning(EVENT_GEMINI_STREAM_ERROR, error_type="TimeoutError")
        raise GeminiUnavailableError() from exc
    except genai_errors.ServerError as exc:
        logger.warning(EVENT_GEMINI_STREAM_ERROR, error_type="ServerError")
        raise GeminiUnavailableError() from exc
    except genai_errors.ClientError as exc:
        if exc.code == _RATE_LIMIT_STATUS_CODE:
            logger.warning(EVENT_GEMINI_STREAM_ERROR, error_type="RateLimitError")
            raise GeminiUnavailableError() from exc
        raise


async def stream_narration(
    system_instruction: str, prompt: str, timeout_seconds: int
) -> AsyncIterator[str]:
    """Stream narration chunks for the given prompt from Gemini on Vertex AI."""
    config = _build_generation_config(system_instruction)
    logger.info(EVENT_GEMINI_STREAM_OPENED, model=settings.gemini_model_name)
    try:
        async for chunk in _stream_within_timeout(prompt, config, timeout_seconds):
            if chunk.text:
                yield chunk.text
    except asyncio.TimeoutError as exc:
        logger.warning(EVENT_GEMINI_STREAM_ERROR, error_type="TimeoutError")
        raise GeminiUnavailableError() from exc
    except genai_errors.ServerError as exc:
        logger.warning(EVENT_GEMINI_STREAM_ERROR, error_type="ServerError")
        raise GeminiUnavailableError() from exc
    except genai_errors.ClientError as exc:
        if exc.code == _RATE_LIMIT_STATUS_CODE:
            logger.warning(EVENT_GEMINI_STREAM_ERROR, error_type="RateLimitError")
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
