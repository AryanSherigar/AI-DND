"""Integration tests for Playthrough REST endpoints."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.scenario import Scenario
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
