"""Generates narration for a turn by calling Gemini.

The only file in the turn pipeline permitted to call `gemini_client` (CLAUDE.md).

Newbie mode streams plain narration (unchanged, below). Master mode
(scenario_snapshot["mode"] == "master") drives Gemini with native
function-calling in a round-trip loop, validating each proposed mutation via
state_validator.py before continuing the same generation (ADR-4).
"""

import time
from collections.abc import AsyncIterator

import structlog
from google.genai import types
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt

from app.config import settings
from app.exceptions.turn_exceptions import (
    GeminiUnavailableError,
    NarrationGenerationError,
)
from app.integrations import gemini_client
from app.models.memory import MemoryQueryResponse
from app.models.tool_call import MasterModeTurnResult, ToolCallLogEntry
from app.models.turn import LoadedState, TurnRequest
from app.turn import tool_definitions
from app.turn.steps import state_validator, tool_handler

logger = structlog.get_logger()

EVENT_GEMINI_CALL_STARTED = "gemini_call_started"
EVENT_GEMINI_CALL_COMPLETED = "gemini_call_completed"
EVENT_GEMINI_CALL_RETRYING = "gemini_call_retrying"
EVENT_NARRATION_GENERATION_DEGRADED = "narration_generation_degraded"
EVENT_TOOL_CALL_CAP_HIT = "tool_call_cap_hit"

_DEGRADED_NARRATION_MESSAGE = (
    "The narrator is taking longer than expected to respond. Please try again."
)
_CHUNK_WORD_GROUP = 6


async def generate_narration(
    turn_request: TurnRequest,
    loaded_state: LoadedState,
    context: MemoryQueryResponse,
    active_instructions: list[str] | None = None,
    result_sink: MasterModeTurnResult | None = None,
) -> AsyncIterator[str]:
    """Stream narration chunks for the turn, retrying transient Gemini failures."""
    if loaded_state.scenario_snapshot.get("mode") == "master":
        async for chunk in _generate_master_mode(
            turn_request, loaded_state, context, active_instructions or [], result_sink
        ):
            yield chunk
        return

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


# --- Master mode: native function-calling round-trip loop -----------------


async def _generate_master_mode(
    turn_request: TurnRequest,
    loaded_state: LoadedState,
    context: MemoryQueryResponse,
    active_instructions: list[str],
    result_sink: MasterModeTurnResult | None,
) -> AsyncIterator[str]:
    system_instruction = _build_master_system_instruction(
        loaded_state, active_instructions, context
    )
    prompt = _build_prompt(turn_request, loaded_state, context)
    contents: list[types.Content] = [
        types.Content(role="user", parts=[types.Part(text=prompt)])
    ]
    working_state = (
        dict(result_sink.final_state) if result_sink else dict(loaded_state.state)
    )
    scenario_snapshot = loaded_state.scenario_snapshot

    start = time.monotonic()
    round_trips = 0
    final_text = ""
    try:
        while True:
            include_tools = round_trips < settings.tool_call_max_round_trips
            if not include_tools and round_trips == settings.tool_call_max_round_trips:
                logger.warning(EVENT_TOOL_CALL_CAP_HIT, round_trips=round_trips)

            response = await _tool_call_with_retries(
                system_instruction, contents, include_tools
            )
            function_calls = response.function_calls or []
            if not function_calls:
                final_text = response.text or ""
                break

            working_state, contents = _apply_function_calls(
                function_calls,
                response,
                contents,
                working_state,
                scenario_snapshot,
                result_sink,
            )
            round_trips += 1
    except GeminiUnavailableError:
        logger.warning(
            EVENT_NARRATION_GENERATION_DEGRADED,
            playthrough_id=str(turn_request.playthrough_id),
        )
        yield _DEGRADED_NARRATION_MESSAGE
        raise NarrationGenerationError() from None

    if result_sink is not None:
        result_sink.final_state = working_state

    logger.info(
        EVENT_GEMINI_CALL_COMPLETED,
        model=settings.gemini_model_name,
        round_trips=round_trips,
        duration_ms=(time.monotonic() - start) * 1000,
    )
    for chunk in _chunk_text(final_text):
        yield chunk


async def _tool_call_with_retries(
    system_instruction: str, contents: list[types.Content], include_tools: bool
) -> types.GenerateContentResponse:
    tools = [tool_definitions.MASTER_MODE_TOOLS] if include_tools else None
    retrying = AsyncRetrying(
        stop=stop_after_attempt(settings.gemini_max_retries + 1),
        retry=retry_if_exception_type(GeminiUnavailableError),
        reraise=True,
    )
    response: types.GenerateContentResponse | None = None
    async for attempt in retrying:
        if attempt.retry_state.attempt_number > 1:
            logger.warning(
                EVENT_GEMINI_CALL_RETRYING, attempt=attempt.retry_state.attempt_number
            )
        with attempt:
            response = await gemini_client.generate_with_tools(
                system_instruction, contents, settings.gemini_timeout_seconds, tools
            )
    assert response is not None  # AsyncRetrying always yields or raises
    return response


def _apply_function_calls(
    function_calls: list[types.FunctionCall],
    response: types.GenerateContentResponse,
    contents: list[types.Content],
    working_state: dict[str, object],
    scenario_snapshot: dict[str, object],
    result_sink: MasterModeTurnResult | None,
) -> tuple[dict[str, object], list[types.Content]]:
    """Validate each proposed mutation, apply the valid ones, and build the
    function-response turn to append (ADR-4: rejected within the same call)."""
    func_call_content = response.candidates[0].content  # type: ignore[union-attr, index]
    response_parts: list[types.Part] = []

    for call in function_calls:
        mutation = tool_handler.prepare_mutation(call)
        if mutation.op == "roll":
            result = tool_handler.execute_roll_dice(
                mutation.sides or 20, mutation.modifier or 0
            )
            _log_tool_call(result_sink, call, result, is_valid=True)
            response_parts.append(
                types.Part.from_function_response(name=call.name or "", response=result)
            )
            continue

        validation = state_validator.validate_mutation(
            mutation, working_state, scenario_snapshot
        )
        if validation.is_valid:
            working_state = validation.updated_state or working_state
            if mutation.path and result_sink is not None:
                result_sink.mutated_paths.append(mutation.path)
            _log_tool_call(result_sink, call, {"success": True}, is_valid=True)
            response_parts.append(
                types.Part.from_function_response(
                    name=call.name or "", response={"success": True}
                )
            )
        else:
            _log_tool_call(
                result_sink, call, {"error": validation.error_message}, is_valid=False
            )
            response_parts.append(
                types.Part.from_function_response(
                    name=call.name or "", response={"error": validation.error_message}
                )
            )

    new_contents = [
        *contents,
        func_call_content,
        types.Content(role="user", parts=response_parts),
    ]
    return working_state, new_contents


def _log_tool_call(
    result_sink: MasterModeTurnResult | None,
    call: types.FunctionCall,
    result: dict[str, object],
    is_valid: bool,
) -> None:
    if result_sink is None:
        return
    result_sink.tool_calls.append(
        ToolCallLogEntry(
            tool_name=call.name or "",
            arguments=dict(call.args or {}),
            result=result,
            is_valid=is_valid,
        )
    )


def _build_master_system_instruction(
    loaded_state: LoadedState,
    active_instructions: list[str],
    context: MemoryQueryResponse,
) -> str:
    snapshot = loaded_state.scenario_snapshot
    persona = _checkpoint_persona(snapshot, loaded_state.checkpoint)
    entities = snapshot.get("entities", []) or []
    known_entity_ids = {
        str(e.get("entity_id")) for e in entities if isinstance(e, dict)
    }
    on_scene_ids = _on_scene_entity_ids(loaded_state.state, context, known_entity_ids)
    entity_instructions = [
        str(e.get("narrator_instruction"))
        for e in entities
        if isinstance(e, dict)
        and str(e.get("entity_id")) in on_scene_ids
        and e.get("narrator_instruction")
    ]
    invariant_texts = [
        str(inv.get("narrator_text"))
        for inv in snapshot.get("rule_invariants", []) or []
        if isinstance(inv, dict) and inv.get("narrator_text")
    ]
    parts = [persona, *active_instructions, *entity_instructions, *invariant_texts]
    return "\n".join(p for p in parts if p)


def _checkpoint_persona(snapshot: dict[str, object], checkpoint: str | None) -> str:
    """narrator_persona, overridden per-checkpoint if the creator authored a
    checkpoint entry with a narrator_persona_override (reuses the existing
    checkpoints JSONB shape — no new column needed)."""
    base = str(snapshot.get("narrator_persona", "") or "")
    if not checkpoint:
        return base
    for entry in snapshot.get("checkpoints", []) or []:
        if isinstance(entry, dict) and entry.get("name") == checkpoint:
            override = entry.get("narrator_persona_override")
            if override:
                return str(override)
    return base


def _on_scene_entity_ids(
    state: dict[str, object], context: MemoryQueryResponse, known_entity_ids: set[str]
) -> set[str]:
    """Entities referenced in this turn's retrieved facts, or pointed at by
    any entity_ref-shaped value currently in state (master-mode-turn-pipeline
    .spec.md §3.4's heuristic)."""
    ids: set[str] = set()
    for fact in context.facts:
        if fact.subject in known_entity_ids:
            ids.add(fact.subject)
        if fact.object in known_entity_ids:
            ids.add(fact.object)
    ids |= _find_entity_ref_values(state, known_entity_ids)
    return ids


def _find_entity_ref_values(node: object, known_entity_ids: set[str]) -> set[str]:
    if isinstance(node, str):
        return {node} if node in known_entity_ids else set()
    if isinstance(node, dict):
        found: set[str] = set()
        for value in node.values():
            found |= _find_entity_ref_values(value, known_entity_ids)
        return found
    if isinstance(node, list):
        found = set()
        for item in node:
            found |= _find_entity_ref_values(item, known_entity_ids)
        return found
    return set()


def _chunk_text(text: str) -> list[str]:
    """Split a complete master-mode narration into pseudo-streamed pieces.

    Master mode uses non-streaming Gemini calls — the tool-calling loop must
    inspect function_calls before deciding whether to continue, which
    doesn't compose with true token-level streaming in this SDK. Chunking
    the final text preserves the AsyncIterator[str] interface
    response_streamer expects and still delivers narration progressively to
    the client, just not at Gemini's own token granularity the way newbie
    mode's stream_narration does.
    """
    if not text:
        return []
    words = text.split(" ")
    chunks = []
    for i in range(0, len(words), _CHUNK_WORD_GROUP):
        group = words[i : i + _CHUNK_WORD_GROUP]
        suffix = " " if i + _CHUNK_WORD_GROUP < len(words) else ""
        chunks.append(" ".join(group) + suffix)
    return chunks
