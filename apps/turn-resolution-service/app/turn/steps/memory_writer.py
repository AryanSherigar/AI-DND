"""Batches recent turns to the (mocked) memory layer roughly every N turns.

Failures here are swallowed and logged, never raised: per RFC ADR-5 and the
Data Consistency section, memory writes are best-effort and must never block
or fail a turn.
"""

import logging

from app.config import settings
from app.integrations import memory_client
from app.models.memory import MemoryIngestRequest, TurnBatchEntry
from app.models.turn import LoadedState, TurnRequest

logger = logging.getLogger(__name__)


async def maybe_flush_batch(
    turn_request: TurnRequest,
    loaded_state: LoadedState,
    new_turn_count: int,
    updated_turns_so_far: list[dict[str, object]],
) -> None:
    """Fire a batched ingest to the memory layer if this turn hits the interval."""
    if new_turn_count % settings.memory_batch_turn_interval != 0:
        return

    request = _build_ingest_request(
        turn_request, loaded_state, new_turn_count, updated_turns_so_far
    )
    try:
        await memory_client.ingest_batch(request)
    except Exception:
        logger.warning(
            "Memory batch ingest failed for playthrough %s",
            turn_request.playthrough_id,
            exc_info=True,
        )


def _build_ingest_request(
    turn_request: TurnRequest,
    loaded_state: LoadedState,
    new_turn_count: int,
    updated_turns_so_far: list[dict[str, object]],
) -> MemoryIngestRequest:
    batch = updated_turns_so_far[-settings.memory_batch_turn_interval :]
    first_turn_number = new_turn_count - len(batch) + 1
    return MemoryIngestRequest(
        scenario_id=loaded_state.scenario_id,
        playthrough_id=turn_request.playthrough_id,
        turns_batch=[
            TurnBatchEntry(
                turn_number=first_turn_number + i,
                text=f"{turn['action_text']} -> {turn['narration_text']}",
                participant_id=turn_request.participant_id,
            )
            for i, turn in enumerate(batch)
        ],
    )
