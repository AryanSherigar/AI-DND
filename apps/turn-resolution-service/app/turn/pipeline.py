"""Turn resolution pipeline.

The only file that knows step order — steps in app/turn/steps/ never call
each other directly (CLAUDE.md). This pipeline sequences exactly five steps:
request_receiver, state_loader, ai_orchestrator, state_writer, and
response_streamer. Memory retrieval, condition evaluation, and master-mode
tool-calling steps are intentionally not wired in yet (see
docs/specs/turn-resolution-pipeline.spec.md, section 6).
"""

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse, ServerSentEvent

from app.exceptions.turn_exceptions import NarrationGenerationError, StateWriteError
from app.models.turn import LoadedState, TurnRequest, TurnRequestInput
from app.repositories.participant_repo import ParticipantRepo
from app.repositories.playthrough_repo import PlaythroughRepo
from app.repositories.scenario_repo import ScenarioRepo
from app.repositories.turn_log_repo import TurnLogRepo
from app.turn.steps import (
    ai_orchestrator,
    request_receiver,
    response_streamer,
    state_loader,
    state_writer,
)

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
        turn_request, loaded_state, playthrough_repo, turn_log_repo, scenario_repo
    )
    return await response_streamer.build_sse_response(events)


async def _run_turn_events(
    turn_request: TurnRequest,
    loaded_state: LoadedState,
    playthrough_repo: PlaythroughRepo,
    turn_log_repo: TurnLogRepo,
    scenario_repo: ScenarioRepo,
) -> AsyncIterator[ServerSentEvent]:
    chunks: list[str] = []
    try:
        async for chunk in ai_orchestrator.generate_narration(
            turn_request, loaded_state
        ):
            chunks.append(chunk)
            yield response_streamer.narration_event(chunk)
    except NarrationGenerationError:
        return

    narration_text = "".join(chunks)
    try:
        await state_writer.write_turn(
            turn_request,
            loaded_state,
            narration_text,
            playthrough_repo,
            turn_log_repo,
            scenario_repo,
        )
    except StateWriteError:
        yield response_streamer.degraded_event(_DEGRADED_WRITE_MESSAGE)
        return

    yield response_streamer.done_event()
