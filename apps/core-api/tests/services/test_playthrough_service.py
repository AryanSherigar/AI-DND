"""Unit/integration tests for PlaythroughService."""

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.scenario import Scenario
from app.exceptions.playthrough_exceptions import (
    InvalidSetupValuesError,
    PlaythroughMemoryCloneError,
    ScenarioNotPublishedError,
)
from app.exceptions.scenario_exceptions import ScenarioNotFoundError
from app.models.playthrough import PlaythroughCreate
from app.repositories.participant_repo import ParticipantRepo
from app.repositories.playthrough_repo import PlaythroughRepo
from app.repositories.scenario_repo import ScenarioRepo
from app.repositories.share_repo import ShareRepo
from app.repositories.turn_log_repo import TurnLogRepo
from app.repositories.user_repo import UserRepo
from app.services.playthrough_service import PlaythroughService


async def _make_service(db_session: AsyncSession) -> PlaythroughService:
    return PlaythroughService(
        playthrough_repo=PlaythroughRepo(db_session),
        participant_repo=ParticipantRepo(db_session),
        scenario_repo=ScenarioRepo(db_session),
        share_repo=ShareRepo(db_session),
        turn_log_repo=TurnLogRepo(db_session),
    )


async def _make_user(db_session: AsyncSession):
    return await UserRepo(db_session).create(
        auth_provider_id=f"dev-auth-{uuid.uuid4()}", display_name="Dev User"
    )


async def _make_scenario(
    db_session: AsyncSession,
    creator_id: uuid.UUID,
    status: str = "published",
    setup_schema: list[object] | None = None,
    player_count_support: str = "solo",
) -> Scenario:
    scenario = Scenario(
        creator_id=creator_id,
        title="Dragon's Lair",
        mode="newbie",
        complexity_tier="newbie",
        player_count_support=player_count_support,
        status=status,
        setup_schema=setup_schema or [],
        narrator_persona="A grim narrator.",
        world_data={"lore": "A cave full of gold."},
    )
    db_session.add(scenario)
    await db_session.flush()
    return scenario


@pytest.mark.asyncio
async def test_create_playthrough_happy_path(db_session: AsyncSession):
    service = await _make_service(db_session)
    user = await _make_user(db_session)
    scenario = await _make_scenario(db_session, user.user_id)

    result = await service.create_playthrough(
        user_id=user.user_id,
        data=PlaythroughCreate(scenario_id=scenario.scenario_id, setup_values={}),
    )

    assert result.scenario_version == scenario.current_version
    assert result.scenario_snapshot["narrator_persona"] == "A grim narrator."
    assert result.scenario_snapshot["world_data"] == {"lore": "A cave full of gold."}
    assert result.scenario_snapshot["active_conditions"] == []
    assert result.state["setup"] == {}
    assert result.status == "active"

    participant_repo = ParticipantRepo(db_session)
    participant = await participant_repo.get_by_playthrough_and_user(
        result.playthrough_id, user.user_id
    )
    assert participant is not None
    assert participant.role == "owner"
    assert participant.turn_order_position == 1


@pytest.mark.asyncio
async def test_create_playthrough_scenario_not_published(db_session: AsyncSession):
    service = await _make_service(db_session)
    user = await _make_user(db_session)
    scenario = await _make_scenario(db_session, user.user_id, status="draft")

    with pytest.raises(ScenarioNotPublishedError):
        await service.create_playthrough(
            user_id=user.user_id,
            data=PlaythroughCreate(scenario_id=scenario.scenario_id, setup_values={}),
        )


@pytest.mark.asyncio
async def test_create_playthrough_scenario_not_found(db_session: AsyncSession):
    service = await _make_service(db_session)
    user = await _make_user(db_session)

    with pytest.raises(ScenarioNotFoundError):
        await service.create_playthrough(
            user_id=user.user_id,
            data=PlaythroughCreate(scenario_id=uuid.uuid4(), setup_values={}),
        )


@pytest.mark.asyncio
async def test_create_playthrough_missing_required_setup_field(
    db_session: AsyncSession,
):
    service = await _make_service(db_session)
    user = await _make_user(db_session)
    scenario = await _make_scenario(
        db_session,
        user.user_id,
        setup_schema=[
            {"field_key": "character_class", "type": "text", "required": True}
        ],
    )

    with pytest.raises(InvalidSetupValuesError):
        await service.create_playthrough(
            user_id=user.user_id,
            data=PlaythroughCreate(scenario_id=scenario.scenario_id, setup_values={}),
        )


@pytest.mark.asyncio
async def test_create_playthrough_invalid_select_value(db_session: AsyncSession):
    service = await _make_service(db_session)
    user = await _make_user(db_session)
    scenario = await _make_scenario(
        db_session,
        user.user_id,
        setup_schema=[
            {
                "field_key": "difficulty",
                "type": "select",
                "required": True,
                "options": ["easy", "hard"],
            }
        ],
    )

    with pytest.raises(InvalidSetupValuesError):
        await service.create_playthrough(
            user_id=user.user_id,
            data=PlaythroughCreate(
                scenario_id=scenario.scenario_id,
                setup_values={"difficulty": "impossible"},
            ),
        )


@pytest.mark.asyncio
async def test_create_playthrough_memory_clone_failure_is_atomic(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
):
    service = await _make_service(db_session)
    user = await _make_user(db_session)
    scenario = await _make_scenario(db_session, user.user_id)

    async def _raise(*args, **kwargs):
        raise RuntimeError("simulated memory layer outage")

    monkeypatch.setattr(
        "app.services.playthrough_service.memory_client.clone_template_memory_space",
        _raise,
    )

    with pytest.raises(PlaythroughMemoryCloneError):
        await service.create_playthrough(
            user_id=user.user_id,
            data=PlaythroughCreate(scenario_id=scenario.scenario_id, setup_values={}),
        )

    playthroughs = await PlaythroughRepo(db_session).list_by_scenario(
        scenario.scenario_id
    )
    assert playthroughs == []


@pytest.mark.asyncio
async def test_create_multiple_concurrent_playthroughs(db_session: AsyncSession):
    service = await _make_service(db_session)
    user = await _make_user(db_session)
    scenario = await _make_scenario(db_session, user.user_id)

    first = await service.create_playthrough(
        user_id=user.user_id,
        data=PlaythroughCreate(scenario_id=scenario.scenario_id, setup_values={}),
    )
    second = await service.create_playthrough(
        user_id=user.user_id,
        data=PlaythroughCreate(scenario_id=scenario.scenario_id, setup_values={}),
    )

    assert first.playthrough_id != second.playthrough_id


@pytest.mark.asyncio
async def test_create_playthrough_multiplayer_scenario_solo_start(
    db_session: AsyncSession,
):
    service = await _make_service(db_session)
    user = await _make_user(db_session)
    scenario = await _make_scenario(
        db_session, user.user_id, player_count_support="multiplayer"
    )

    result = await service.create_playthrough(
        user_id=user.user_id,
        data=PlaythroughCreate(scenario_id=scenario.scenario_id, setup_values={}),
    )

    participants = await ParticipantRepo(db_session).list_by_playthrough(
        result.playthrough_id
    )
    assert len(participants) == 1
    assert participants[0].role == "owner"


@pytest.mark.asyncio
async def test_create_playthrough_with_multi_select_and_object_options(
    db_session: AsyncSession,
):
    service = await _make_service(db_session)
    user = await _make_user(db_session)
    scenario = await _make_scenario(
        db_session,
        user.user_id,
        setup_schema=[
            {
                "key": "role",
                "type": "single_select",
                "required": True,
                "options": [{"value": "mage", "label": "Mage"}],
            },
            {
                "key": "skills",
                "type": "multi_select",
                "required": True,
                "options": [
                    {"value": "fireball", "label": "Fireball"},
                    {"value": "teleport", "label": "Teleport"},
                ],
            },
        ],
    )

    result = await service.create_playthrough(
        user_id=user.user_id,
        data=PlaythroughCreate(
            scenario_id=scenario.scenario_id,
            setup_values={"role": "mage", "skills": ["fireball", "teleport"]},
        ),
    )

    assert result.state["setup"]["role"] == "mage"
    assert result.state["setup"]["skills"] == ["fireball", "teleport"]
