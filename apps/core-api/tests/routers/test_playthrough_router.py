"""Integration tests for Playthrough REST endpoints."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.playthrough import Playthrough
from app.db.models.scenario import Scenario
from app.db.models.turn_log import TurnLog
from app.repositories.share_repo import ShareRepo
from app.repositories.user_repo import UserRepo


@pytest.fixture
async def dev_user(db_session: AsyncSession):
    return await UserRepo(db_session).create(
        auth_provider_id=f"dev-auth-{uuid.uuid4()}", display_name="Dev Creator"
    )


@pytest.fixture
async def dev_user2(db_session: AsyncSession):
    return await UserRepo(db_session).create(
        auth_provider_id=f"dev-auth-{uuid.uuid4()}", display_name="Dev User 2"
    )


@pytest.fixture
async def published_scenario(db_session: AsyncSession, dev_user):
    scenario = Scenario(
        creator_id=dev_user.user_id,
        title="Dragon's Lair",
        mode="newbie",
        complexity_tier="newbie",
        player_count_support="solo",
        status="published",
        narrator_persona="A grim narrator.",
        world_data={"lore": "A cave full of gold."},
    )
    db_session.add(scenario)
    await db_session.flush()
    return scenario


@pytest.mark.asyncio
async def test_create_and_get_playthrough_flow(
    async_client: AsyncClient, dev_user, dev_user2, published_scenario
):
    headers = {"x-dev-user-id": str(dev_user.user_id)}

    response = await async_client.post(
        "/v1/playthroughs",
        json={"scenario_id": str(published_scenario.scenario_id), "setup_values": {}},
        headers=headers,
    )
    assert response.status_code == 201
    data = response.json()
    assert data["scenario_id"] == str(published_scenario.scenario_id)
    assert data["scenario_title"] == "Dragon's Lair"
    assert data["status"] == "active"
    playthrough_id = data["playthrough_id"]

    # Owner can fetch it.
    get_resp = await async_client.get(
        f"/v1/playthroughs/{playthrough_id}", headers=headers
    )
    assert get_resp.status_code == 200
    assert get_resp.json()["playthrough_id"] == playthrough_id

    # A non-participant is denied.
    headers2 = {"x-dev-user-id": str(dev_user2.user_id)}
    denied_resp = await async_client.get(
        f"/v1/playthroughs/{playthrough_id}", headers=headers2
    )
    assert denied_resp.status_code == 403


@pytest.mark.asyncio
async def test_get_playthrough_reports_active_conditions(
    async_client: AsyncClient, dev_user, db_session: AsyncSession
):
    """A condition's expression is re-evaluated on every GET against the
    playthrough's live state, so a returning player sees correct status
    badges immediately rather than only after their next turn."""
    from app.models.condition import ConditionCreate
    from app.repositories.condition_repo import ConditionRepo
    from app.repositories.entity_repo import EntityRepo
    from app.repositories.scenario_repo import ScenarioRepo
    from app.services.condition_service import ConditionService

    scenario = Scenario(
        creator_id=dev_user.user_id,
        title="The Hollow Cairn",
        mode="master",
        complexity_tier="master",
        player_count_support="solo",
        status="published",
        narrator_persona="Dry humor.",
        state_schema={
            "player": {"type": "object", "fields": {"health": {"type": "number"}}}
        },
    )
    db_session.add(scenario)
    await db_session.flush()

    condition_service = ConditionService(
        ConditionRepo(db_session), EntityRepo(db_session), ScenarioRepo(db_session)
    )
    await condition_service.create_condition(
        scenario.scenario_id,
        dev_user.user_id,
        ConditionCreate(
            label="Bleeding Out",
            condition_expression={"field": "player.health", "op": "<=", "value": 20},
            narrator_instruction="Describe labored breathing.",
        ),
    )

    headers = {"x-dev-user-id": str(dev_user.user_id)}
    create_resp = await async_client.post(
        "/v1/playthroughs",
        json={"scenario_id": str(scenario.scenario_id), "setup_values": {}},
        headers=headers,
    )
    playthrough_id = create_resp.json()["playthrough_id"]

    # Condition is not yet true at full health.
    healthy_resp = await async_client.get(
        f"/v1/playthroughs/{playthrough_id}", headers=headers
    )
    assert healthy_resp.json()["active_conditions"] == []

    playthrough = await db_session.get(Playthrough, uuid.UUID(playthrough_id))
    playthrough.state = {**playthrough.state, "player": {"health": 10}}
    await db_session.flush()

    bleeding_resp = await async_client.get(
        f"/v1/playthroughs/{playthrough_id}", headers=headers
    )
    assert bleeding_resp.json()["active_conditions"] == ["Bleeding Out"]


@pytest.mark.asyncio
async def test_create_playthrough_scenario_not_published(
    async_client: AsyncClient, dev_user
):
    headers = {"x-dev-user-id": str(dev_user.user_id)}
    scenario_resp = await async_client.post(
        "/v1/scenarios",
        json={
            "title": "Draft Scenario",
            "mode": "newbie",
            "complexity_tier": "newbie",
        },
        headers=headers,
    )
    scenario_id = scenario_resp.json()["scenario_id"]

    response = await async_client.post(
        "/v1/playthroughs",
        json={"scenario_id": scenario_id, "setup_values": {}},
        headers=headers,
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_create_playthrough_scenario_not_found(
    async_client: AsyncClient, dev_user
):
    headers = {"x-dev-user-id": str(dev_user.user_id)}
    response = await async_client.post(
        "/v1/playthroughs",
        json={"scenario_id": str(uuid.uuid4()), "setup_values": {}},
        headers=headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_playthrough_not_found(async_client: AsyncClient, dev_user):
    headers = {"x-dev-user-id": str(dev_user.user_id)}
    response = await async_client.get(
        f"/v1/playthroughs/{uuid.uuid4()}", headers=headers
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_list_turns_returns_paginated_history_for_participant(
    async_client: AsyncClient, dev_user, published_scenario, db_session: AsyncSession
):
    headers = {"x-dev-user-id": str(dev_user.user_id)}
    create_resp = await async_client.post(
        "/v1/playthroughs",
        json={"scenario_id": str(published_scenario.scenario_id), "setup_values": {}},
        headers=headers,
    )
    playthrough_id = create_resp.json()["playthrough_id"]

    db_session.add_all(
        [
            TurnLog(
                playthrough_id=uuid.UUID(playthrough_id),
                turn_number=n,
                action_text=f"action {n}",
                narration_text=f"narration {n}",
                tool_calls=(
                    [
                        {
                            "tool_name": "adjust_numeric_field",
                            "arguments": {"path": "player.health", "delta": -10},
                            "result": {"before": 100, "after": 90},
                            "is_valid": True,
                        }
                    ]
                    if n == 1
                    else []
                ),
            )
            for n in (1, 2, 3)
        ]
    )
    await db_session.flush()

    response = await async_client.get(
        f"/v1/playthroughs/{playthrough_id}/turns",
        params={"page": 1, "page_size": 2},
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_count"] == 3
    assert [item["turn_number"] for item in data["items"]] == [1, 2]
    first_turn_tool_calls = data["items"][0]["tool_calls"]
    assert first_turn_tool_calls[0]["tool_name"] == "adjust_numeric_field"
    assert first_turn_tool_calls[0]["arguments"] == {
        "path": "player.health",
        "delta": -10,
    }
    assert first_turn_tool_calls[0]["result"] == {"before": 100, "after": 90}
    assert first_turn_tool_calls[0]["is_valid"] is True
    assert data["items"][1]["tool_calls"] == []


@pytest.mark.asyncio
async def test_list_turns_accessible_via_valid_spectate_token(
    async_client: AsyncClient,
    dev_user,
    dev_user2,
    published_scenario,
    db_session: AsyncSession,
):
    headers = {"x-dev-user-id": str(dev_user.user_id)}
    create_resp = await async_client.post(
        "/v1/playthroughs",
        json={"scenario_id": str(published_scenario.scenario_id), "setup_values": {}},
        headers=headers,
    )
    playthrough_id = create_resp.json()["playthrough_id"]

    share = await ShareRepo(db_session).create(
        playthrough_id=uuid.UUID(playthrough_id),
        mode="spectate",
        share_token=f"tok_{uuid.uuid4()}",
    )

    # A non-participant, unauthenticated except via the share token.
    response = await async_client.get(
        f"/v1/playthroughs/{playthrough_id}/turns",
        params={"share_token": share.share_token},
    )

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_turns_denies_non_participant_without_token(
    async_client: AsyncClient, dev_user, dev_user2, published_scenario
):
    headers = {"x-dev-user-id": str(dev_user.user_id)}
    create_resp = await async_client.post(
        "/v1/playthroughs",
        json={"scenario_id": str(published_scenario.scenario_id), "setup_values": {}},
        headers=headers,
    )
    playthrough_id = create_resp.json()["playthrough_id"]

    headers2 = {"x-dev-user-id": str(dev_user2.user_id)}
    response = await async_client.get(
        f"/v1/playthroughs/{playthrough_id}/turns", headers=headers2
    )

    assert response.status_code == 403


@pytest.fixture
async def published_scenario_with_setup_schema(db_session: AsyncSession, dev_user):
    scenario = Scenario(
        creator_id=dev_user.user_id,
        title="Dragon's Lair",
        mode="newbie",
        complexity_tier="newbie",
        player_count_support="solo",
        status="published",
        narrator_persona="A grim narrator.",
        world_data={"lore": "A cave full of gold."},
        setup_schema=[
            {
                "key": "character_class",
                "label": "Class",
                "type": "single_select",
                "required": False,
                "options": ["warrior", "mage"],
            }
        ],
    )
    db_session.add(scenario)
    await db_session.flush()
    return scenario


@pytest.mark.asyncio
async def test_update_character_fields_success(
    async_client: AsyncClient, dev_user, published_scenario_with_setup_schema
):
    headers = {"x-dev-user-id": str(dev_user.user_id)}
    create_resp = await async_client.post(
        "/v1/playthroughs",
        json={
            "scenario_id": str(published_scenario_with_setup_schema.scenario_id),
            "setup_values": {"character_name": "Old Name"},
        },
        headers=headers,
    )
    playthrough_id = create_resp.json()["playthrough_id"]

    response = await async_client.patch(
        f"/v1/playthroughs/{playthrough_id}/character",
        json={
            "setup_values": {
                "character_name": "New Name",
                "character_class": "mage",
            }
        },
        headers=headers,
    )

    assert response.status_code == 200
    setup = response.json()["state"]["setup"]
    assert setup["character_name"] == "New Name"
    assert setup["character_class"] == "mage"


@pytest.mark.asyncio
async def test_update_character_fields_denied_for_non_participant(
    async_client: AsyncClient, dev_user, dev_user2, published_scenario
):
    headers = {"x-dev-user-id": str(dev_user.user_id)}
    create_resp = await async_client.post(
        "/v1/playthroughs",
        json={"scenario_id": str(published_scenario.scenario_id), "setup_values": {}},
        headers=headers,
    )
    playthrough_id = create_resp.json()["playthrough_id"]

    headers2 = {"x-dev-user-id": str(dev_user2.user_id)}
    response = await async_client.patch(
        f"/v1/playthroughs/{playthrough_id}/character",
        json={"setup_values": {"character_name": "New Name"}},
        headers=headers2,
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_update_character_fields_not_found(async_client: AsyncClient, dev_user):
    headers = {"x-dev-user-id": str(dev_user.user_id)}
    response = await async_client.patch(
        f"/v1/playthroughs/{uuid.uuid4()}/character",
        json={"setup_values": {"character_name": "New Name"}},
        headers=headers,
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_update_character_fields_invalid_setup_value(
    async_client: AsyncClient, dev_user, published_scenario_with_setup_schema
):
    headers = {"x-dev-user-id": str(dev_user.user_id)}
    create_resp = await async_client.post(
        "/v1/playthroughs",
        json={
            "scenario_id": str(published_scenario_with_setup_schema.scenario_id),
            "setup_values": {},
        },
        headers=headers,
    )
    playthrough_id = create_resp.json()["playthrough_id"]

    response = await async_client.patch(
        f"/v1/playthroughs/{playthrough_id}/character",
        json={"setup_values": {"character_class": "not_an_option"}},
        headers=headers,
    )

    assert response.status_code == 422
