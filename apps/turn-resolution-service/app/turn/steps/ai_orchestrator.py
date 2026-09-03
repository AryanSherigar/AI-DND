"""Generates narration for a turn by calling Gemini.

The only file in the turn pipeline permitted to call `gemini_client` (CLAUDE.md).
"""

import time
from collections.abc import AsyncIterator

import structlog
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt

from app.config import settings
from app.exceptions.turn_exceptions import (
    GeminiUnavailableError,
    NarrationGenerationError,
)
from app.integrations import gemini_client
from app.models.memory import MemoryQueryResponse
from app.models.turn import LoadedState, TurnRequest

logger = structlog.get_logger()

EVENT_GEMINI_CALL_STARTED = "gemini_call_started"
EVENT_GEMINI_CALL_COMPLETED = "gemini_call_completed"
EVENT_GEMINI_CALL_RETRYING = "gemini_call_retrying"
EVENT_NARRATION_GENERATION_DEGRADED = "narration_generation_degraded"

_DEGRADED_NARRATION_MESSAGE = (
    "The narrator is taking longer than expected to respond. Please try again."
)


async def generate_narration(
    turn_request: TurnRequest,
    loaded_state: LoadedState,
    context: MemoryQueryResponse,
) -> AsyncIterator[str]:
    """Stream narration chunks for the turn, retrying transient Gemini failures."""
    system_instruction = _build_system_instruction(loaded_state)
    prompt = _build_prompt(turn_request, loaded_state, context)
    start = time.monotonic()
    chunk_count = 0
    logger.info(EVENT_GEMINI_CALL_STARTED, model=settings.gemini_model_name)
    try:
        async for chunk in _stream_with_retries(system_instruction, prompt):
            chunk_count += 1
            yield chunk
    except GeminiUnavailableError:
        logger.warning(
            EVENT_NARRATION_GENERATION_DEGRADED,
            playthrough_id=str(turn_request.playthrough_id),
        )
        yield _DEGRADED_NARRATION_MESSAGE
        raise NarrationGenerationError() from None
    else:
        logger.info(
            EVENT_GEMINI_CALL_COMPLETED,
            model=settings.gemini_model_name,
            chunk_count=chunk_count,
            duration_ms=(time.monotonic() - start) * 1000,
        )


async def _stream_with_retries(
    system_instruction: str, prompt: str
) -> AsyncIterator[str]:
    retrying = AsyncRetrying(
        stop=stop_after_attempt(settings.gemini_max_retries + 1),
        retry=retry_if_exception_type(GeminiUnavailableError),
        reraise=True,
    )
    async for attempt in retrying:
        if attempt.retry_state.attempt_number > 1:
            logger.warning(
                EVENT_GEMINI_CALL_RETRYING,
                attempt=attempt.retry_state.attempt_number,
            )
        with attempt:
            async for chunk in gemini_client.stream_narration(
                system_instruction, prompt, settings.gemini_timeout_seconds
            ):
                yield chunk


def _build_system_instruction(loaded_state: LoadedState) -> str:
    return str(loaded_state.scenario_snapshot.get("narrator_persona", ""))


def _build_prompt(
    turn_request: TurnRequest, loaded_state: LoadedState, context: MemoryQueryResponse
) -> str:
    snapshot = loaded_state.scenario_snapshot
    history = _recent_history(loaded_state.state)
    facts_block = _build_facts_block(context)
    return (
        f"World: {snapshot.get('world_data', '')}\n\n"
        f"{facts_block}"
        f"Recent turns: {history}\n\n"
        f"Player action: {turn_request.action_text}"
    )


def _build_facts_block(context: MemoryQueryResponse) -> str:
    """Render retrieved facts as a prompt block, or omit it entirely on abstention."""
    if context.abstained or not context.facts:
        return ""
    facts_text = "; ".join(
        f"{fact.subject} {fact.predicate} {fact.object}" for fact in context.facts
    )
    return f"Known world facts: {facts_text}\n\n"


def _recent_history(state: dict[str, object]) -> list[object]:
    narrative = state.get("narrative", {})
    turns_so_far = narrative.get("turns_so_far", [])
    return turns_so_far[-settings.turn_history_window_size :]
