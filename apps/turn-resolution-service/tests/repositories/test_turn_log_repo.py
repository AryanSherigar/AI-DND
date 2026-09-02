"""Integration tests for TurnLogRepo against a real test Postgres instance."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.playthrough import Playthrough
from app.db.models.scenario import Scenario
from app.db.models.turn_log import TurnLog
from app.db.models.user import User
from app.repositories.turn_log_repo import TurnLogRepo

pytestmark = pytest.mark.asyncio(loop_scope="session")


async def _seed_playthrough(session: AsyncSession) -> Playthrough:
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
    session.add(user)
    await session.flush()
    session.add(scenario)
    await session.flush()

    playthrough = Playthrough(
        scenario_id=scenario_id, created_by=user_id, scenario_version=1
    )
    session.add(playthrough)
    await session.flush()
    return playthrough


async def test_create_persists_turn_log_row(db_session: AsyncSession) -> None:
    playthrough = await _seed_playthrough(db_session)
    repo = TurnLogRepo(db_session)

    created = await repo.create(
        playthrough_id=playthrough.playthrough_id,
        turn_number=1,
        participant_id=None,
        action_text="I look around.",
        narration_text="You see a torchlit corridor.",
    )

    stmt = select(TurnLog).where(TurnLog.turn_id == created.turn_id)
    result = await db_session.execute(stmt)
    fetched = result.scalars().first()

    assert fetched is not None
    assert fetched.playthrough_id == playthrough.playthrough_id
    assert fetched.turn_number == 1
    assert fetched.action_text == "I look around."
    assert fetched.narration_text == "You see a torchlit corridor."
    assert fetched.tool_calls == []
