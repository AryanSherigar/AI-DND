"""Turn resolution pipeline.

The only file that knows step order — steps in app/turn/steps/ never call
each other directly (CLAUDE.md). This pipeline sequences seven steps:
request_receiver, state_loader, context_retrieval, ai_orchestrator,
state_writer, memory_writer, and response_streamer. Condition evaluation and
master-mode tool-calling steps are intentionally not wired in yet — newbie
mode doesn't use them (see docs/specs/trs-turn-endpoint-and-memory-wiring.spec.md).
"""

import uuid
from collections.abc import AsyncIterator

import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

from app.db.models.participant import Participant
from app.exceptions.turn_exceptions import NarrationGenerationError, StateWriteError
from app.models.turn import LoadedState, TurnRequest, TurnRequestInput
from app.repositories.participant_repo import ParticipantRepo
from app.repositories.playthrough_repo import PlaythroughRepo
from app.repositories.scenario_repo import ScenarioRepo
from app.repositories.turn_log_repo import TurnLogRepo
from app.session import notification_manager, spectator_manager
from app.turn.steps import (
    ai_orchestrator,
    context_retrieval,
    memory_writer,
    request_receiver,
    response_streamer,
    state_loader,
    state_writer,
)
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
    context = await context_retrieval.retrieve_context(turn_request, loaded_state)

    chunks: list[str] = []
    try:
        async for chunk in ai_orchestrator.generate_narration(
            turn_request, loaded_state, context
        ):
            chunks.append(chunk)
            await spectator_manager.publish(
                turn_request.playthrough_id, "narration", chunk
            )
            yield response_streamer.narration_event(chunk)
    except NarrationGenerationError:
        logger.warning(
            EVENT_SSE_STREAM_ERROR, playthrough_id=playthrough_id, outcome="error"
        )
        return

    try:
        updated_turns_so_far = await state_writer.write_turn(
            turn_request,
            loaded_state,
            "".join(chunks),
            playthrough_repo,
            turn_log_repo,
            scenario_repo,
        )
    except StateWriteError:
        logger.warning(
            EVENT_SSE_STREAM_CLOSED, playthrough_id=playthrough_id, outcome="degraded"
        )
        yield response_streamer.degraded_event(_DEGRADED_WRITE_MESSAGE)
        return

    await _after_successful_write(
        turn_request, loaded_state, updated_turns_so_far, participant_repo
    )
    logger.info(EVENT_SSE_STREAM_CLOSED, playthrough_id=playthrough_id, outcome="done")
    yield response_streamer.done_event()


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
