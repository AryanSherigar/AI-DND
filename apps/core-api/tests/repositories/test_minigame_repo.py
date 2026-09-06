"""Integration tests for MinigameRepo against a real test Postgres."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.scenario import Scenario
from app.db.models.scenario_minigame import ScenarioMinigame
from app.db.models.user import User
from app.repositories.minigame_repo import MinigameRepo
from app.repositories.user_repo import UserRepo


@pytest.fixture
async def creator(db_session: AsyncSession) -> User:
    return await UserRepo(db_session).create(
        auth_provider_id=f"test-auth-{uuid.uuid4()}", display_name="Creator"
    )


@pytest.fixture
async def master_scenario(db_session: AsyncSession, creator: User) -> Scenario:
    scenario = Scenario(
        creator_id=creator.user_id,
        title="The Hollow Cairn",
        mode="master",
        complexity_tier="master",
        player_count_support="solo",
        state_schema={"player": {"type": "object", "fields": {}}},
    )
    db_session.add(scenario)
    await db_session.flush()
    return scenario


def _binary_minigame(
    scenario_id: uuid.UUID, priority: int, label: str
) -> ScenarioMinigame:
    return ScenarioMinigame(
        scenario_id=scenario_id,
        label=label,
        minigame_type="dodge",
        priority=priority,
        outcome_mode="binary",
        win_mutation={"path": "player.health", "op": "set", "value": 100},
        lose_mutation={"path": "player.health", "op": "decrement", "value": 10},
        dodge_config={"difficulty": 2},
    )


@pytest.mark.asyncio
async def test_create_and_get_by_id(
    db_session: AsyncSession, master_scenario: Scenario
):
    repo = MinigameRepo(db_session)
    created = await repo.create(_binary_minigame(master_scenario.scenario_id, 0, "A"))

    fetched = await repo.get_by_id(created.minigame_id)
    assert fetched is not None
    assert fetched.label == "A"
    assert fetched.minigame_type == "dodge"
    assert fetched.dodge_config == {"difficulty": 2}


@pytest.mark.asyncio
async def test_get_by_id_missing_returns_none(db_session: AsyncSession):
    repo = MinigameRepo(db_session)
    assert await repo.get_by_id(uuid.uuid4()) is None


@pytest.mark.asyncio
async def test_list_by_scenario_orders_by_priority_ascending(
    db_session: AsyncSession, master_scenario: Scenario
):
    repo = MinigameRepo(db_session)
    await repo.create(_binary_minigame(master_scenario.scenario_id, 5, "Third"))
    await repo.create(_binary_minigame(master_scenario.scenario_id, 1, "First"))
    await repo.create(_binary_minigame(master_scenario.scenario_id, 3, "Second"))

    items = await repo.list_by_scenario(master_scenario.scenario_id)
    assert [m.label for m in items] == ["First", "Second", "Third"]


@pytest.mark.asyncio
async def test_update_persists_changes(
    db_session: AsyncSession, master_scenario: Scenario
):
    repo = MinigameRepo(db_session)
    created = await repo.create(_binary_minigame(master_scenario.scenario_id, 0, "A"))

    created.label = "Renamed"
    updated = await repo.update(created)
    assert updated.label == "Renamed"

    refetched = await repo.get_by_id(created.minigame_id)
    assert refetched.label == "Renamed"


@pytest.mark.asyncio
async def test_delete_removes_row(db_session: AsyncSession, master_scenario: Scenario):
    repo = MinigameRepo(db_session)
    created = await repo.create(_binary_minigame(master_scenario.scenario_id, 0, "A"))

    await repo.delete(created)
    assert await repo.get_by_id(created.minigame_id) is None
