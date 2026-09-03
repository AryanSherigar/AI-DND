"""Unit/integration tests for EndConditionService."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.user import User
from app.exceptions.end_condition_exceptions import EndConditionNotFoundError
from app.models.end_condition import EndConditionCreate
from app.models.entity import EntityCreate
from app.models.scenario import ScenarioCreate
from app.repositories.end_condition_repo import EndConditionRepo
from app.repositories.entity_repo import EntityRepo
from app.repositories.scenario_repo import ScenarioRepo
from app.repositories.user_repo import UserRepo
from app.services.end_condition_service import EndConditionService
from app.services.entity_service import EntityService
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
                "flags": {
                    "type": "object",
                    "fields": {"made_pact": {"type": "boolean"}},
                }
            },
        ),
    )


@pytest.fixture
def end_condition_service(db_session: AsyncSession) -> EndConditionService:
    return EndConditionService(
        EndConditionRepo(db_session), EntityRepo(db_session), ScenarioRepo(db_session)
    )


@pytest.mark.asyncio
async def test_multiple_win_outcomes_persisted_independently(
    end_condition_service: EndConditionService,
    master_scenario,
    creator: User,
    db_session: AsyncSession,
):
    """Two end conditions tagged 'win' on the same scenario are not deduplicated."""
    entity_service = EntityService(EntityRepo(db_session), ScenarioRepo(db_session))
    warden = await entity_service.create_entity(
        master_scenario.scenario_id,
        creator.user_id,
        EntityCreate(entity_type="character", canonical_name="The Warden"),
    )

    warden_defeated = await end_condition_service.create_end_condition(
        master_scenario.scenario_id,
        creator.user_id,
        EndConditionCreate(
            condition_expression={
                "field": f"{warden.entity_id}.health",
                "op": "<=",
                "value": 0,
            },
            outcome_tag="win",
            outcome_title="The Ashen Ending",
            outcome_text="The Warden kneels...",
            priority=0,
        ),
    )
    secret_pact = await end_condition_service.create_end_condition(
        master_scenario.scenario_id,
        creator.user_id,
        EndConditionCreate(
            condition_expression={
                "field": "flags.made_pact",
                "op": "==",
                "value": True,
            },
            outcome_tag="win",
            outcome_title="The Vigil's Ending",
            outcome_text="You do not kill the Warden...",
            is_secret=True,
            priority=1,
        ),
    )

    items = await end_condition_service.list_end_conditions(
        master_scenario.scenario_id, creator.user_id
    )
    assert len(items) == 2
    ids = {item.end_condition_id for item in items}
    assert warden_defeated.end_condition_id in ids
    assert secret_pact.end_condition_id in ids
    assert secret_pact.is_secret is True


@pytest.mark.asyncio
async def test_reorder_end_conditions(
    end_condition_service: EndConditionService, master_scenario, creator: User
):
    first = await end_condition_service.create_end_condition(
        master_scenario.scenario_id,
        creator.user_id,
        EndConditionCreate(
            outcome_tag="win", outcome_title="A", outcome_text="a", priority=0
        ),
    )
    second = await end_condition_service.create_end_condition(
        master_scenario.scenario_id,
        creator.user_id,
        EndConditionCreate(
            outcome_tag="lose", outcome_title="B", outcome_text="b", priority=1
        ),
    )

    reordered = await end_condition_service.reorder_end_conditions(
        master_scenario.scenario_id,
        creator.user_id,
        [second.end_condition_id, first.end_condition_id],
    )
    assert [item.end_condition_id for item in reordered] == [
        second.end_condition_id,
        first.end_condition_id,
    ]
    assert reordered[0].priority == 0
    assert reordered[1].priority == 1


@pytest.mark.asyncio
async def test_delete_end_condition(
    end_condition_service: EndConditionService, master_scenario, creator: User
):
    created = await end_condition_service.create_end_condition(
        master_scenario.scenario_id,
        creator.user_id,
        EndConditionCreate(
            outcome_tag="lose", outcome_title="Consumed", outcome_text="x"
        ),
    )
    await end_condition_service.delete_end_condition(
        master_scenario.scenario_id, created.end_condition_id, creator.user_id
    )
    with pytest.raises(EndConditionNotFoundError):
        await end_condition_service.get_end_condition(
            master_scenario.scenario_id, created.end_condition_id, creator.user_id
        )
