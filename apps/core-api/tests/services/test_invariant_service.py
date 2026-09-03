"""Unit/integration tests for InvariantService."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.exceptions.invariant_exceptions import (
    InvariantNotFoundError,
    InvariantValidationError,
)
from app.models.entity import EntityCreate
from app.models.invariant import InvariantCreate, InvariantUpdate
from app.models.scenario import ScenarioCreate
from app.repositories.entity_repo import EntityRepo
from app.repositories.invariant_repo import InvariantRepo
from app.repositories.scenario_repo import ScenarioRepo
from app.repositories.user_repo import UserRepo
from app.services.entity_service import EntityService
from app.services.invariant_service import InvariantService
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
            title="The Hollow Cairn",
            mode="master",
            complexity_tier="master",
            state_schema={
                "player": {
                    "type": "object",
                    "fields": {
                        "health": {"type": "number"},
                        "max_health": {"type": "number"},
                    },
                }
            },
        ),
    )


@pytest.fixture
def entity_service(db_session: AsyncSession) -> EntityService:
    return EntityService(EntityRepo(db_session), ScenarioRepo(db_session))


@pytest.fixture
def invariant_service(db_session: AsyncSession) -> InvariantService:
    return InvariantService(
        InvariantRepo(db_session), EntityRepo(db_session), ScenarioRepo(db_session)
    )


@pytest.mark.asyncio
async def test_create_invariant_applies_to_player(
    invariant_service: InvariantService, master_scenario, creator: User
):
    result = await invariant_service.create_invariant(
        master_scenario.scenario_id,
        creator.user_id,
        InvariantCreate(
            label="Health cannot exceed its cap",
            invariant_expression={
                "field": "player.health",
                "op": "<=",
                "value": "player.max_health",
            },
            applies_to="player",
            narrator_text="Health can never be restored beyond its maximum.",
        ),
    )
    assert result.applies_to == "player"


@pytest.mark.asyncio
async def test_create_invariant_applies_to_entity(
    invariant_service: InvariantService,
    entity_service: EntityService,
    master_scenario,
    creator: User,
):
    warden = await entity_service.create_entity(
        master_scenario.scenario_id,
        creator.user_id,
        EntityCreate(entity_type="character", canonical_name="The Warden"),
    )
    result = await invariant_service.create_invariant(
        master_scenario.scenario_id,
        creator.user_id,
        InvariantCreate(
            label="Warden cannot go below zero health",
            invariant_expression={"field": "player.health", "op": ">=", "value": 0},
            applies_to=str(warden.entity_id),
            narrator_text="The Warden cannot fall below zero health.",
        ),
    )
    assert result.applies_to == str(warden.entity_id)


@pytest.mark.asyncio
async def test_create_invariant_invalid_applies_to_rejected(
    invariant_service: InvariantService, master_scenario, creator: User
):
    with pytest.raises(InvariantValidationError):
        await invariant_service.create_invariant(
            master_scenario.scenario_id,
            creator.user_id,
            InvariantCreate(
                label="Bad",
                invariant_expression={"field": "player.health", "op": ">=", "value": 0},
                applies_to="not-a-real-entity-or-scope",
                narrator_text="x",
            ),
        )


@pytest.mark.asyncio
async def test_create_invariant_unknown_field_rejected(
    invariant_service: InvariantService, master_scenario, creator: User
):
    with pytest.raises(InvariantValidationError):
        await invariant_service.create_invariant(
            master_scenario.scenario_id,
            creator.user_id,
            InvariantCreate(
                label="Bad",
                invariant_expression={
                    "field": "nowhere.field",
                    "op": "==",
                    "value": True,
                },
                applies_to="global",
                narrator_text="x",
            ),
        )


@pytest.mark.asyncio
async def test_update_and_delete_invariant(
    invariant_service: InvariantService, master_scenario, creator: User
):
    created = await invariant_service.create_invariant(
        master_scenario.scenario_id,
        creator.user_id,
        InvariantCreate(
            label="Health cap",
            invariant_expression={"field": "player.health", "op": "<=", "value": 100},
            applies_to="global",
            narrator_text="x",
        ),
    )
    updated = await invariant_service.update_invariant(
        master_scenario.scenario_id,
        created.invariant_id,
        creator.user_id,
        InvariantUpdate(narrator_text="Updated narration."),
    )
    assert updated.narrator_text == "Updated narration."

    await invariant_service.delete_invariant(
        master_scenario.scenario_id, created.invariant_id, creator.user_id
    )
    with pytest.raises(InvariantNotFoundError):
        await invariant_service.get_invariant(
            master_scenario.scenario_id, created.invariant_id, creator.user_id
        )
