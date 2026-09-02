"""Integration tests for ScenarioRepo against a real test Postgres instance."""

import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.scenario import Scenario
from app.db.models.user import User
from app.repositories.scenario_repo import ScenarioRepo


async def _seed_scenario(session: AsyncSession) -> Scenario:
    # ID generated explicitly: the ORM column's default=uuid.uuid4 only fires
    # at flush/INSERT time, not at object construction.
    user_id = uuid.uuid4()
    user = User(
        user_id=user_id, display_name="Creator", auth_provider_id=str(uuid.uuid4())
    )
    scenario = Scenario(
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
    return scenario


@pytest.mark.asyncio(loop_scope="session")
async def test_increment_play_count_increments_by_one(db_session: AsyncSession) -> None:
    scenario = await _seed_scenario(db_session)
    repo = ScenarioRepo(db_session)

    await repo.increment_play_count(scenario.scenario_id)
    await db_session.flush()

    stmt = select(Scenario).where(Scenario.scenario_id == scenario.scenario_id)
    result = await db_session.execute(stmt)
    fetched = result.scalars().first()

    assert fetched is not None
    assert fetched.play_count == 1


def test_scenario_repo_exposes_only_increment_play_count() -> None:
    public_methods = [name for name in vars(ScenarioRepo) if not name.startswith("_")]

    assert public_methods == ["increment_play_count"]
