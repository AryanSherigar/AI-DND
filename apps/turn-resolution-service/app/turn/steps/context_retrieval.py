"""Retrieves grounded world facts from the memory layer for a turn."""

import time

import structlog

from app.integrations import memory_client
from app.models.memory import Fact, MemoryQueryRequest, MemoryQueryResponse
from app.models.turn import LoadedState, TurnRequest
from app.turn import expression_evaluator

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
    revealed_fact_ids = {
        str(fid) for fid in loaded_state.state.get("revealed_facts", [])
    }
    response.facts = _filter_hidden(response.facts, revealed_fact_ids)
    response.facts = _filter_when_active(response.facts, loaded_state.state)
    logger.info(
        EVENT_TURN_STEP_COMPLETED,
        step_name=STEP_NAME,
        facts_returned=len(response.facts),
        abstained=response.abstained,
        duration_ms=(time.monotonic() - start) * 1000,
    )
    return response


def _filter_hidden(facts: list[Fact], revealed_fact_ids: set[str]) -> list[Fact]:
    """Drop facts flagged hidden unless this playthrough has revealed them."""
    return [f for f in facts if not f.hidden or str(f.fact_id) in revealed_fact_ids]


def _filter_when_active(facts: list[Fact], game_state: dict[str, object]) -> list[Fact]:
    """Drop facts whose when_active expression doesn't currently hold."""
    return [
        f
        for f in facts
        if f.when_active is None
        or expression_evaluator.evaluate(f.when_active, game_state)
    ]
