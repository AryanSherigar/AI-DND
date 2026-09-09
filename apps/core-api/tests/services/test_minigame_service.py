"""Unit/integration tests for MinigameService."""

import uuid

import httpx
import pytest
from app.db.models.user import User
from app.exceptions.minigame_exceptions import (
    MinigameModeError,
    MinigameNotFoundError,
    MinigameUnreachableError,
    MinigameValidationError,
)
from app.models.minigame import DodgeConfig, MinigameCreate
from app.models.playthrough import PlaythroughCreate
from app.models.scenario import ScenarioCreate
from app.repositories.condition_repo import ConditionRepo
from app.repositories.end_condition_repo import EndConditionRepo
from app.repositories.entity_repo import EntityRepo
from app.repositories.fact_repo import FactRepo
from app.repositories.invariant_repo import InvariantRepo
from app.repositories.map_repo import MapRepo
from app.repositories.minigame_repo import MinigameRepo
from app.repositories.participant_repo import ParticipantRepo
from app.repositories.playthrough_repo import PlaythroughRepo
from app.repositories.scenario_music_repo import ScenarioMusicRepo
from app.repositories.scenario_repo import ScenarioRepo
from app.repositories.share_repo import ShareRepo
from app.repositories.turn_log_repo import TurnLogRepo
from app.repositories.user_repo import UserRepo
from app.services.minigame_service import MinigameService
from app.services.playthrough_service import PlaythroughService
from app.services.scenario_service import ScenarioService
from sqlalchemy.ext.asyncio import AsyncSession


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
            player_count_support="solo",
            state_schema={
                "player": {"type": "object", "fields": {"health": {"type": "number"}}}
            },
        ),
    )


@pytest.fixture
async def newbie_scenario(db_session: AsyncSession, creator: User):
    scenario_service = ScenarioService(ScenarioRepo(db_session))
    return await scenario_service.create_scenario(
        creator.user_id,
        ScenarioCreate(
            title="A Freeform Tale", mode="newbie", complexity_tier="newbie"
        ),
    )


def _minigame_service(db_session: AsyncSession, handler=None) -> MinigameService:
    client = (
        httpx.AsyncClient(transport=httpx.MockTransport(handler))
        if handler
        else httpx.AsyncClient()
    )
    return MinigameService(
        MinigameRepo(db_session),
        EntityRepo(db_session),
        ScenarioRepo(db_session),
        client,
    )


def _binary_dodge_create(**overrides) -> MinigameCreate:
    defaults: dict[str, object] = {
        "label": "Warden's Onslaught",
        "minigame_type": "dodge",
        "outcome_mode": "binary",
        "win_mutation": {"path": "player.health", "op": "set", "value": 100},
        "lose_mutation": {"path": "player.health", "op": "decrement", "value": 15},
        "dodge_config": DodgeConfig(difficulty=3),
    }
    defaults.update(overrides)
    return MinigameCreate(**defaults)


def _binary_replit_create(url: str, **overrides) -> MinigameCreate:
    defaults: dict[str, object] = {
        "label": "Rune Match",
        "minigame_type": "replit_embed",
        "outcome_mode": "binary",
        "win_mutation": {"path": "player.health", "op": "set", "value": 100},
        "lose_mutation": {"path": "player.health", "op": "decrement", "value": 15},
        "replit_embed_url": url,
    }
    defaults.update(overrides)
    return MinigameCreate(**defaults)


@pytest.mark.asyncio
async def test_create_minigame_rejects_newbie_mode_scenario(
    db_session: AsyncSession, newbie_scenario, creator: User
):
    service = _minigame_service(db_session)
    with pytest.raises(MinigameModeError):
        await service.create_minigame(
            newbie_scenario.scenario_id, creator.user_id, _binary_dodge_create()
        )


@pytest.mark.asyncio
async def test_create_minigame_master_mode_succeeds(
    db_session: AsyncSession, master_scenario, creator: User
):
    service = _minigame_service(db_session)
    created = await service.create_minigame(
        master_scenario.scenario_id, creator.user_id, _binary_dodge_create()
    )
    assert created.label == "Warden's Onslaught"
    assert created.minigame_type == "dodge"
    assert created.dodge_config == DodgeConfig(difficulty=3)


@pytest.mark.asyncio
async def test_create_binary_minigame_with_tiered_outcomes_rejected():
    """Pydantic's model_validator on MinigameCreate itself rejects a binary
    outcome_mode carrying tiered_outcomes — the single source of truth for
    outcome-shape validation, exercised again at the router layer in
    test_minigame_router.py."""
    with pytest.raises(ValueError):
        _binary_dodge_create(
            tiered_outcomes=[
                {
                    "min_score": 0,
                    "max_score": 10,
                    "mutation": {"path": "player.health", "op": "set", "value": 0},
                }
            ]
        )


@pytest.mark.asyncio
async def test_create_tiered_minigame_without_outcomes_rejected():
    with pytest.raises(ValueError):
        _binary_dodge_create(
            outcome_mode="tiered",
            win_mutation=None,
            lose_mutation=None,
            tiered_outcomes=[],
        )


@pytest.mark.asyncio
async def test_create_dodge_minigame_with_replit_url_rejected():
    with pytest.raises(ValueError):
        _binary_dodge_create(replit_embed_url="https://example.repl.co")


@pytest.mark.asyncio
async def test_create_replit_minigame_with_dodge_config_rejected():
    with pytest.raises(ValueError):
        _binary_replit_create(
            "https://example.repl.co", dodge_config=DodgeConfig(difficulty=2)
        )


@pytest.mark.asyncio
async def test_trigger_expression_unknown_field_rejected(
    db_session: AsyncSession, master_scenario, creator: User
):
    service = _minigame_service(db_session)
    data = _binary_dodge_create(
        trigger_condition_expression={
            "field": "not_a_real_field",
            "op": "==",
            "value": True,
        }
    )
    with pytest.raises(MinigameValidationError):
        await service.create_minigame(
            master_scenario.scenario_id, creator.user_id, data
        )


@pytest.mark.asyncio
async def test_replit_reachability_check_fails_after_all_retries(
    db_session: AsyncSession, master_scenario, creator: User
):
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503)

    service = _minigame_service(db_session, handler)
    data = _binary_replit_create("https://example.repl.co")
    with pytest.raises(MinigameUnreachableError):
        await service.create_minigame(
            master_scenario.scenario_id, creator.user_id, data
        )


@pytest.mark.asyncio
async def test_replit_reachability_check_retries_then_succeeds(
    db_session: AsyncSession, master_scenario, creator: User
):
    attempts = {"count": 0}

    def handler(request: httpx.Request) -> httpx.Response:
        attempts["count"] += 1
        if attempts["count"] < 2:
            return httpx.Response(503)
        return httpx.Response(200)

    service = _minigame_service(db_session, handler)
    data = _binary_replit_create("https://example.repl.co")
    created = await service.create_minigame(
        master_scenario.scenario_id, creator.user_id, data
    )
    assert attempts["count"] == 2
    assert created.replit_embed_url == "https://example.repl.co"


@pytest.mark.asyncio
async def test_list_minigames_ordered_by_priority_ascending(
    db_session: AsyncSession, master_scenario, creator: User
):
    service = _minigame_service(db_session)
    await service.create_minigame(
        master_scenario.scenario_id,
        creator.user_id,
        _binary_dodge_create(label="Third", priority=5),
    )
    await service.create_minigame(
        master_scenario.scenario_id,
        creator.user_id,
        _binary_dodge_create(label="First", priority=1),
    )
    await service.create_minigame(
        master_scenario.scenario_id,
        creator.user_id,
        _binary_dodge_create(label="Second", priority=3),
    )

    items = await service.list_minigames(master_scenario.scenario_id, creator.user_id)
    assert [i.label for i in items] == ["First", "Second", "Third"]


@pytest.mark.asyncio
async def test_reorder_minigames(
    db_session: AsyncSession, master_scenario, creator: User
):
    service = _minigame_service(db_session)
    first = await service.create_minigame(
        master_scenario.scenario_id,
        creator.user_id,
        _binary_dodge_create(label="A", priority=0),
    )
    second = await service.create_minigame(
        master_scenario.scenario_id,
        creator.user_id,
        _binary_dodge_create(label="B", priority=1),
    )

    reordered = await service.reorder_minigames(
        master_scenario.scenario_id,
        creator.user_id,
        [second.minigame_id, first.minigame_id],
    )
    assert [m.minigame_id for m in reordered] == [second.minigame_id, first.minigame_id]
    assert reordered[0].priority == 0
    assert reordered[1].priority == 1


@pytest.mark.asyncio
async def test_delete_minigame(
    db_session: AsyncSession, master_scenario, creator: User
):
    service = _minigame_service(db_session)
    created = await service.create_minigame(
        master_scenario.scenario_id, creator.user_id, _binary_dodge_create()
    )
    await service.delete_minigame(
        master_scenario.scenario_id, created.minigame_id, creator.user_id
    )
    with pytest.raises(MinigameNotFoundError):
        await service.get_minigame(
            master_scenario.scenario_id, created.minigame_id, creator.user_id
        )


@pytest.mark.asyncio
async def test_update_minigame_reintroducing_invalid_shape_rejected(
    db_session: AsyncSession, master_scenario, creator: User
):
    """A PATCH that would leave the merged minigame shape invalid (dodge type
    plus a replit_embed_url) is rejected the same way a create would be."""
    from app.models.minigame import MinigameUpdate

    service = _minigame_service(db_session)
    created = await service.create_minigame(
        master_scenario.scenario_id, creator.user_id, _binary_dodge_create()
    )
    with pytest.raises(MinigameValidationError):
        await service.update_minigame(
            master_scenario.scenario_id,
            created.minigame_id,
            creator.user_id,
            MinigameUpdate(replit_embed_url="https://example.repl.co"),
        )


@pytest.mark.asyncio
async def test_playthrough_snapshot_includes_minigames_sorted_by_priority(
    db_session: AsyncSession, master_scenario, creator: User
):
    """Task 3 verification: creating a playthrough for a scenario with 2
    minigames produces scenario_snapshot["scenario_minigames"] sorted by
    priority ascending."""
    minigame_service = _minigame_service(db_session)
    await minigame_service.create_minigame(
        master_scenario.scenario_id,
        creator.user_id,
        _binary_dodge_create(label="Second", priority=4),
    )
    await minigame_service.create_minigame(
        master_scenario.scenario_id,
        creator.user_id,
        _binary_dodge_create(label="First", priority=1),
    )

    playthrough_service = PlaythroughService(
        playthrough_repo=PlaythroughRepo(db_session),
        participant_repo=ParticipantRepo(db_session),
        scenario_repo=ScenarioRepo(db_session),
        share_repo=ShareRepo(db_session),
        turn_log_repo=TurnLogRepo(db_session),
        entity_repo=EntityRepo(db_session),
        fact_repo=FactRepo(db_session),
        condition_repo=ConditionRepo(db_session),
        invariant_repo=InvariantRepo(db_session),
        end_condition_repo=EndConditionRepo(db_session),
        map_repo=MapRepo(db_session),
        minigame_repo=MinigameRepo(db_session),
        scenario_music_repo=ScenarioMusicRepo(db_session),
    )
    result = await playthrough_service.create_playthrough(
        user_id=creator.user_id,
        data=PlaythroughCreate(
            scenario_id=master_scenario.scenario_id, setup_values={}
        ),
        is_playtest=True,
    )

    minigames = result.scenario_snapshot["scenario_minigames"]
    assert [m["label"] for m in minigames] == ["First", "Second"]
    assert minigames[0]["outcome_mode"] == "binary"
    assert minigames[0]["dodge_config"]["difficulty"] == 3
