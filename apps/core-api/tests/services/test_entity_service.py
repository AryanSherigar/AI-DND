"""Unit/integration tests for EntityService."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.exceptions.entity_exceptions import EntityNotFoundError
from app.exceptions.scenario_exceptions import (
    ScenarioAccessDeniedError,
    ScenarioNotFoundError,
)
from app.models.entity import AttributeFieldSchema, EntityCreate, EntityUpdate
from app.models.fact import FactCreate
from app.models.scenario import ScenarioCreate
from app.repositories.entity_repo import EntityRepo
from app.repositories.fact_repo import FactRepo
from app.repositories.scenario_repo import ScenarioRepo
from app.repositories.user_repo import UserRepo
from app.services.entity_service import EntityService
from app.services.fact_service import FactService
from app.services.scenario_service import ScenarioService


@pytest.fixture
async def creator(db_session: AsyncSession) -> User:
    return await UserRepo(db_session).create(
        auth_provider_id=f"test-auth-{uuid.uuid4()}", display_name="Creator"
    )


@pytest.fixture
async def other_user(db_session: AsyncSession) -> User:
    return await UserRepo(db_session).create(
        auth_provider_id=f"test-auth-{uuid.uuid4()}", display_name="Other"
    )


@pytest.fixture
async def master_scenario(db_session: AsyncSession, creator: User):
    scenario_service = ScenarioService(ScenarioRepo(db_session))
    return await scenario_service.create_scenario(
        creator.user_id,
        ScenarioCreate(
            title="The Hollow Cairn", mode="master", complexity_tier="master"
        ),
    )


@pytest.fixture
def entity_service(db_session: AsyncSession) -> EntityService:
    return EntityService(EntityRepo(db_session), ScenarioRepo(db_session))


@pytest.mark.asyncio
async def test_create_entity(
    entity_service: EntityService, master_scenario, creator: User
):
    payload = EntityCreate(
        entity_type="character",
        canonical_name="The Warden",
        aliases=["the Warden", "It"],
        description="The cairn's undying guardian.",
        attributes_schema={
            "health": AttributeFieldSchema(type="number", initial=150, min=0, max=150)
        },
        narrator_instruction="Speaks rarely; grave and formal.",
    )
    result = await entity_service.create_entity(
        master_scenario.scenario_id, creator.user_id, payload
    )

    assert result.canonical_name == "The Warden"
    assert result.entity_type == "character"
    assert result.attributes_schema["health"]["initial"] == 150
    assert result.scenario_id == master_scenario.scenario_id


@pytest.mark.asyncio
async def test_create_entity_wrong_creator_denied(
    entity_service: EntityService, master_scenario, other_user: User
):
    payload = EntityCreate(entity_type="location", canonical_name="Hollow Cairn")
    with pytest.raises(ScenarioAccessDeniedError):
        await entity_service.create_entity(
            master_scenario.scenario_id, other_user.user_id, payload
        )


@pytest.mark.asyncio
async def test_create_entity_nonexistent_scenario(
    entity_service: EntityService, creator: User
):
    payload = EntityCreate(entity_type="item", canonical_name="Ember Sigil")
    with pytest.raises(ScenarioNotFoundError):
        await entity_service.create_entity(uuid.uuid4(), creator.user_id, payload)


@pytest.mark.asyncio
async def test_list_and_get_entity(
    entity_service: EntityService, master_scenario, creator: User
):
    created = await entity_service.create_entity(
        master_scenario.scenario_id,
        creator.user_id,
        EntityCreate(entity_type="faction", canonical_name="The Vigil"),
    )

    items = await entity_service.list_entities(
        master_scenario.scenario_id, creator.user_id
    )
    assert len(items) == 1
    assert items[0].entity_id == created.entity_id

    fetched = await entity_service.get_entity(
        master_scenario.scenario_id, created.entity_id, creator.user_id
    )
    assert fetched.canonical_name == "The Vigil"


@pytest.mark.asyncio
async def test_update_entity(
    entity_service: EntityService, master_scenario, creator: User
):
    created = await entity_service.create_entity(
        master_scenario.scenario_id,
        creator.user_id,
        EntityCreate(
            entity_type="item", canonical_name="Rustbound Blade", obtainable=True
        ),
    )

    updated = await entity_service.update_entity(
        master_scenario.scenario_id,
        created.entity_id,
        creator.user_id,
        EntityUpdate(description="A plain sword, better than bare hands."),
    )
    assert updated.description == "A plain sword, better than bare hands."
    assert updated.canonical_name == "Rustbound Blade"  # untouched fields preserved


@pytest.mark.asyncio
async def test_delete_entity(
    entity_service: EntityService, master_scenario, creator: User
):
    created = await entity_service.create_entity(
        master_scenario.scenario_id,
        creator.user_id,
        EntityCreate(entity_type="character", canonical_name="Kestrel Vane"),
    )

    await entity_service.delete_entity(
        master_scenario.scenario_id, created.entity_id, creator.user_id
    )

    with pytest.raises(EntityNotFoundError):
        await entity_service.get_entity(
            master_scenario.scenario_id, created.entity_id, creator.user_id
        )


@pytest.mark.asyncio
async def test_cross_scenario_isolation(
    entity_service: EntityService,
    master_scenario,
    creator: User,
    db_session: AsyncSession,
):
    """An entity created under scenario A is not reachable via scenario B's path."""
    scenario_service = ScenarioService(ScenarioRepo(db_session))
    other_scenario = await scenario_service.create_scenario(
        creator.user_id,
        ScenarioCreate(title="Another World", mode="master", complexity_tier="master"),
    )
    created = await entity_service.create_entity(
        master_scenario.scenario_id,
        creator.user_id,
        EntityCreate(entity_type="location", canonical_name="Ashfall Village"),
    )

    with pytest.raises(EntityNotFoundError):
        await entity_service.get_entity(
            other_scenario.scenario_id, created.entity_id, creator.user_id
        )


@pytest.mark.asyncio
async def test_delete_entity_cascades_to_referencing_facts(
    entity_service: EntityService,
    master_scenario,
    creator: User,
    db_session: AsyncSession,
):
    """Deleting an entity referenced by facts as subject or object cascades (DB-level)."""
    fact_repo = FactRepo(db_session)
    fact_service = FactService(
        fact_repo, EntityRepo(db_session), ScenarioRepo(db_session)
    )

    warden = await entity_service.create_entity(
        master_scenario.scenario_id,
        creator.user_id,
        EntityCreate(entity_type="character", canonical_name="The Warden"),
    )
    cairn = await entity_service.create_entity(
        master_scenario.scenario_id,
        creator.user_id,
        EntityCreate(entity_type="location", canonical_name="Hollow Cairn"),
    )
    # cairn as object of one fact, subject of another — both must cascade.
    await fact_service.create_fact(
        master_scenario.scenario_id,
        creator.user_id,
        FactCreate(
            subject_entity_id=warden.entity_id,
            predicate="located_at",
            object_entity_id=cairn.entity_id,
        ),
    )
    await fact_service.create_fact(
        master_scenario.scenario_id,
        creator.user_id,
        FactCreate(
            subject_entity_id=cairn.entity_id,
            predicate="entrance_guarded_by",
            object_literal="the_vigil",
        ),
    )
    assert await fact_repo.count_referencing_entity(cairn.entity_id) == 2

    await entity_service.delete_entity(
        master_scenario.scenario_id, cairn.entity_id, creator.user_id
    )

    assert await fact_repo.count_referencing_entity(cairn.entity_id) == 0
