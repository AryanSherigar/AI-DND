"""Loads the frozen scenario snapshot and narrative state for a turn (ADR-8)."""

import time
import uuid

import structlog

from app.exceptions.turn_exceptions import PlaythroughNotActiveError
from app.models.turn import LoadedState
from app.repositories.playthrough_repo import PlaythroughRepo

logger = structlog.get_logger()

EVENT_TURN_STEP_COMPLETED = "turn_step_completed"
STEP_NAME = "state_loader"


async def load_state(
    playthrough_id: uuid.UUID, playthrough_repo: PlaythroughRepo
) -> LoadedState:
    """Load scenario_snapshot and narrative state for the given playthrough.

    Reads only Playthrough.scenario_snapshot — never Scenario directly (ADR-8).
    """
    start = time.monotonic()
    playthrough = await playthrough_repo.get_by_id(playthrough_id)
    if playthrough is None:
        raise PlaythroughNotActiveError()

    logger.info(
        EVENT_TURN_STEP_COMPLETED,
        step_name=STEP_NAME,
        turn_count=playthrough.turn_count,
        duration_ms=(time.monotonic() - start) * 1000,
    )
    return LoadedState(
        scenario_id=playthrough.scenario_id,
        scenario_snapshot=playthrough.scenario_snapshot,
        state=playthrough.state,
        turn_count=playthrough.turn_count,
        checkpoint=playthrough.checkpoint,
    )
