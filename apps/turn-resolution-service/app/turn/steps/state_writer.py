"""Persists a completed turn: TurnLog row, updated state, conditional play_count.

Commits explicitly on success rather than relying on a request-scoped
dependency's post-yield commit: this pipeline is consumed from inside a
long-lived SSE generator, and FastAPI resolves `Depends(...)` cleanup as soon
as the endpoint function returns the response object — before the generator
body (and therefore this write) has actually run (the same class of ordering
bug documented in docs/adr/010 for BackgroundTasks). Committing here is what
guarantees "done" is never emitted for a turn that isn't actually durable.
"""

import uuid

from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.exceptions.turn_exceptions import StateWriteError
from app.models.turn import LoadedState, TurnRequest
from app.repositories.playthrough_repo import PlaythroughRepo
from app.repositories.scenario_repo import ScenarioRepo
from app.repositories.turn_log_repo import TurnLogRepo


async def write_turn(
    turn_request: TurnRequest,
    loaded_state: LoadedState,
    narration_text: str,
    playthrough_repo: PlaythroughRepo,
    turn_log_repo: TurnLogRepo,
    scenario_repo: ScenarioRepo,
) -> None:
    """Persist a completed turn, retrying transient failures."""
    new_turn_count = loaded_state.turn_count + 1
    updated_state = _append_turn(
        loaded_state.state, turn_request.action_text, narration_text
    )

    await _persist_with_retry(
        turn_request,
        loaded_state.scenario_id,
        new_turn_count,
        narration_text,
        updated_state,
        playthrough_repo,
        turn_log_repo,
        scenario_repo,
    )


async def _persist_with_retry(
    turn_request: TurnRequest,
    scenario_id: uuid.UUID,
    new_turn_count: int,
    narration_text: str,
    updated_state: dict[str, object],
    playthrough_repo: PlaythroughRepo,
    turn_log_repo: TurnLogRepo,
    scenario_repo: ScenarioRepo,
) -> None:
    max_attempts = settings.state_write_max_retries + 1
    for attempt in range(max_attempts):
        try:
            await _write_once(
                turn_request,
                scenario_id,
                new_turn_count,
                narration_text,
                updated_state,
                playthrough_repo,
                turn_log_repo,
                scenario_repo,
            )
            return
        except SQLAlchemyError as exc:
            await playthrough_repo.session.rollback()
            if attempt == max_attempts - 1:
                raise StateWriteError() from exc


async def _write_once(
    turn_request: TurnRequest,
    scenario_id: uuid.UUID,
    new_turn_count: int,
    narration_text: str,
    updated_state: dict[str, object],
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
    )
    await playthrough_repo.update_state(
        turn_request.playthrough_id, updated_state, new_turn_count
    )
    if new_turn_count == settings.play_count_increment_turn_threshold:
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
