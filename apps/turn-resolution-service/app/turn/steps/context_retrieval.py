"""Retrieves grounded world facts from the (mocked) memory layer for a turn."""

import time

import structlog

from app.integrations import memory_client
from app.models.memory import MemoryQueryRequest, MemoryQueryResponse
from app.models.turn import LoadedState, TurnRequest

logger = structlog.get_logger()

EVENT_TURN_STEP_COMPLETED = "turn_step_completed"
STEP_NAME = "context_retrieval"


async def retrieve_context(
    turn_request: TurnRequest, loaded_state: LoadedState
) -> MemoryQueryResponse:
    """Query the memory layer for facts relevant to this turn's action."""
    start = time.monotonic()
    request = MemoryQueryRequest(
        scenario_id=loaded_state.scenario_id,
        playthrough_id=turn_request.playthrough_id,
        participant_id=turn_request.participant_id,
        query_text=turn_request.action_text,
        checkpoint=loaded_state.checkpoint or "",
        game_state=loaded_state.state,
        as_of_turn=loaded_state.turn_count,
    )
    response = await memory_client.query_memory(request)
    logger.info(
        EVENT_TURN_STEP_COMPLETED,
        step_name=STEP_NAME,
        facts_returned=len(response.facts),
        abstained=response.abstained,
        duration_ms=(time.monotonic() - start) * 1000,
    )
    return response
