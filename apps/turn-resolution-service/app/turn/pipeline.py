"""Turn resolution pipeline.

The only file that knows step order — steps in app/turn/steps/ never call
each other directly (CLAUDE.md). Newbie mode: request_receiver, state_loader,
context_retrieval, ai_orchestrator, state_writer, memory_writer,
response_streamer. Master mode additionally runs condition_evaluator between
state_loader and context_retrieval (active conditions + Effect C, applied
before the AI narrates — see docs/specs/master-mode-turn-pipeline.spec.md),
carries the AI's validated tool-call mutations + tool-call log through to
state_writer, and runs end_condition_evaluator immediately after
state_writer, before memory_writer (see
docs/specs/master-mode-end-conditions.spec.md). For scenarios with ≥1 map,
also runs map_state_sync right before state_writer, folding any
current_location_id change's discovery update into the same persisted write
(see docs/specs/master-mode-maps.spec.md).
"""

import uuid
from collections.abc import AsyncIterator

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

from app.db.models.participant import Participant
from app.exceptions.turn_exceptions import NarrationGenerationError, StateWriteError
from app.models.tool_call import MasterModeTurnResult
from app.models.turn import LoadedState, TurnRequest, TurnRequestInput
from app.repositories.participant_repo import ParticipantRepo
from app.repositories.playthrough_repo import PlaythroughRepo
from app.repositories.scenario_repo import ScenarioRepo
from app.repositories.turn_log_repo import TurnLogRepo
from app.session import notification_manager, spectator_manager
from app.turn.steps import (
    ai_orchestrator,
    condition_evaluator,
    context_retrieval,
    end_condition_evaluator,
    map_state_sync,
    memory_writer,
    request_receiver,
    response_streamer,
    state_loader,
    state_writer,
    turn_summary_builder,
)
from app.turn.steps.end_condition_evaluator import MatchedOutcome
from app.turn.turn_order import expected_participant

logger = structlog.get_logger()

EVENT_SSE_STREAM_OPENED = "sse_stream_opened"
EVENT_SSE_STREAM_CLOSED = "sse_stream_closed"
EVENT_SSE_STREAM_ERROR = "sse_stream_error"

_DEGRADED_WRITE_MESSAGE = (
    "Your turn couldn't be saved. Please try submitting your action again."
)


async def run_turn(
    turn_input: TurnRequestInput, session: AsyncSession
) -> EventSourceResponse:
    """Validate, generate narration, persist, and stream a single turn."""
    playthrough_repo = PlaythroughRepo(session)
    participant_repo = ParticipantRepo(session)
    turn_log_repo = TurnLogRepo(session)
    scenario_repo = ScenarioRepo(session)

    turn_request = await request_receiver.receive_request(
        turn_input, playthrough_repo, participant_repo
    )
    loaded_state = await state_loader.load_state(
        turn_request.playthrough_id, playthrough_repo
    )

    events = _run_turn_events(
        turn_request,
        loaded_state,
        playthrough_repo,
        turn_log_repo,
        scenario_repo,
        participant_repo,
    )
    return await response_streamer.build_sse_response(events)


def _format_ai_event(
    event_type: str, data: str, chunks: list[str]
) -> ServerSentEvent | None:
    """Format AI stream event and accumulate narration chunks."""
    if event_type == "mood":
        return response_streamer.mood_event(data)
    if event_type == "narration":
        chunks.append(data)
        return response_streamer.narration_event(data)
    return None


async def _run_turn_events(
    turn_request: TurnRequest,
    loaded_state: LoadedState,
    playthrough_repo: PlaythroughRepo,
    turn_log_repo: TurnLogRepo,
    scenario_repo: ScenarioRepo,
    participant_repo: ParticipantRepo,
) -> AsyncIterator[ServerSentEvent]:
    playthrough_id = str(turn_request.playthrough_id)
    logger.info(EVENT_SSE_STREAM_OPENED, playthrough_id=playthrough_id)

    is_master_mode = loaded_state.scenario_snapshot.get("mode") == "master"
    active_instructions: list[str] = []
    mutated_paths: set[str] = set()

    if is_master_mode:
        evaluation = condition_evaluator.evaluate_conditions(loaded_state)
        loaded_state = loaded_state.model_copy(update={"state": evaluation.state})
        active_instructions = evaluation.active_instructions
        mutated_paths |= evaluation.mutated_paths

    context = await context_retrieval.retrieve_context(turn_request, loaded_state)
    result_sink = MasterModeTurnResult(final_state=loaded_state.state)

    chunks: list[str] = []
    try:
        async for event_type, data in ai_orchestrator.generate_narration(
            turn_request, loaded_state, context, active_instructions, result_sink
        ):
            await spectator_manager.publish(
                turn_request.playthrough_id, event_type, data
            )
            sse_event = _format_ai_event(event_type, data, chunks)
            if sse_event:
                yield sse_event
    except NarrationGenerationError:
        logger.warning(
            EVENT_SSE_STREAM_ERROR, playthrough_id=playthrough_id, outcome="error"
        )
        return

    working_state: dict[str, object] | None = None
    tool_calls: list[dict[str, object]] | None = None
    if is_master_mode:
        mutated_paths |= set(result_sink.mutated_paths)
        working_state = result_sink.final_state
        tool_calls = [tc.model_dump() for tc in result_sink.tool_calls]
        if loaded_state.scenario_snapshot.get("maps"):
            mutated_paths |= map_state_sync.sync_discovered_locations(
                loaded_state.state, working_state
            )

    try:
        updated_state = await state_writer.write_turn(
            turn_request,
            loaded_state,
            "".join(chunks),
            playthrough_repo,
            turn_log_repo,
            scenario_repo,
            working_state=working_state,
            tool_calls=tool_calls,
            mutated_paths=mutated_paths or None,
        )
    except StateWriteError:
        logger.warning(
            EVENT_SSE_STREAM_CLOSED, playthrough_id=playthrough_id, outcome="degraded"
        )
        yield response_streamer.degraded_event(_DEGRADED_WRITE_MESSAGE)
        return

    matched_outcome: MatchedOutcome | None = None
    if is_master_mode:
        matched_outcome = end_condition_evaluator.evaluate_end_conditions(
            loaded_state, updated_state
        )
        if matched_outcome:
            await _finalize_ending(
                turn_request.playthrough_id, matched_outcome, playthrough_repo
            )

    await _after_successful_write(
        turn_request,
        loaded_state,
        updated_state["narrative"]["turns_so_far"],
        participant_repo,
    )

    if is_master_mode:
        yield _build_turn_summary_event(loaded_state, updated_state, tool_calls or [])

    if matched_outcome:
        yield response_streamer.playthrough_ended_event(
            matched_outcome.outcome_tag,
            matched_outcome.outcome_title,
            matched_outcome.outcome_text,
        )
    logger.info(EVENT_SSE_STREAM_CLOSED, playthrough_id=playthrough_id, outcome="done")
    yield response_streamer.done_event()


def _build_turn_summary_event(
    loaded_state: LoadedState,
    updated_state: dict[str, object],
    tool_calls: list[dict[str, object]],
) -> ServerSentEvent:
    """Compose the turn_summary event from this turn's tool calls plus the
    full set of currently-active conditions (not just ones that changed this
    turn) against the final, post-write state."""
    conditions = loaded_state.scenario_snapshot.get("scenario_conditions", []) or []
    active_conditions = condition_evaluator.list_active_condition_labels(
        conditions, updated_state
    )
    payload = turn_summary_builder.build_turn_summary(
        tool_calls,
        loaded_state.state,
        updated_state,
        loaded_state.scenario_snapshot,
        active_conditions,
    )
    return response_streamer.turn_summary_event(payload)


async def _finalize_ending(
    playthrough_id: uuid.UUID,
    matched_outcome: MatchedOutcome,
    playthrough_repo: PlaythroughRepo,
) -> None:
    """Persist the matched outcome and broadcast it to other participants."""
    await playthrough_repo.mark_ended(
        playthrough_id,
        matched_outcome.outcome_tag,
        matched_outcome.outcome_title,
        matched_outcome.outcome_text,
    )
    await notification_manager.notify_playthrough_ended(
        playthrough_id, matched_outcome.outcome_title
    )


async def _after_successful_write(
    turn_request: TurnRequest,
    loaded_state: LoadedState,
    updated_turns_so_far: list[dict[str, object]],
    participant_repo: ParticipantRepo,
) -> None:
    """Fire the memory batch, multiplayer notification, and spectator relay."""
    new_turn_count = loaded_state.turn_count + 1
    await memory_writer.maybe_flush_batch(
        turn_request, loaded_state, new_turn_count, updated_turns_so_far
    )
    await _notify_next_participant(
        turn_request.playthrough_id, new_turn_count, participant_repo
    )
    await spectator_manager.publish(turn_request.playthrough_id, "done", "")


async def _notify_next_participant(
    playthrough_id: uuid.UUID, new_turn_count: int, participant_repo: ParticipantRepo
) -> None:
    """Push a 'your_turn' notification to whoever acts next, in multiplayer only."""
    participants: list[Participant] = await participant_repo.list_by_playthrough(
        playthrough_id
    )
    if len(participants) <= 1:
        return
    next_participant = expected_participant(participants, new_turn_count)
    await notification_manager.notify_next_turn(
        playthrough_id, next_participant.participant_id
    )
