"""Integration test running the full turn pipeline against a real test Postgres."""

import uuid
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.participant import Participant
from app.db.models.playthrough import Playthrough
from app.db.models.scenario import Scenario
from app.db.models.turn_log import TurnLog
from app.db.models.user import User
from app.exceptions.turn_exceptions import StateWriteError
from app.models.turn import TurnRequestInput
from app.session import notification_manager
from app.turn import pipeline
from app.turn.steps import ai_orchestrator

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _seed_playthrough(session: AsyncSession) -> tuple[Playthrough, Participant]:
    # IDs generated explicitly: the ORM column's default=uuid.uuid4 only fires
    # at flush/INSERT time, not at object construction.
    user_id, scenario_id = uuid.uuid4(), uuid.uuid4()
    user = User(
        user_id=user_id, display_name="Tester", auth_provider_id=str(uuid.uuid4())
    )
    scenario = Scenario(
        scenario_id=scenario_id,
        creator_id=user_id,
        title="Test Scenario",
        mode="newbie",
        complexity_tier="newbie",
        player_count_support="solo",
    )
    playthrough = Playthrough(
        scenario_id=scenario_id,
        created_by=user_id,
        scenario_version=1,
        scenario_snapshot={
            "narrator_persona": "A grim voice.",
            "world_data": "A dungeon.",
        },
        state={"setup": {}, "narrative": {"opening_prompt": None, "turns_so_far": []}},
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


async def test_run_turn_streams_narration_and_persists_turn(
    db_session: AsyncSession, monkeypatch
) -> None:
    async def fake_stream(system_instruction: str, prompt: str, timeout_seconds: int):
        yield "You step into "
        yield "the torchlit corridor."

    monkeypatch.setattr(ai_orchestrator.gemini_client, "stream_narration", fake_stream)

    playthrough, participant = await _seed_playthrough(db_session)

    turn_input = TurnRequestInput(
        playthrough_id=playthrough.playthrough_id,
        participant_id=participant.participant_id,
        action_text="I step forward.",
    )

    response = await pipeline.run_turn(turn_input, db_session)
    events = [event async for event in response.body_iterator]

    event_types = [event.event for event in events]
    assert event_types == ["narration", "narration", "done"]

    turn_log_stmt = select(TurnLog).where(
        TurnLog.playthrough_id == playthrough.playthrough_id
    )
    turn_log = (await db_session.execute(turn_log_stmt)).scalars().first()
    assert turn_log is not None
    assert turn_log.narration_text == "You step into the torchlit corridor."
    assert turn_log.action_text == "I step forward."

    playthrough_stmt = select(Playthrough).where(
        Playthrough.playthrough_id == playthrough.playthrough_id
    )
    updated = (await db_session.execute(playthrough_stmt)).scalars().first()
    assert updated is not None
    assert updated.turn_count == 1
    assert len(updated.state["narrative"]["turns_so_far"]) == 1


async def test_run_turn_degrades_gracefully_on_write_failure(
    db_session: AsyncSession, monkeypatch
) -> None:
    async def fake_stream(system_instruction: str, prompt: str, timeout_seconds: int):
        yield "Narration before the failure."

    monkeypatch.setattr(ai_orchestrator.gemini_client, "stream_narration", fake_stream)

    playthrough, participant = await _seed_playthrough(db_session)

    monkeypatch.setattr(
        pipeline.state_writer, "write_turn", AsyncMock(side_effect=StateWriteError())
    )

    turn_input = TurnRequestInput(
        playthrough_id=playthrough.playthrough_id,
        participant_id=participant.participant_id,
        action_text="I step forward.",
    )

    response = await pipeline.run_turn(turn_input, db_session)
    events = [event async for event in response.body_iterator]

    event_types = [event.event for event in events]
    assert event_types == ["narration", "degraded"]

    turn_log_stmt = select(TurnLog).where(
        TurnLog.playthrough_id == playthrough.playthrough_id
    )
    turn_log = (await db_session.execute(turn_log_stmt)).scalars().first()
    assert turn_log is None


async def test_run_turn_notifies_next_participant_in_multiplayer(
    db_session: AsyncSession, monkeypatch
) -> None:
    async def fake_stream(system_instruction: str, prompt: str, timeout_seconds: int):
        yield "The other adventurer watches."

    monkeypatch.setattr(ai_orchestrator.gemini_client, "stream_narration", fake_stream)

    playthrough, participant_one = await _seed_playthrough(db_session)
    second_user_id = uuid.uuid4()
    db_session.add(
        User(
            user_id=second_user_id,
            display_name="Second Tester",
            auth_provider_id=str(uuid.uuid4()),
        )
    )
    await db_session.flush()
    participant_two = Participant(
        playthrough_id=playthrough.playthrough_id,
        user_id=second_user_id,
        role="joined",
        turn_order_position=2,
    )
    db_session.add(participant_two)
    await db_session.flush()

    queue = notification_manager.subscribe(
        playthrough.playthrough_id, participant_two.participant_id
    )
    try:
        turn_input = TurnRequestInput(
            playthrough_id=playthrough.playthrough_id,
            participant_id=participant_one.participant_id,
            action_text="I step forward.",
        )
        response = await pipeline.run_turn(turn_input, db_session)
        [event async for event in response.body_iterator]

        assert not queue.empty()
        event_name, _ = queue.get_nowait()
        assert event_name == "your_turn"
    finally:
        notification_manager.unsubscribe(
            playthrough.playthrough_id, participant_two.participant_id
        )
