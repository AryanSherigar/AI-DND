"""Unit/integration tests for FactService."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.exceptions.fact_exceptions import (
    FactInvalidReferenceError,
    FactNotFoundError,
    FactValidationError,
)
from app.models.entity import EntityCreate
from app.models.fact import FactCreate, FactUpdate
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


@pytest.fixture
def fact_service(db_session: AsyncSession) -> FactService:
    return FactService(
        FactRepo(db_session), EntityRepo(db_session), ScenarioRepo(db_session)
    )


@pytest.fixture
async def warden_and_cairn(
    entity_service: EntityService, master_scenario, creator: User
):
    """Two entities from The Hollow Cairn: subject and object for fact tests."""
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
    return warden, cairn


@pytest.mark.asyncio
async def test_create_fact_with_entity_object(
    fact_service: FactService, master_scenario, creator: User, warden_and_cairn
):
    warden, cairn = warden_and_cairn
    result = await fact_service.create_fact(
        master_scenario.scenario_id,
        creator.user_id,
        FactCreate(
            subject_entity_id=warden.entity_id,
            predicate="located_at",
            object_entity_id=cairn.entity_id,
        ),
    )
    assert result.predicate == "located_at"
    assert result.object_entity_id == cairn.entity_id
    assert result.object_literal is None


@pytest.mark.asyncio
async def test_create_fact_with_literal_object(
    fact_service: FactService, master_scenario, creator: User, warden_and_cairn
):
    warden, _ = warden_and_cairn
    result = await fact_service.create_fact(
        master_scenario.scenario_id,
        creator.user_id,
        FactCreate(
            subject_entity_id=warden.entity_id,
            predicate="vulnerable_to",
            object_literal="ember_sigil_light",
            hidden=True,
        ),
    )
    assert result.object_literal == "ember_sigil_light"
    assert result.hidden is True


@pytest.mark.asyncio
async def test_create_fact_object_exclusivity_both_set(
    fact_service: FactService, master_scenario, creator: User, warden_and_cairn
):
    warden, cairn = warden_and_cairn
    with pytest.raises(FactValidationError):
        await fact_service.create_fact(
            master_scenario.scenario_id,
            creator.user_id,
            FactCreate(
                subject_entity_id=warden.entity_id,
                predicate="located_at",
                object_entity_id=cairn.entity_id,
                object_literal="also a literal",
            ),
        )


@pytest.mark.asyncio
async def test_create_fact_object_exclusivity_neither_set(
    fact_service: FactService, master_scenario, creator: User, warden_and_cairn
):
    warden, _ = warden_and_cairn
    with pytest.raises(FactValidationError):
        await fact_service.create_fact(
            master_scenario.scenario_id,
            creator.user_id,
            FactCreate(subject_entity_id=warden.entity_id, predicate="guards"),
        )


@pytest.mark.asyncio
async def test_create_fact_invalid_subject_reference(
    fact_service: FactService, master_scenario, creator: User
):
    with pytest.raises(FactInvalidReferenceError):
        await fact_service.create_fact(
            master_scenario.scenario_id,
            creator.user_id,
            FactCreate(
                subject_entity_id=uuid.uuid4(), predicate="guards", object_literal="x"
            ),
        )


@pytest.mark.asyncio
async def test_create_fact_cross_scenario_entity_reference_rejected(
    fact_service: FactService,
    entity_service: EntityService,
    master_scenario,
    creator: User,
    db_session: AsyncSession,
    warden_and_cairn,
):
    """A fact in scenario A cannot reference an entity that belongs to scenario B."""
    warden, _ = warden_and_cairn
    scenario_service = ScenarioService(ScenarioRepo(db_session))
    other_scenario = await scenario_service.create_scenario(
        creator.user_id,
        ScenarioCreate(title="Another World", mode="master", complexity_tier="master"),
    )
    foreign_entity = await entity_service.create_entity(
        other_scenario.scenario_id,
        creator.user_id,
        EntityCreate(entity_type="location", canonical_name="Elsewhere"),
    )

    with pytest.raises(FactInvalidReferenceError):
        await fact_service.create_fact(
            master_scenario.scenario_id,
            creator.user_id,
            FactCreate(
                subject_entity_id=warden.entity_id,
                predicate="located_at",
                object_entity_id=foreign_entity.entity_id,
            ),
        )


@pytest.mark.asyncio
async def test_hidden_fact_round_trip(
    fact_service: FactService, master_scenario, creator: User, warden_and_cairn
):
    warden, _ = warden_and_cairn
    created = await fact_service.create_fact(
        master_scenario.scenario_id,
        creator.user_id,
        FactCreate(
            subject_entity_id=warden.entity_id,
            predicate="vulnerable_to",
            object_literal="ember_sigil",
            hidden=True,
        ),
    )
    fetched = await fact_service.get_fact(
        master_scenario.scenario_id, created.fact_id, creator.user_id
    )
    assert fetched.hidden is True


@pytest.mark.asyncio
async def test_update_fact_self_supersession_rejected(
    fact_service: FactService, master_scenario, creator: User, warden_and_cairn
):
    warden, _ = warden_and_cairn
    created = await fact_service.create_fact(
        master_scenario.scenario_id,
        creator.user_id,
        FactCreate(
            subject_entity_id=warden.entity_id, predicate="guards", object_literal="x"
        ),
    )
    with pytest.raises(FactValidationError):
        await fact_service.update_fact(
            master_scenario.scenario_id,
            created.fact_id,
            creator.user_id,
            FactUpdate(superseded_fact_id=created.fact_id),
        )


@pytest.mark.asyncio
async def test_delete_fact(
    fact_service: FactService, master_scenario, creator: User, warden_and_cairn
):
    warden, _ = warden_and_cairn
    created = await fact_service.create_fact(
        master_scenario.scenario_id,
        creator.user_id,
        FactCreate(
            subject_entity_id=warden.entity_id, predicate="guards", object_literal="x"
        ),
    )
    await fact_service.delete_fact(
        master_scenario.scenario_id, created.fact_id, creator.user_id
    )
    with pytest.raises(FactNotFoundError):
        await fact_service.get_fact(
            master_scenario.scenario_id, created.fact_id, creator.user_id
        )
