"""Integration tests for PlaythroughRepo against a real test Postgres instance."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.playthrough import Playthrough
from app.db.models.scenario import Scenario
from app.db.models.user import User
from app.repositories.playthrough_repo import PlaythroughRepo


@pytest.fixture
async def user(db_session: AsyncSession) -> User:
    user = User(
        user_id=uuid.uuid4(),
        display_name="Tester",
        auth_provider_id=f"test-auth-{uuid.uuid4()}",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def scenario(db_session: AsyncSession, user: User) -> Scenario:
    scenario = Scenario(
        scenario_id=uuid.uuid4(),
        creator_id=user.user_id,
        title="Test Scenario",
        mode="newbie",
        complexity_tier="newbie",
        player_count_support="both",
        status="published",
    )
    db_session.add(scenario)
    await db_session.flush()
    return scenario


@pytest.fixture
async def playthrough(
    db_session: AsyncSession, user: User, scenario: Scenario
) -> Playthrough:
    playthrough = Playthrough(
        playthrough_id=uuid.uuid4(),
        scenario_id=scenario.scenario_id,
        created_by=user.user_id,
        scenario_version=1,
        state={"setup": {}},
    )
    db_session.add(playthrough)
    await db_session.flush()
    return playthrough


@pytest.mark.asyncio
async def test_get_by_id_for_update_returns_playthrough(
    db_session: AsyncSession, playthrough: Playthrough
) -> None:
    repo = PlaythroughRepo(db_session)
    result = await repo.get_by_id_for_update(playthrough.playthrough_id)
    assert result is not None
    assert result.playthrough_id == playthrough.playthrough_id


@pytest.mark.asyncio
async def test_get_by_id_for_update_returns_none_for_unknown(
    db_session: AsyncSession,
) -> None:
    repo = PlaythroughRepo(db_session)
    result = await repo.get_by_id_for_update(uuid.uuid4())
    assert result is None
