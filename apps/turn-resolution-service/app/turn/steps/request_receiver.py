"""Validates an incoming turn request before any state loading occurs."""

import time
import uuid

import structlog

from app.db.models.participant import Participant
from app.db.models.playthrough import Playthrough as PlaythroughModel
from app.exceptions.turn_exceptions import (
    ParticipantNotFoundError,
    PlaythroughNotActiveError,
    TurnOrderError,
)
from app.models.turn import TurnRequest, TurnRequestInput
from app.repositories.participant_repo import ParticipantRepo
from app.repositories.playthrough_repo import PlaythroughRepo
from app.turn.turn_order import expected_participant

logger = structlog.get_logger()

EVENT_TURN_STEP_COMPLETED = "turn_step_completed"
EVENT_TURN_REJECTED_NOT_ACTIVE = "turn_rejected_not_active"
STEP_NAME = "request_receiver"


async def receive_request(
    turn_input: TurnRequestInput,
    playthrough_repo: PlaythroughRepo,
    participant_repo: ParticipantRepo,
) -> TurnRequest:
    """Validate playthrough status, participant membership, and turn order."""
    start = time.monotonic()
    playthrough = await playthrough_repo.get_by_id(turn_input.playthrough_id)
    if playthrough is None or playthrough.status != "active":
        logger.warning(
            EVENT_TURN_REJECTED_NOT_ACTIVE,
            playthrough_id=str(turn_input.playthrough_id),
            status=playthrough.status if playthrough is not None else "not_found",
        )
        raise PlaythroughNotActiveError(_not_active_message(playthrough))

    participants = await participant_repo.list_by_playthrough(turn_input.playthrough_id)
    acting_participant = _find_participant(participants, turn_input.participant_id)
    if acting_participant is None:
        raise ParticipantNotFoundError()

    if len(participants) > 1:
        _validate_turn_order(participants, acting_participant, playthrough.turn_count)

    logger.info(
        EVENT_TURN_STEP_COMPLETED,
        step_name=STEP_NAME,
        playthrough_id=str(turn_input.playthrough_id),
        duration_ms=(time.monotonic() - start) * 1000,
    )
    return TurnRequest(
        playthrough_id=turn_input.playthrough_id,
        participant_id=turn_input.participant_id,
        action_text=turn_input.action_text,
        turn_count=playthrough.turn_count,
    )


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
