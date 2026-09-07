"""Unit/integration tests for ScenarioService."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.entity import Entity
from app.db.models.map_connection import MapConnection
from app.db.models.map_pin import MapPin
from app.db.models.scenario_entity_type import ScenarioEntityType
from app.db.models.scenario_map import ScenarioMap
from app.db.models.scenario_minigame import ScenarioMinigame
from app.db.models.user import User
from app.exceptions.scenario_exceptions import (
    ScenarioAccessDeniedError,
    ScenarioNotFoundError,
)
from app.models.scenario import ScenarioCreate, ScenarioUpdate
from app.repositories.entity_repo import EntityRepo
from app.repositories.map_repo import MapRepo
from app.repositories.minigame_repo import MinigameRepo
from app.repositories.scenario_entity_type_repo import ScenarioEntityTypeRepo
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


async def _seed_test_map_and_pins(
    db_session: AsyncSession,
    scenario_id: uuid.UUID,
    loc1_id: uuid.UUID,
    loc2_id: uuid.UUID,
) -> uuid.UUID:
    map_repo = MapRepo(db_session)
    smap = await map_repo.create_map(
        ScenarioMap(scenario_id=scenario_id, name="Citadel Map", display_order=0)
    )
    await map_repo.create_pin(
        MapPin(
            map_id=smap.map_id,
            scenario_id=scenario_id,
            entity_id=loc1_id,
            x=0.1,
            y=0.2,
            is_start_location=True,
        )
    )
    await map_repo.create_pin(
        MapPin(
            map_id=smap.map_id,
            scenario_id=scenario_id,
            entity_id=loc2_id,
            x=0.8,
            y=0.9,
            is_start_location=False,
        )
    )
    pair = sorted((loc1_id, loc2_id))
    await map_repo.create_connection(
        MapConnection(
            scenario_id=scenario_id,
            entity_id_a=pair[0],
            entity_id_b=pair[1],
            label="Main Highway",
        )
    )
    return smap.map_id


async def _seed_test_world(
    db_session: AsyncSession, scenario_id: uuid.UUID
) -> tuple[uuid.UUID, uuid.UUID]:
    et_repo = ScenarioEntityTypeRepo(db_session)
    await et_repo.create(
        ScenarioEntityType(
            scenario_id=scenario_id,
            type_key="relic",
            display_label="Relic",
            attributes_schema={},
        )
    )
    entity_repo = EntityRepo(db_session)
    loc1 = await entity_repo.create(
        Entity(
            scenario_id=scenario_id,
            entity_type="location",
            canonical_name="North Gate",
        )
    )
    loc2 = await entity_repo.create(
        Entity(
            scenario_id=scenario_id,
            entity_type="location",
            canonical_name="South Gate",
        )
    )
    minigame_repo = MinigameRepo(db_session)
    await minigame_repo.create(
        ScenarioMinigame(
            scenario_id=scenario_id,
            label="Defense",
            minigame_type="dodge",
            outcome_mode="binary",
            dodge_config={"difficulty": 2},
            win_mutation={"path": "player.health", "op": "set", "value": 100},
            lose_mutation={"path": "player.health", "op": "decrement", "value": 20},
        )
    )
    return loc1.entity_id, loc2.entity_id


@pytest.mark.asyncio
async def test_duplicate_master_scenario_sub_resources(
    db_session: AsyncSession, sample_user: User
):
    service = ScenarioService(ScenarioRepo(db_session))
    source = await service.create_scenario(
        sample_user.user_id,
        ScenarioCreate(title="Citadel", mode="master", complexity_tier="master"),
    )
    loc1_id, loc2_id = await _seed_test_world(db_session, source.scenario_id)
    await _seed_test_map_and_pins(db_session, source.scenario_id, loc1_id, loc2_id)

    dup = await service.duplicate_scenario(source.scenario_id, sample_user.user_id)
    assert dup.title == "Citadel (Copy)"

    dup_ets = await ScenarioEntityTypeRepo(db_session).list_by_scenario(dup.scenario_id)
    assert len(dup_ets) == 1 and dup_ets[0].type_key == "relic"

    dup_entities = await EntityRepo(db_session).list_by_scenario(dup.scenario_id)
    assert len(dup_entities) == 2

    dup_maps = await MapRepo(db_session).list_maps_by_scenario(dup.scenario_id)
    assert len(dup_maps) == 1 and dup_maps[0].name == "Citadel Map"

    dup_pins = await MapRepo(db_session).list_pins_by_scenario(dup.scenario_id)
    assert len(dup_pins) == 2 and sum(1 for p in dup_pins if p.is_start_location) == 1

    dup_conns = await MapRepo(db_session).list_connections_by_scenario(dup.scenario_id)
    assert len(dup_conns) == 1 and dup_conns[0].entity_id_a < dup_conns[0].entity_id_b

    dup_games = await MinigameRepo(db_session).list_by_scenario(dup.scenario_id)
    assert len(dup_games) == 1 and dup_games[0].label == "Defense"
