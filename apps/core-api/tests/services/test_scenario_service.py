"""Unit/integration tests for ScenarioService."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.exceptions.scenario_exceptions import (
    ScenarioAccessDeniedError,
    ScenarioNotFoundError,
)
from app.models.scenario import ScenarioCreate, ScenarioUpdate
from app.repositories.scenario_repo import ScenarioRepo
from app.repositories.user_repo import UserRepo
from app.services.scenario_service import ScenarioService


@pytest.fixture
async def sample_user(db_session: AsyncSession) -> User:
    """Fixture creating a test user."""
    user_repo = UserRepo(db_session)
    return await user_repo.create(
        auth_provider_id=f"test-auth-{uuid.uuid4()}", display_name="Creator User"
    )


@pytest.fixture
async def other_user(db_session: AsyncSession) -> User:
    """Fixture creating a secondary test user."""
    user_repo = UserRepo(db_session)
    return await user_repo.create(
        auth_provider_id=f"test-auth-{uuid.uuid4()}", display_name="Other User"
    )


@pytest.mark.asyncio
async def test_create_scenario(db_session: AsyncSession, sample_user: User):
    service = ScenarioService(ScenarioRepo(db_session))
    payload = ScenarioCreate(
        title="Dungeon Escape",
        mode="newbie",
        complexity_tier="newbie",
        logline="Escape the dark dungeon",
    )
    result = await service.create_scenario(sample_user.user_id, payload)

    assert result.title == "Dungeon Escape"
    assert result.mode == "newbie"
    assert result.status == "draft"
    assert result.current_version == 1
    assert result.creator_id == sample_user.user_id


@pytest.mark.asyncio
async def test_get_draft_scenario_access_control(
    db_session: AsyncSession, sample_user: User, other_user: User
):
    service = ScenarioService(ScenarioRepo(db_session))
    payload = ScenarioCreate(
        title="Secret Draft", mode="master", complexity_tier="master"
    )
    created = await service.create_scenario(sample_user.user_id, payload)

    # Creator gets scenario
    scen = await service.get_scenario(created.scenario_id, sample_user.user_id)
    assert scen.scenario_id == created.scenario_id

    # Non-creator gets 404
    with pytest.raises(ScenarioNotFoundError):
        await service.get_scenario(created.scenario_id, other_user.user_id)

    # Unauthenticated gets 404
    with pytest.raises(ScenarioNotFoundError):
        await service.get_scenario(created.scenario_id, None)


@pytest.mark.asyncio
async def test_update_scenario_selective_version_increment(
    db_session: AsyncSession, sample_user: User
):
    service = ScenarioService(ScenarioRepo(db_session))
    created = await service.create_scenario(
        sample_user.user_id,
        ScenarioCreate(title="Initial Title", mode="newbie", complexity_tier="newbie"),
    )
    assert created.current_version == 1

    # Metadata update does NOT increment version
    updated1 = await service.update_scenario(
        created.scenario_id,
        sample_user.user_id,
        ScenarioUpdate(title="Updated Title"),
    )
    assert updated1.title == "Updated Title"
    assert updated1.current_version == 1

    # Story field update DOES increment version
    updated2 = await service.update_scenario(
        created.scenario_id,
        sample_user.user_id,
        ScenarioUpdate(narrator_persona="Dark Narrator Persona"),
    )
    assert updated2.narrator_persona == "Dark Narrator Persona"
    assert updated2.current_version == 2


@pytest.mark.asyncio
async def test_delete_scenario_hard_vs_soft(
    db_session: AsyncSession, sample_user: User
):
    repo = ScenarioRepo(db_session)
    service = ScenarioService(repo)
    created = await service.create_scenario(
        sample_user.user_id,
        ScenarioCreate(title="Unplayed", mode="newbie", complexity_tier="newbie"),
    )

    # Hard delete scenario with 0 playthroughs
    await service.delete_scenario(created.scenario_id, sample_user.user_id)
    with pytest.raises(ScenarioNotFoundError):
        await service.get_scenario(created.scenario_id, sample_user.user_id)


@pytest.mark.asyncio
async def test_list_scenarios_mine_requires_user(db_session: AsyncSession):
    service = ScenarioService(ScenarioRepo(db_session))
    with pytest.raises(ScenarioAccessDeniedError):
        await service.list_scenarios(current_user_id=None, mine=True)
