"""Unit tests for request_receiver.py, with repositories mocked."""

import uuid
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.exceptions.turn_exceptions import (
    ParticipantNotFoundError,
    PlaythroughNotActiveError,
    TurnOrderError,
)
from app.models.turn import TurnRequestInput
from app.turn.steps.request_receiver import receive_request


def _participant(participant_id: uuid.UUID, position: int) -> SimpleNamespace:
    return SimpleNamespace(participant_id=participant_id, turn_order_position=position)


async def test_solo_turn_passes_validation() -> None:
    playthrough_id = uuid.uuid4()
    participant_id = uuid.uuid4()
    playthrough_repo = AsyncMock()
    playthrough_repo.get_by_id.return_value = SimpleNamespace(
        status="active", turn_count=0
    )
    participant_repo = AsyncMock()
    participant_repo.list_by_playthrough.return_value = [
        _participant(participant_id, 1)
    ]

    turn_request = await receive_request(
        TurnRequestInput(
            playthrough_id=playthrough_id,
            participant_id=participant_id,
            action_text="look",
        ),
        playthrough_repo,
        participant_repo,
    )

    assert turn_request.turn_count == 0


async def test_inactive_playthrough_raises() -> None:
    playthrough_repo = AsyncMock()
    playthrough_repo.get_by_id.return_value = SimpleNamespace(
        status="completed", turn_count=5
    )
    participant_repo = AsyncMock()

    with pytest.raises(PlaythroughNotActiveError):
        await receive_request(
            TurnRequestInput(
                playthrough_id=uuid.uuid4(),
                participant_id=uuid.uuid4(),
                action_text="look",
            ),
            playthrough_repo,
            participant_repo,
        )


async def test_unknown_participant_raises() -> None:
    playthrough_repo = AsyncMock()
    playthrough_repo.get_by_id.return_value = SimpleNamespace(
        status="active", turn_count=0
    )
    participant_repo = AsyncMock()
    participant_repo.list_by_playthrough.return_value = [_participant(uuid.uuid4(), 1)]

    with pytest.raises(ParticipantNotFoundError):
        await receive_request(
            TurnRequestInput(
                playthrough_id=uuid.uuid4(),
                participant_id=uuid.uuid4(),
                action_text="look",
            ),
            playthrough_repo,
            participant_repo,
        )


async def test_multiplayer_out_of_turn_raises() -> None:
    acting_id = uuid.uuid4()
    playthrough_repo = AsyncMock()
    playthrough_repo.get_by_id.return_value = SimpleNamespace(
        status="active", turn_count=0
    )
    participant_repo = AsyncMock()
    participant_repo.list_by_playthrough.return_value = [
        _participant(uuid.uuid4(), 1),
        _participant(acting_id, 2),
    ]

    with pytest.raises(TurnOrderError):
        await receive_request(
            TurnRequestInput(
                playthrough_id=uuid.uuid4(),
                participant_id=acting_id,
                action_text="look",
            ),
            playthrough_repo,
            participant_repo,
        )


async def test_multiplayer_correct_turn_passes() -> None:
    first_id, second_id = uuid.uuid4(), uuid.uuid4()
    playthrough_repo = AsyncMock()
    playthrough_repo.get_by_id.return_value = SimpleNamespace(
        status="active", turn_count=0
    )
    participant_repo = AsyncMock()
    participant_repo.list_by_playthrough.return_value = [
        _participant(first_id, 1),
        _participant(second_id, 2),
    ]

    turn_request = await receive_request(
        TurnRequestInput(
            playthrough_id=uuid.uuid4(), participant_id=first_id, action_text="look"
        ),
        playthrough_repo,
        participant_repo,
    )

    assert turn_request.participant_id == first_id
