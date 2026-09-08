"""Validates an incoming turn request before any state loading occurs."""

import time
import uuid

import structlog

from app.db.models.participant import Participant
from app.db.models.playthrough import Playthrough as PlaythroughModel
from app.exceptions.turn_exceptions import (
    MinigameResultMismatchError,
    MinigameResultRequiredError,
    ParticipantAccessDeniedError,
    ParticipantNotFoundError,
    PlaythroughNotActiveError,
    TurnOrderError,
)
from app.models.auth import CurrentUser
from app.models.turn import TurnRequest, TurnRequestInput
from app.repositories.participant_repo import ParticipantRepo
from app.repositories.playthrough_repo import PlaythroughRepo
from app.turn.turn_order import expected_participant

logger = structlog.get_logger()

EVENT_TURN_STEP_COMPLETED = "turn_step_completed"
EVENT_TURN_REJECTED_NOT_ACTIVE = "turn_rejected_not_active"
EVENT_TURN_REJECTED_ACCESS_DENIED = "turn_rejected_access_denied"
STEP_NAME = "request_receiver"
STATE_KEY_PENDING_MINIGAME = "_pending_minigame"


async def receive_request(
    turn_input: TurnRequestInput,
    playthrough_repo: PlaythroughRepo,
    participant_repo: ParticipantRepo,
    current_user: CurrentUser,
) -> TurnRequest:
    """Validate playthrough status, participant membership, user ownership,
    pending-minigame gating, and turn order."""
    start = time.monotonic()
    playthrough = await playthrough_repo.get_by_id(turn_input.playthrough_id)
    _validate_playthrough_active(playthrough, turn_input.playthrough_id)

    participants = await participant_repo.list_by_playthrough(turn_input.playthrough_id)
    acting_participant = _validate_acting_participant(
        participants, turn_input, current_user
    )

    _validate_minigame_gating(turn_input, _pending_minigame(playthrough))

    if len(participants) > 1:
        _validate_turn_order(participants, acting_participant, playthrough.turn_count)

    _log_step_completed(start, turn_input.playthrough_id)
    return TurnRequest(
        playthrough_id=turn_input.playthrough_id,
        participant_id=turn_input.participant_id,
        action_text=turn_input.action_text,
        action_kind=turn_input.action_kind,
        minigame_result=turn_input.minigame_result,
        turn_count=playthrough.turn_count,
    )


def _validate_playthrough_active(
    playthrough: PlaythroughModel | None, playthrough_id: uuid.UUID
) -> None:
    if playthrough is None or playthrough.status != "active":
        logger.warning(
            EVENT_TURN_REJECTED_NOT_ACTIVE,
            playthrough_id=str(playthrough_id),
            status=playthrough.status if playthrough is not None else "not_found",
        )
        raise PlaythroughNotActiveError(_not_active_message(playthrough))


def _validate_acting_participant(
    participants: list[Participant],
    turn_input: TurnRequestInput,
    current_user: CurrentUser,
) -> Participant:
    acting_participant = _find_participant(participants, turn_input.participant_id)
    if acting_participant is None:
        raise ParticipantNotFoundError()

    if acting_participant.user_id != current_user.user_id:
        logger.warning(
            EVENT_TURN_REJECTED_ACCESS_DENIED,
            playthrough_id=str(turn_input.playthrough_id),
            participant_id=str(turn_input.participant_id),
            participant_user_id=str(acting_participant.user_id),
            current_user_id=str(current_user.user_id),
        )
        raise ParticipantAccessDeniedError()

    return acting_participant


def _log_step_completed(start: float, playthrough_id: uuid.UUID) -> None:
    logger.info(
        EVENT_TURN_STEP_COMPLETED,
        step_name=STEP_NAME,
        playthrough_id=str(playthrough_id),
        duration_ms=(time.monotonic() - start) * 1000,
    )


def _pending_minigame(playthrough: PlaythroughModel) -> dict[str, object] | None:
    """Read _pending_minigame off the already-fetched Playthrough row — no
    new query needed, per docs/specs/master-mode-minigames.spec.md §3.3."""
    state = getattr(playthrough, "state", None)
    if not isinstance(state, dict):
        return None
    pending = state.get(STATE_KEY_PENDING_MINIGAME)
    return pending if isinstance(pending, dict) else None


def _validate_minigame_gating(
    turn_input: TurnRequestInput, pending_minigame: dict[str, object] | None
) -> None:
    """A playthrough can never have two minigames pending, and a submitted
    result must match the minigame actually pending — see §2 sequence flow
    step 8 and §3.2's pending-minigame gating cases."""
    if turn_input.action_kind == "minigame_result":
        _validate_minigame_result_submission(turn_input, pending_minigame)
        return
    if pending_minigame is not None:
        raise MinigameResultRequiredError()


def _validate_minigame_result_submission(
    turn_input: TurnRequestInput, pending_minigame: dict[str, object] | None
) -> None:
    if pending_minigame is None:
        raise MinigameResultMismatchError()
    submitted_id = (
        turn_input.minigame_result.minigame_id if turn_input.minigame_result else None
    )
    if submitted_id != pending_minigame.get("minigame_id"):
        raise MinigameResultMismatchError()
    # Old pending records predate attempt ids and remain compatible. New
    # records require the server-issued id, preventing a stale overlay from
    # resolving a later encounter with the same minigame definition.
    pending_attempt_id = pending_minigame.get("attempt_id")
    submitted_attempt_id = (
        turn_input.minigame_result.attempt_id if turn_input.minigame_result else None
    )
    if pending_attempt_id is not None and submitted_attempt_id != pending_attempt_id:
        raise MinigameResultMismatchError()


def _not_active_message(playthrough: PlaythroughModel | None) -> str:
    """Distinguish a completed story from an abandoned or missing one."""
    if playthrough is not None and playthrough.status == "completed":
        return "This playthrough has already ended"
    return "Playthrough is not active"


def _find_participant(
    participants: list[Participant], participant_id: uuid.UUID
) -> Participant | None:
    for participant in participants:
        if participant.participant_id == participant_id:
            return participant
    return None


def _validate_turn_order(
    participants: list[Participant],
    acting_participant: Participant,
    turn_count: int,
) -> None:
    expected = expected_participant(participants, turn_count)
    if acting_participant.participant_id != expected.participant_id:
        raise TurnOrderError()
