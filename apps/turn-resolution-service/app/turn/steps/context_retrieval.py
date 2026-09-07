"""Retrieves grounded world facts from the memory layer for a turn.

Failures here are caught, logged, and degraded gracefully to an abstained
empty response: per RFC ADR-5, memory layer failures must never block
gameplay.
"""

import time

import structlog

from app.exceptions.turn_exceptions import MemoryLayerUnavailableError
from app.integrations import memory_client
from app.models.memory import Fact, MemoryQueryRequest, MemoryQueryResponse
from app.models.turn import LoadedState, TurnRequest
from app.turn import expression_evaluator

logger = structlog.get_logger()

EVENT_TURN_STEP_COMPLETED = "turn_step_completed"
EVENT_CONTEXT_RETRIEVAL_DEGRADED = "context_retrieval_degraded"
STEP_NAME = "context_retrieval"


async def retrieve_context(
    turn_request: TurnRequest, loaded_state: LoadedState
) -> MemoryQueryResponse:
    """Query the memory layer for facts relevant to this turn's action."""
    start_time = time.monotonic()
    request = _build_query_request(turn_request, loaded_state)
    response = await _query_memory_safe(request, turn_request, loaded_state, start_time)
    if response is None:
        return MemoryQueryResponse(facts=[], abstained=True)

    _apply_fact_filters(response, loaded_state)
    logger.info(
        EVENT_TURN_STEP_COMPLETED,
        step_name=STEP_NAME,
        facts_returned=len(response.facts),
        abstained=response.abstained,
        duration_ms=(time.monotonic() - start_time) * 1000,
    )
    return response


def _build_query_request(
    turn_request: TurnRequest, loaded_state: LoadedState
) -> MemoryQueryRequest:
    return MemoryQueryRequest(
        scenario_id=loaded_state.scenario_id,
        playthrough_id=turn_request.playthrough_id,
        participant_id=turn_request.participant_id,
        query_text=turn_request.action_text,
        checkpoint=loaded_state.checkpoint or "",
        game_state=loaded_state.state,
        as_of_turn=loaded_state.turn_count,
    )


async def _query_memory_safe(
    request: MemoryQueryRequest,
    turn_request: TurnRequest,
    loaded_state: LoadedState,
    start_time: float,
) -> MemoryQueryResponse | None:
    playthrough_id = str(turn_request.playthrough_id)
    try:
        return await memory_client.query_memory(request)
    except MemoryLayerUnavailableError as exc:
        logger.warning(
            EVENT_CONTEXT_RETRIEVAL_DEGRADED,
            playthrough_id=playthrough_id,
            turn_count=loaded_state.turn_count,
            duration_ms=(time.monotonic() - start_time) * 1000,
            error_type="MemoryLayerUnavailableError",
            error=str(exc),
        )
        return None
    except Exception as exc:
        logger.warning(
            EVENT_CONTEXT_RETRIEVAL_DEGRADED,
            playthrough_id=playthrough_id,
            turn_count=loaded_state.turn_count,
            duration_ms=(time.monotonic() - start_time) * 1000,
            error_type="UnexpectedError",
            error=str(exc),
            exc_info=True,
        )
        return None


def _apply_fact_filters(
    response: MemoryQueryResponse, loaded_state: LoadedState
) -> None:
    revealed_fact_ids = {
        str(fid) for fid in loaded_state.state.get("revealed_facts", [])
    }
    response.facts = _filter_hidden(response.facts, revealed_fact_ids)
    response.facts = _filter_when_active(response.facts, loaded_state.state)


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
