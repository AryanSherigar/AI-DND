"""Retrieves grounded world facts from the (mocked) memory layer for a turn."""

from app.integrations import memory_client
from app.models.memory import MemoryQueryRequest, MemoryQueryResponse
from app.models.turn import LoadedState, TurnRequest


async def retrieve_context(
    turn_request: TurnRequest, loaded_state: LoadedState
) -> MemoryQueryResponse:
    """Query the memory layer for facts relevant to this turn's action."""
    request = MemoryQueryRequest(
        scenario_id=loaded_state.scenario_id,
        playthrough_id=turn_request.playthrough_id,
        participant_id=turn_request.participant_id,
        query_text=turn_request.action_text,
        checkpoint=loaded_state.checkpoint or "",
        game_state=loaded_state.state,
        as_of_turn=loaded_state.turn_count,
    )
    return await memory_client.query_memory(request)
