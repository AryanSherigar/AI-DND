"""Validates an incoming turn request before any state loading occurs."""

import uuid

from app.db.models.participant import Participant
from app.exceptions.turn_exceptions import (
    ParticipantNotFoundError,
    PlaythroughNotActiveError,
    TurnOrderError,
)
from app.models.turn import TurnRequest, TurnRequestInput
from app.repositories.participant_repo import ParticipantRepo
from app.repositories.playthrough_repo import PlaythroughRepo


async def receive_request(
    turn_input: TurnRequestInput,
    playthrough_repo: PlaythroughRepo,
    participant_repo: ParticipantRepo,
) -> TurnRequest:
    """Validate playthrough status, participant membership, and turn order."""
    playthrough = await playthrough_repo.get_by_id(turn_input.playthrough_id)
    if playthrough is None or playthrough.status != "active":
        raise PlaythroughNotActiveError()

    participants = await participant_repo.list_by_playthrough(turn_input.playthrough_id)
    acting_participant = _find_participant(participants, turn_input.participant_id)
    if acting_participant is None:
        raise ParticipantNotFoundError()

    if len(participants) > 1:
        _validate_turn_order(participants, acting_participant, playthrough.turn_count)

    return TurnRequest(
        playthrough_id=turn_input.playthrough_id,
        participant_id=turn_input.participant_id,
        action_text=turn_input.action_text,
        turn_count=playthrough.turn_count,
    )


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
    # NOTE: no existing precedent in the codebase for "whose turn is it" — this
    # derives it from turn_order_position (1-indexed) cycling with turn_count,
    # so participant at position 1 acts on turn_count 0, position 2 on turn_count 1, etc.
    ordered = sorted(participants, key=lambda p: p.turn_order_position)
    expected_participant = ordered[turn_count % len(ordered)]
    if acting_participant.participant_id != expected_participant.participant_id:
        raise TurnOrderError()
