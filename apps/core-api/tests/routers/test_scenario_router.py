"""Integration tests for Scenario REST endpoints."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.user_repo import UserRepo


@pytest.fixture
async def dev_user(db_session: AsyncSession):
    user_repo = UserRepo(db_session)
    return await user_repo.create(
        auth_provider_id=f"dev-auth-{uuid.uuid4()}", display_name="Dev Creator"
    )


@pytest.fixture
async def dev_user2(db_session: AsyncSession):
    user_repo = UserRepo(db_session)
    return await user_repo.create(
        auth_provider_id=f"dev-auth-{uuid.uuid4()}", display_name="Dev User 2"
    )


@pytest.mark.asyncio
async def test_create_and_get_scenario_flow(
    async_client: AsyncClient, dev_user, dev_user2
):
    headers = {"x-dev-user-id": str(dev_user.user_id)}
    payload = {
        "title": "Dragon's Lair",
        "mode": "newbie",
        "complexity_tier": "intermediate",
        "logline": "Enter the lair if you dare.",
    }

    # 1. Create Scenario
    response = await async_client.post("/v1/scenarios", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "Dragon's Lair"
    assert data["status"] == "draft"
    scenario_id = data["scenario_id"]

    # 2. Get Scenario as Creator
    response = await async_client.get(f"/v1/scenarios/{scenario_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["scenario_id"] == scenario_id

    # 3. Get Scenario as Non-Creator (should return 404 for draft)
    headers2 = {"x-dev-user-id": str(dev_user2.user_id)}
    response = await async_client.get(f"/v1/scenarios/{scenario_id}", headers=headers2)
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_patch_and_delete_scenario_flow(async_client: AsyncClient, dev_user):
    headers = {"x-dev-user-id": str(dev_user.user_id)}
    create_payload = {
        "title": "Ancient Temple",
        "mode": "master",
        "complexity_tier": "master",
    }

    # 1. Create
    resp = await async_client.post(
        "/v1/scenarios", json=create_payload, headers=headers
    )
    assert resp.status_code == 201
    scenario_id = resp.json()["scenario_id"]

    # 2. Patch title (metadata) -> current_version remains 1
    patch_resp1 = await async_client.patch(
        f"/v1/scenarios/{scenario_id}",
        json={"title": "Ruined Temple"},
        headers=headers,
    )
    assert patch_resp1.status_code == 200
    assert patch_resp1.json()["title"] == "Ruined Temple"
    assert patch_resp1.json()["current_version"] == 1

    # 3. Patch narrator_persona (story) -> current_version becomes 2
    patch_resp2 = await async_client.patch(
        f"/v1/scenarios/{scenario_id}",
        json={"narrator_persona": "Spooky Narrator"},
        headers=headers,
    )
    assert patch_resp2.status_code == 200
    assert patch_resp2.json()["current_version"] == 2

    # 4. Delete scenario
    del_resp = await async_client.delete(
        f"/v1/scenarios/{scenario_id}", headers=headers
    )
    assert del_resp.status_code == 204

    # 5. Verify deleted
    get_resp = await async_client.get(f"/v1/scenarios/{scenario_id}", headers=headers)
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_list_scenarios_my_dashboard(async_client: AsyncClient, dev_user):
    headers = {"x-dev-user-id": str(dev_user.user_id)}
    # Create two draft scenarios
    await async_client.post(
        "/v1/scenarios",
        json={"title": "Draft 1", "mode": "newbie", "complexity_tier": "newbie"},
        headers=headers,
    )
    await async_client.post(
        "/v1/scenarios",
        json={"title": "Draft 2", "mode": "newbie", "complexity_tier": "newbie"},
        headers=headers,
    )

    # Fetch mine scenarios
    list_resp = await async_client.get("/v1/scenarios?mine=true", headers=headers)
    assert list_resp.status_code == 200
    data = list_resp.json()
    assert data["total_count"] >= 2
