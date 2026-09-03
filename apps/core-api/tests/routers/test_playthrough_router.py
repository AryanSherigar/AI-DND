"""Integration tests for Playthrough REST endpoints."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

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
