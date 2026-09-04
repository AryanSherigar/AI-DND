"""Integration tests for end-condition evaluation wired into the turn pipeline."""

import uuid
from unittest.mock import AsyncMock

import pytest
from google.genai import types
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.participant import Participant
from app.db.models.playthrough import Playthrough
from app.db.models.scenario import Scenario
from app.db.models.user import User
from app.exceptions.turn_exceptions import PlaythroughNotActiveError
from app.models.turn import TurnRequestInput
from app.session import notification_manager
from app.turn import pipeline
from app.turn.steps import ai_orchestrator, state_loader

pytestmark = pytest.mark.asyncio(loop_scope="session")


class _FakeCandidate:
    def __init__(self) -> None:
        self.content = "fake-model-turn-content"


class _FakeResponse:
    def __init__(self, function_calls: list[types.FunctionCall], text: str) -> None:
        self.function_calls = function_calls
        self.text = text
        self.candidates = [_FakeCandidate()]


_WARDEN_DEFEATED = {
    "condition_expression": {"field": "the_warden.health", "op": "<=", "value": 0},
    "outcome_tag": "win",
    "outcome_title": "The Ashen Ending",
    "outcome_text": "The Warden kneels, and the cairn exhales.",
    "is_secret": False,
}

_VIGILS_ENDING = {
    "condition_expression": {"field": "flags.made_pact", "op": "==", "value": True},
    "outcome_tag": "win",
    "outcome_title": "The Vigil's Ending",
    "outcome_text": "You do not kill the Warden. You relieve it.",
    "is_secret": True,
}


async def _seed_master_playthrough(
    session: AsyncSession, end_conditions: list[dict[str, object]]
) -> tuple[Playthrough, Participant]:
    user_id, scenario_id = uuid.uuid4(), uuid.uuid4()
    user = User(
        user_id=user_id, display_name="Tester", auth_provider_id=str(uuid.uuid4())
    )
    scenario = Scenario(
        scenario_id=scenario_id,
        creator_id=user_id,
        title="The Hollow Cairn",
        mode="master",
        complexity_tier="master",
        player_count_support="solo",
    )
    playthrough = Playthrough(
        scenario_id=scenario_id,
        created_by=user_id,
        scenario_version=1,
        scenario_snapshot={
            "mode": "master",
            "narrator_persona": "Dry, weary humor.",
            "world_data": {},
            "state_schema": {},
            "entities": [],
            "rule_invariants": [],
            "scenario_conditions": [],
            "end_conditions": end_conditions,
        },
        state={
            "the_warden": {"health": 0},
            "flags": {"made_pact": False},
            "narrative": {"turns_so_far": []},
        },
    )
    session.add(user)
    await session.flush()
    session.add(scenario)
    await session.flush()
    session.add(playthrough)
    await session.flush()

    participant = Participant(
        playthrough_id=playthrough.playthrough_id,
        user_id=user_id,
        role="owner",
        turn_order_position=1,
    )
    session.add(participant)
    await session.flush()

    return playthrough, participant


async def _add_second_participant(
    session: AsyncSession, playthrough_id: uuid.UUID
) -> Participant:
    second_user_id = uuid.uuid4()
    session.add(
        User(
            user_id=second_user_id,
            display_name="Second Tester",
            auth_provider_id=str(uuid.uuid4()),
        )
    )
    await session.flush()
    participant_two = Participant(
        playthrough_id=playthrough_id,
        user_id=second_user_id,
        role="joined",
        turn_order_position=2,
    )
    session.add(participant_two)
    await session.flush()
    return participant_two


def _fake_narration(text: str):
    """A no-tool-calls master-mode Gemini response, patched onto
    generate_with_tools (not stream_narration — master mode always drives
    Gemini through the function-calling loop, see ai_orchestrator.py)."""

    async def _generate(system_instruction, contents, timeout_seconds, tools):
        return _FakeResponse([], text)

    return _generate


async def test_matched_end_condition_completes_playthrough(
    db_session: AsyncSession, monkeypatch
) -> None:
    monkeypatch.setattr(
        ai_orchestrator.gemini_client,
        "generate_with_tools",
        _fake_narration("The Warden falls."),
    )

    playthrough, participant = await _seed_master_playthrough(
        db_session, [_WARDEN_DEFEATED]
    )

    turn_input = TurnRequestInput(
        playthrough_id=playthrough.playthrough_id,
        participant_id=participant.participant_id,
        action_text="I strike the final blow.",
    )
    response = await pipeline.run_turn(turn_input, db_session)
    events = [event async for event in response.body_iterator]

    assert [e.event for e in events] == [
        "narration",
        "turn_summary",
        "playthrough_ended",
        "done",
    ]

    stmt = select(Playthrough).where(
        Playthrough.playthrough_id == playthrough.playthrough_id
    )
    updated = (await db_session.execute(stmt)).scalars().first()
    assert updated is not None
    assert updated.status == "completed"
    assert updated.ended_outcome_tag == "win"
    assert updated.ended_outcome_title == "The Ashen Ending"
    assert updated.ended_outcome_text == _WARDEN_DEFEATED["outcome_text"]


async def test_first_matching_condition_wins_ordering(
    db_session: AsyncSession, monkeypatch
) -> None:
    monkeypatch.setattr(
        ai_orchestrator.gemini_client,
        "generate_with_tools",
        _fake_narration("The Warden falls."),
    )

    playthrough, participant = await _seed_master_playthrough(
        db_session, [_WARDEN_DEFEATED, _VIGILS_ENDING]
    )
    playthrough.state = {
        "the_warden": {"health": 0},
        "flags": {"made_pact": True},
        "narrative": {"turns_so_far": []},
    }
    await db_session.flush()

    turn_input = TurnRequestInput(
        playthrough_id=playthrough.playthrough_id,
        participant_id=participant.participant_id,
        action_text="I strike the final blow.",
    )
    response = await pipeline.run_turn(turn_input, db_session)
    [event async for event in response.body_iterator]

    stmt = select(Playthrough).where(
        Playthrough.playthrough_id == playthrough.playthrough_id
    )
    updated = (await db_session.execute(stmt)).scalars().first()
    assert updated is not None
    assert updated.ended_outcome_title == "The Ashen Ending"
    assert updated.ended_outcome_text != _VIGILS_ENDING["outcome_text"]


async def test_no_match_leaves_playthrough_active(
    db_session: AsyncSession, monkeypatch
) -> None:
    monkeypatch.setattr(
        ai_orchestrator.gemini_client,
        "generate_with_tools",
        _fake_narration("The Warden still stands."),
    )

    playthrough, participant = await _seed_master_playthrough(db_session, [])

    turn_input = TurnRequestInput(
        playthrough_id=playthrough.playthrough_id,
        participant_id=participant.participant_id,
        action_text="I swing and miss.",
    )
    response = await pipeline.run_turn(turn_input, db_session)
    events = [event async for event in response.body_iterator]

    assert [e.event for e in events] == ["narration", "turn_summary", "done"]

    stmt = select(Playthrough).where(
        Playthrough.playthrough_id == playthrough.playthrough_id
    )
    updated = (await db_session.execute(stmt)).scalars().first()
    assert updated is not None
    assert updated.status == "active"
    assert updated.ended_outcome_tag is None
    assert updated.ended_outcome_title is None
    assert updated.ended_outcome_text is None


async def test_secret_ending_matches_like_any_other(
    db_session: AsyncSession, monkeypatch
) -> None:
    monkeypatch.setattr(
        ai_orchestrator.gemini_client,
        "generate_with_tools",
        _fake_narration("The pact is sealed."),
    )

    playthrough, participant = await _seed_master_playthrough(
        db_session, [_VIGILS_ENDING]
    )
    playthrough.state = {
        "the_warden": {"health": 100},
        "flags": {"made_pact": True},
        "narrative": {"turns_so_far": []},
    }
    await db_session.flush()

    turn_input = TurnRequestInput(
        playthrough_id=playthrough.playthrough_id,
        participant_id=participant.participant_id,
        action_text="I offer the pact.",
    )
    response = await pipeline.run_turn(turn_input, db_session)
    [event async for event in response.body_iterator]

    stmt = select(Playthrough).where(
        Playthrough.playthrough_id == playthrough.playthrough_id
    )
    updated = (await db_session.execute(stmt)).scalars().first()
    assert updated is not None
    assert updated.status == "completed"
    assert updated.ended_outcome_title == "The Vigil's Ending"


async def test_post_completion_turn_is_rejected_before_state_loader(
    db_session: AsyncSession, monkeypatch
) -> None:
    playthrough, participant = await _seed_master_playthrough(db_session, [])
    playthrough.status = "completed"
    await db_session.flush()

    spy = AsyncMock(wraps=state_loader.load_state)
    monkeypatch.setattr(state_loader, "load_state", spy)

    turn_input = TurnRequestInput(
        playthrough_id=playthrough.playthrough_id,
        participant_id=participant.participant_id,
        action_text="I try to keep playing.",
    )

    with pytest.raises(PlaythroughNotActiveError):
        await pipeline.run_turn(turn_input, db_session)

    spy.assert_not_awaited()


async def test_multiplayer_fan_out_on_ended_turn(
    db_session: AsyncSession, monkeypatch
) -> None:
    monkeypatch.setattr(
        ai_orchestrator.gemini_client,
        "generate_with_tools",
        _fake_narration("The Warden falls."),
    )

    playthrough, participant_one = await _seed_master_playthrough(
        db_session, [_WARDEN_DEFEATED]
    )
    participant_two = await _add_second_participant(
        db_session, playthrough.playthrough_id
    )

    queue = notification_manager.subscribe(
        playthrough.playthrough_id, participant_two.participant_id
    )
    try:
        turn_input = TurnRequestInput(
            playthrough_id=playthrough.playthrough_id,
            participant_id=participant_one.participant_id,
            action_text="I strike the final blow.",
        )
        response = await pipeline.run_turn(turn_input, db_session)
        [event async for event in response.body_iterator]

        assert not queue.empty()
        event_name, outcome_title = queue.get_nowait()
        assert event_name == "playthrough_ended"
        assert outcome_title == "The Ashen Ending"
    finally:
        notification_manager.unsubscribe(
            playthrough.playthrough_id, participant_two.participant_id
        )
