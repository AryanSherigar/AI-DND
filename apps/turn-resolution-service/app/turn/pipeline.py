"""Turn resolution pipeline.

The only file that knows step order — steps in app/turn/steps/ never call
each other directly (CLAUDE.md). Newbie mode: request_receiver, state_loader,
context_retrieval, ai_orchestrator, state_writer, memory_writer,
response_streamer. Master mode additionally runs, between state_loader and
context_retrieval: minigame_result_resolver (only when the incoming request's
action_kind is "minigame_result" — resolves the pending minigame's outcome
into a state mutation + narrator instruction and clears _pending_minigame,
see docs/specs/master-mode-minigames.spec.md §2), then condition_evaluator
(active conditions + Effect C, applied before the AI narrates — see
docs/specs/master-mode-turn-pipeline.spec.md), carries the AI's validated
tool-call mutations + tool-call log through to state_writer, and runs
end_condition_evaluator immediately after state_writer, before memory_writer
(see docs/specs/master-mode-end-conditions.spec.md). For scenarios with ≥1
map, also runs map_state_sync right before state_writer, folding any
current_location_id change's discovery update into the same persisted write
(see docs/specs/master-mode-maps.spec.md). Immediately after map_state_sync
(same slot, still before state_writer), runs minigame_trigger_evaluator: for
a solo playthrough with no minigame already pending, evaluates
scenario_minigames in priority order against the final working_state and, on
the first match, stamps the play-time payload into
working_state["_pending_minigame"] and fires a best-effort pre-warm ping for
a replit_embed minigame's URL. When a fresh trigger was just stamped this
turn, end_condition_evaluator is skipped entirely (minigame wins over an
end condition matching the same turn) and a minigame SSE event is yielded
after turn_summary_event, before playthrough_ended_event/done_event (see
docs/specs/master-mode-minigames.spec.md §2).
"""

import uuid
from collections.abc import AsyncIterator

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from sse_starlette.sse import EventSourceResponse, ServerSentEvent
from tenacity import AsyncRetrying, retry_if_exception_type, stop_after_attempt

from app.config import settings
from app.db.models.participant import Participant
from app.exceptions.turn_exceptions import NarrationGenerationError, StateWriteError
from app.models.minigame_event import MinigameEventPayload
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
    minigame_result_resolver,
    minigame_trigger_evaluator,
    request_receiver,
    response_streamer,
    state_loader,
    state_writer,
    turn_summary_builder,
)
from app.turn.steps.end_condition_evaluator import MatchedOutcome
from app.turn.steps.minigame_trigger_evaluator import MatchedMinigameTrigger
from app.turn.turn_order import expected_participant

logger = structlog.get_logger()

EVENT_SSE_STREAM_OPENED = "sse_stream_opened"
EVENT_SSE_STREAM_CLOSED = "sse_stream_closed"
EVENT_SSE_STREAM_ERROR = "sse_stream_error"
EVENT_MINIGAME_PREWARM_FAILED = "minigame_prewarm_failed"

_DEGRADED_WRITE_MESSAGE = (
    "Your turn couldn't be saved. Please try submitting your action again."
)
_MINIGAME_TYPE_REPLIT_EMBED = "replit_embed"
_PREWARM_TIMEOUT_SECONDS = 2.0
_PREWARM_MAX_ATTEMPTS = 2


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
    participants = await participant_repo.list_by_playthrough(
        turn_request.playthrough_id
    )
    participant_count = len(participants)
    active_instructions: list[str] = []
    mutated_paths: set[str] = set()

    if is_master_mode:
        loaded_state, active_instructions, mutated_paths = _evaluate_master_mode_intake(
            turn_request, loaded_state
        )

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
    matched_trigger: MatchedMinigameTrigger | None = None
    if is_master_mode:
        mutated_paths |= set(result_sink.mutated_paths)
        working_state = result_sink.final_state
        tool_calls = [tc.model_dump() for tc in result_sink.tool_calls]
        if loaded_state.scenario_snapshot.get("maps"):
            mutated_paths |= map_state_sync.sync_discovered_locations(
                loaded_state.state, working_state
            )
        matched_trigger = minigame_trigger_evaluator.evaluate_trigger(
            loaded_state.scenario_snapshot.get("scenario_minigames", []) or [],
            working_state,
            participant_count,
            settings.minigame_iframe_handshake_timeout_seconds,
        )
        if matched_trigger:
            mutated_paths |= await _stamp_pending_minigame(
                working_state, matched_trigger
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
    if is_master_mode and not matched_trigger:
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
        participants,
    )

    if is_master_mode:
        yield _build_turn_summary_event(loaded_state, updated_state, tool_calls or [])

    if matched_trigger:
        yield response_streamer.minigame_event(
            MinigameEventPayload(**matched_trigger.payload)
        )

    if matched_outcome:
        yield response_streamer.playthrough_ended_event(
            matched_outcome.outcome_tag,
            matched_outcome.outcome_title,
            matched_outcome.outcome_text,
        )
    logger.info(EVENT_SSE_STREAM_CLOSED, playthrough_id=playthrough_id, outcome="done")
    yield response_streamer.done_event()


def _evaluate_master_mode_intake(
    turn_request: TurnRequest, loaded_state: LoadedState
) -> tuple[LoadedState, list[str], set[str]]:
    """Run minigame_result_resolver (only for a minigame_result submission),
    then condition_evaluator, in the pipeline slot between state_loader and
    context_retrieval — minigame_result_resolver runs first so
    condition_evaluator's own Effect C pass sees its mutation already
    applied."""
    active_instructions: list[str] = []
    mutated_paths: set[str] = set()

    if turn_request.action_kind == "minigame_result" and turn_request.minigame_result:
        resolution = minigame_result_resolver.resolve_result(
            loaded_state.scenario_snapshot.get("scenario_minigames", []) or [],
            loaded_state.state,
            loaded_state.scenario_snapshot,
            turn_request.minigame_result.minigame_id,
            turn_request.minigame_result.outcome_tag,
            turn_request.minigame_result.score,
        )
        loaded_state = loaded_state.model_copy(update={"state": resolution.state})
        active_instructions.append(resolution.instruction)
        mutated_paths |= resolution.mutated_paths

    evaluation = condition_evaluator.evaluate_conditions(loaded_state)
    loaded_state = loaded_state.model_copy(update={"state": evaluation.state})
    active_instructions += evaluation.active_instructions
    mutated_paths |= evaluation.mutated_paths
    return loaded_state, active_instructions, mutated_paths


async def _stamp_pending_minigame(
    working_state: dict[str, object], matched_trigger: MatchedMinigameTrigger
) -> set[str]:
    """Mutate working_state in place with the matched trigger's payload and,
    for a replit_embed minigame, fire the best-effort pre-warm ping."""
    working_state[minigame_trigger_evaluator.STATE_KEY_PENDING_MINIGAME] = (
        matched_trigger.payload
    )
    if matched_trigger.payload.get("minigame_type") == _MINIGAME_TYPE_REPLIT_EMBED:
        replit_embed_url = matched_trigger.payload.get("replit_embed_url")
        if replit_embed_url:
            await _prewarm_replit_url(str(replit_embed_url))
    return {minigame_trigger_evaluator.STATE_KEY_PENDING_MINIGAME}


async def _prewarm_replit_url(url: str) -> None:
    """Best-effort HTTP ping to wake a sleeping free-tier Replit before the
    player reaches the minigame overlay. Capped total budget of a couple
    seconds so it never meaningfully delays the SSE stream — exceptions are
    swallowed and logged, never re-raised into the turn (§3.6 "Never")."""
    try:
        async with httpx.AsyncClient(timeout=_PREWARM_TIMEOUT_SECONDS) as client:
            async for attempt in AsyncRetrying(
                stop=stop_after_attempt(_PREWARM_MAX_ATTEMPTS),
                retry=retry_if_exception_type(httpx.HTTPError),
                reraise=True,
            ):
                with attempt:
                    await client.get(url)
    except Exception:
        logger.warning(EVENT_MINIGAME_PREWARM_FAILED, url=url, exc_info=True)


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
    participants: list[Participant],
) -> None:
    """Fire the memory batch, multiplayer notification, and spectator relay."""
    new_turn_count = loaded_state.turn_count + 1
    await memory_writer.maybe_flush_batch(
        turn_request, loaded_state, new_turn_count, updated_turns_so_far
    )
    await _notify_next_participant(
        turn_request.playthrough_id, new_turn_count, participants
    )
    await spectator_manager.publish(turn_request.playthrough_id, "done", "")


async def _notify_next_participant(
    playthrough_id: uuid.UUID,
    new_turn_count: int,
    participants: list[Participant],
) -> None:
    """Push a 'your_turn' notification to whoever acts next, in multiplayer
    only. participants is fetched once, near the top of _run_turn_events —
    also the source of participant_count for the minigame solo-only gate."""
    if len(participants) <= 1:
        return
    next_participant = expected_participant(participants, new_turn_count)
    await notification_manager.notify_next_turn(
        playthrough_id, next_participant.participant_id
    )
