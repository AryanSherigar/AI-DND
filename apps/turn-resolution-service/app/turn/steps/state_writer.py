"""Persists a completed turn: TurnLog row, updated state, conditional play_count.

Commits explicitly on success rather than relying on a request-scoped
dependency's post-yield commit: this pipeline is consumed from inside a
long-lived SSE generator, and FastAPI resolves `Depends(...)` cleanup as soon
as the endpoint function returns the response object — before the generator
body (and therefore this write) has actually run (the same class of ordering
bug documented in docs/adr/010 for BackgroundTasks). Committing here is what
guarantees "done" is never emitted for a turn that isn't actually durable.
"""

import time
import uuid

import structlog
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.exceptions.turn_exceptions import StateWriteError
from app.models.turn import LoadedState, TurnRequest
from app.repositories.playthrough_repo import PlaythroughRepo
from app.repositories.scenario_repo import ScenarioRepo
from app.repositories.turn_log_repo import TurnLogRepo

logger = structlog.get_logger()

EVENT_TURN_STEP_COMPLETED = "turn_step_completed"
EVENT_TURN_STATE_WRITE_FAILED = "turn_state_write_failed"
STEP_NAME = "state_writer"


async def write_turn(
    turn_request: TurnRequest,
    loaded_state: LoadedState,
    narration_text: str,
    playthrough_repo: PlaythroughRepo,
    turn_log_repo: TurnLogRepo,
    scenario_repo: ScenarioRepo,
    working_state: dict[str, object] | None = None,
    tool_calls: list[dict[str, object]] | None = None,
    mutated_paths: set[str] | None = None,
) -> dict[str, object]:
    """Persist a completed turn, retrying transient failures.

    working_state (master mode only) is the state as of after condition_
    evaluator's Effect C mutations and the AI's validated tool-call
    mutations — the base this appends narrative onto, instead of
    loaded_state.state directly. mutated_paths (master mode) is persisted as
    `_last_changed_fields`, read by next turn's condition_evaluator to scope
    which conditions/invariants need re-evaluating.

    Returns the full updated state so callers can extract turns_so_far
    (memory_writer) or evaluate end conditions against it directly
    (end_condition_evaluator), without recomputing it from Playthrough.state.
    """
    start = time.monotonic()
    new_turn_count = loaded_state.turn_count + 1
    base_state = working_state if working_state is not None else loaded_state.state
    updated_state = _append_turn(base_state, turn_request.action_text, narration_text)
    if mutated_paths:
        updated_state = dict(updated_state)
        updated_state["_last_changed_fields"] = sorted(mutated_paths)

    retry_count = await _persist_with_retry(
        turn_request,
        loaded_state.scenario_id,
        loaded_state.is_playtest,
        new_turn_count,
        narration_text,
        updated_state,
        tool_calls or [],
        playthrough_repo,
        turn_log_repo,
        scenario_repo,
    )
    logger.info(
        EVENT_TURN_STEP_COMPLETED,
        step_name=STEP_NAME,
        duration_ms=(time.monotonic() - start) * 1000,
        retry_count=retry_count,
    )
    return updated_state


async def _persist_with_retry(
    turn_request: TurnRequest,
    scenario_id: uuid.UUID,
    is_playtest: bool,
    new_turn_count: int,
    narration_text: str,
    updated_state: dict[str, object],
    tool_calls: list[dict[str, object]],
    playthrough_repo: PlaythroughRepo,
    turn_log_repo: TurnLogRepo,
    scenario_repo: ScenarioRepo,
) -> int:
    max_attempts = settings.state_write_max_retries + 1
    for attempt in range(max_attempts):
        try:
            await _write_once(
                turn_request,
                scenario_id,
                is_playtest,
                new_turn_count,
                narration_text,
                updated_state,
                tool_calls,
                playthrough_repo,
                turn_log_repo,
                scenario_repo,
            )
            return attempt
        except SQLAlchemyError as exc:
            await playthrough_repo.session.rollback()
            if attempt == max_attempts - 1:
                logger.error(
                    EVENT_TURN_STATE_WRITE_FAILED,
                    playthrough_id=str(turn_request.playthrough_id),
                    retry_count=attempt,
                )
                raise StateWriteError() from exc
    return max_attempts - 1


async def _write_once(
    turn_request: TurnRequest,
    scenario_id: uuid.UUID,
    is_playtest: bool,
    new_turn_count: int,
    narration_text: str,
    updated_state: dict[str, object],
    tool_calls: list[dict[str, object]],
    playthrough_repo: PlaythroughRepo,
    turn_log_repo: TurnLogRepo,
    scenario_repo: ScenarioRepo,
) -> None:
    await turn_log_repo.create(
        playthrough_id=turn_request.playthrough_id,
        turn_number=new_turn_count,
        participant_id=turn_request.participant_id,
        action_text=turn_request.action_text,
        narration_text=narration_text,
        tool_calls=tool_calls,
    )
    await playthrough_repo.update_state(
        turn_request.playthrough_id, updated_state, new_turn_count
    )
    should_increment_play_count = (
        new_turn_count == settings.play_count_increment_turn_threshold
        and not is_playtest
    )
    if should_increment_play_count:
        await scenario_repo.increment_play_count(scenario_id)
    await playthrough_repo.session.commit()


def _append_turn(
    state: dict[str, object], action_text: str, narration_text: str
) -> dict[str, object]:
    narrative = dict(state.get("narrative", {}))
    turns_so_far = list(narrative.get("turns_so_far", []))
    turns_so_far.append({"action_text": action_text, "narration_text": narration_text})
    narrative["turns_so_far"] = turns_so_far

    updated_state = dict(state)
    updated_state["narrative"] = narrative
    return updated_state
