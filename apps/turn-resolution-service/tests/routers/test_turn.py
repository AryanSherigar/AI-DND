"""Integration tests for POST /v1/turn, against a real test Postgres."""

import uuid

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.participant import Participant
from app.db.models.playthrough import Playthrough
from app.db.models.scenario import Scenario
from app.db.models.user import User
from app.turn.steps import ai_orchestrator


async def _seed_playthrough(session: AsyncSession) -> tuple[Playthrough, Participant]:
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
    await session.commit()

    return playthrough, participant


async def test_submit_turn_streams_narration_and_done(
    async_client: AsyncClient, db_session: AsyncSession, monkeypatch
) -> None:
    async def fake_stream(system_instruction: str, prompt: str, timeout_seconds: int):
        yield "You step into "
        yield "the torchlit corridor."

    monkeypatch.setattr(ai_orchestrator.gemini_client, "stream_narration", fake_stream)

    playthrough, participant = await _seed_playthrough(db_session)

    response = await async_client.post(
        "/v1/turn",
        json={
            "playthrough_id": str(playthrough.playthrough_id),
            "participant_id": str(participant.participant_id),
            "action_text": "I step forward.",
        },
        headers={"x-dev-user-id": str(participant.user_id)},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    body = response.text
    assert "event: narration" in body
    assert "event: done" in body


async def test_submit_turn_requires_authentication(async_client: AsyncClient) -> None:
    response = await async_client.post(
        "/v1/turn",
        json={
            "playthrough_id": str(uuid.uuid4()),
            "participant_id": str(uuid.uuid4()),
            "action_text": "I step forward.",
        },
    )

    assert response.status_code == 401
