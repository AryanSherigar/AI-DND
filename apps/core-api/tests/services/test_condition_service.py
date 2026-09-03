"""Unit/integration tests for ConditionService."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.exceptions.condition_exceptions import (
    ConditionNotFoundError,
    ConditionValidationError,
)
from app.models.condition import ConditionCreate, ConditionUpdate, StateMutation
from app.models.scenario import ScenarioCreate, ScenarioUpdate
from app.repositories.condition_repo import ConditionRepo
from app.repositories.entity_repo import EntityRepo
from app.repositories.scenario_repo import ScenarioRepo
from app.repositories.user_repo import UserRepo
from app.services.condition_service import ConditionService
from app.services.scenario_service import ScenarioService


@pytest.fixture
async def creator(db_session: AsyncSession) -> User:
    return await UserRepo(db_session).create(
        auth_provider_id=f"test-auth-{uuid.uuid4()}", display_name="Creator"
    )


@pytest.fixture
async def master_scenario(db_session: AsyncSession, creator: User):
    """A master scenario with a state_schema field, matching The Hollow Cairn."""
    scenario_service = ScenarioService(ScenarioRepo(db_session))
    created = await scenario_service.create_scenario(
        creator.user_id,
        ScenarioCreate(
            title="The Hollow Cairn", mode="master", complexity_tier="master"
        ),
    )
    return await scenario_service.update_scenario(
        created.scenario_id,
        creator.user_id,
        ScenarioUpdate(
            state_schema={
                "flags": {
                    "type": "object",
                    "fields": {"entered_cairn": {"type": "boolean"}},
                },
                "player": {"type": "object", "fields": {"sanity": {"type": "number"}}},
            }
        ),
    )


@pytest.fixture
def condition_service(db_session: AsyncSession) -> ConditionService:
    return ConditionService(
        ConditionRepo(db_session), EntityRepo(db_session), ScenarioRepo(db_session)
    )


@pytest.mark.asyncio
async def test_create_condition_narrator_only(
    condition_service: ConditionService, master_scenario, creator: User
):
    result = await condition_service.create_condition(
        master_scenario.scenario_id,
        creator.user_id,
        ConditionCreate(
            label="Kestrel Accompanies",
            condition_expression={
                "field": "flags.entered_cairn",
                "op": "==",
                "value": True,
            },
            narrator_instruction="Kestrel Vane now travels with the player.",
        ),
    )
    assert result.label == "Kestrel Accompanies"
    assert result.state_mutation is None


@pytest.mark.asyncio
async def test_create_condition_with_effect_c_mutation(
    condition_service: ConditionService, master_scenario, creator: User
):
    result = await condition_service.create_condition(
        master_scenario.scenario_id,
        creator.user_id,
        ConditionCreate(
            label="The Cairn Presses In",
            condition_expression={
                "field": "flags.entered_cairn",
                "op": "==",
                "value": True,
            },
            narrator_instruction="The cairn presses in on the player's mind.",
            state_mutation=StateMutation(path="player.sanity", op="decrement", value=2),
        ),
    )
    assert result.state_mutation == {
        "path": "player.sanity",
        "op": "decrement",
        "value": 2,
    }


@pytest.mark.asyncio
async def test_create_condition_unknown_field_rejected(
    condition_service: ConditionService, master_scenario, creator: User
):
    with pytest.raises(ConditionValidationError):
        await condition_service.create_condition(
            master_scenario.scenario_id,
            creator.user_id,
            ConditionCreate(
                label="Bad Condition",
                condition_expression={
                    "field": "nonexistent.field",
                    "op": "==",
                    "value": True,
                },
                narrator_instruction="This should never persist.",
            ),
        )


@pytest.mark.asyncio
async def test_create_condition_unknown_mutation_target_rejected(
    condition_service: ConditionService, master_scenario, creator: User
):
    with pytest.raises(ConditionValidationError):
        await condition_service.create_condition(
            master_scenario.scenario_id,
            creator.user_id,
            ConditionCreate(
                label="Bad Mutation",
                narrator_instruction="x",
                state_mutation=StateMutation(path="nowhere.field", op="set", value=1),
            ),
        )


@pytest.mark.asyncio
async def test_update_and_delete_condition(
    condition_service: ConditionService, master_scenario, creator: User
):
    created = await condition_service.create_condition(
        master_scenario.scenario_id,
        creator.user_id,
        ConditionCreate(label="Warden Is Wary", narrator_instruction="Watchful."),
    )
    updated = await condition_service.update_condition(
        master_scenario.scenario_id,
        created.condition_id,
        creator.user_id,
        ConditionUpdate(narrator_instruction="Very watchful indeed."),
    )
    assert updated.narrator_instruction == "Very watchful indeed."

    await condition_service.delete_condition(
        master_scenario.scenario_id, created.condition_id, creator.user_id
    )
    with pytest.raises(ConditionNotFoundError):
        await condition_service.get_condition(
            master_scenario.scenario_id, created.condition_id, creator.user_id
        )
