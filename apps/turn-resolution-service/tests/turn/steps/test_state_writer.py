"""Unit tests for state_writer.py, with repositories mocked."""

import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.config import settings
from app.exceptions.turn_exceptions import StateWriteError
from app.models.turn import LoadedState, TurnRequest
from app.turn.steps.state_writer import write_turn


def _turn_request() -> TurnRequest:
    return TurnRequest(
        playthrough_id=uuid.uuid4(),
        participant_id=uuid.uuid4(),
        action_text="I look around.",
        turn_count=0,
    )


def _loaded_state(
    turn_count: int,
    scenario_id: uuid.UUID | None = None,
    is_playtest: bool = False,
) -> LoadedState:
    return LoadedState(
        scenario_id=scenario_id or uuid.uuid4(),
        scenario_snapshot={},
        state={"narrative": {"turns_so_far": []}},
        turn_count=turn_count,
        checkpoint=None,
        is_playtest=is_playtest,
    )


def _repos() -> tuple[AsyncMock, AsyncMock, AsyncMock]:
    playthrough_repo = AsyncMock()
    playthrough_repo.session = AsyncMock()
    turn_log_repo = AsyncMock()
    scenario_repo = AsyncMock()
    return playthrough_repo, turn_log_repo, scenario_repo


async def test_write_turn_persists_turn_log_and_state() -> None:
    playthrough_repo, turn_log_repo, scenario_repo = _repos()
    turn_request = _turn_request()

    updated_state = await write_turn(
        turn_request,
        _loaded_state(turn_count=0),
        "You see a corridor.",
        playthrough_repo,
        turn_log_repo,
        scenario_repo,
    )

    turn_log_repo.create.assert_awaited_once()
    playthrough_repo.update_state.assert_awaited_once()
    assert playthrough_repo.update_state.call_args.args[2] == 1
    scenario_repo.increment_play_count.assert_not_awaited()
    assert len(updated_state["narrative"]["turns_so_far"]) == 1


async def test_write_turn_increments_play_count_at_threshold() -> None:
    playthrough_repo, turn_log_repo, scenario_repo = _repos()
    scenario_id = uuid.uuid4()
    turn_request = _turn_request()

    await write_turn(
        turn_request,
        _loaded_state(
            turn_count=settings.play_count_increment_turn_threshold - 1,
            scenario_id=scenario_id,
        ),
        "narration",
        playthrough_repo,
        turn_log_repo,
        scenario_repo,
    )

    scenario_repo.increment_play_count.assert_awaited_once_with(scenario_id)


async def test_write_turn_does_not_increment_play_count_off_threshold() -> None:
    playthrough_repo, turn_log_repo, scenario_repo = _repos()
    turn_request = _turn_request()

    await write_turn(
        turn_request,
        _loaded_state(turn_count=settings.play_count_increment_turn_threshold),
        "narration",
        playthrough_repo,
        turn_log_repo,
        scenario_repo,
    )

    scenario_repo.increment_play_count.assert_not_awaited()


async def test_write_turn_skips_play_count_increment_for_playtest() -> None:
    playthrough_repo, turn_log_repo, scenario_repo = _repos()
    scenario_id = uuid.uuid4()
    turn_request = _turn_request()

    await write_turn(
        turn_request,
        _loaded_state(
            turn_count=settings.play_count_increment_turn_threshold - 1,
            scenario_id=scenario_id,
            is_playtest=True,
        ),
        "narration",
        playthrough_repo,
        turn_log_repo,
        scenario_repo,
    )

    scenario_repo.increment_play_count.assert_not_awaited()


async def test_write_turn_raises_after_retries_exhausted() -> None:
    playthrough_repo, turn_log_repo, scenario_repo = _repos()
    turn_log_repo.create.side_effect = SQLAlchemyError("simulated write failure")

    with pytest.raises(StateWriteError):
        await write_turn(
            _turn_request(),
            _loaded_state(turn_count=0),
            "narration",
            playthrough_repo,
            turn_log_repo,
            scenario_repo,
        )

    assert turn_log_repo.create.await_count == settings.state_write_max_retries + 1


async def test_write_turn_persists_working_state_and_mutated_paths() -> None:
    playthrough_repo, turn_log_repo, scenario_repo = _repos()
    turn_request = _turn_request()
    working_state = {"player": {"health": 90}, "narrative": {"turns_so_far": []}}

    await write_turn(
        turn_request,
        _loaded_state(turn_count=0),
        "You take a hit.",
        playthrough_repo,
        turn_log_repo,
        scenario_repo,
        working_state=working_state,
        tool_calls=[{"tool_name": "adjust_numeric_field", "is_valid": True}],
        mutated_paths={"player.health"},
    )

    persisted_state = playthrough_repo.update_state.call_args.args[1]
    assert persisted_state["player"]["health"] == 90
    assert persisted_state["_last_changed_fields"] == ["player.health"]
    turn_log_repo.create.assert_awaited_once()
    assert turn_log_repo.create.call_args.kwargs["tool_calls"] == [
        {"tool_name": "adjust_numeric_field", "is_valid": True}
    ]
