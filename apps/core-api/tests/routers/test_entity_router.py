"""Integration tests for Entity REST endpoints."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

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
async def master_scenario_id(async_client: AsyncClient, dev_user) -> str:
    headers = {"x-dev-user-id": str(dev_user.user_id)}
    response = await async_client.post(
        "/v1/scenarios",
        json={
            "title": "The Hollow Cairn",
            "mode": "master",
            "complexity_tier": "master",
        },
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()["scenario_id"]


@pytest.mark.asyncio
async def test_entity_crud_flow(
    async_client: AsyncClient, dev_user, master_scenario_id: str
):
    headers = {"x-dev-user-id": str(dev_user.user_id)}

    # Create
    create_resp = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/entities",
        json={
            "entity_type": "character",
            "canonical_name": "The Warden",
            "attributes_schema": {
                "health": {"type": "number", "initial": 150, "min": 0, "max": 150}
            },
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    entity = create_resp.json()
    entity_id = entity["entity_id"]
    assert entity["canonical_name"] == "The Warden"

    # List
    list_resp = await async_client.get(
        f"/v1/scenarios/{master_scenario_id}/entities", headers=headers
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()["items"]) == 1

    # Get
    get_resp = await async_client.get(
        f"/v1/scenarios/{master_scenario_id}/entities/{entity_id}", headers=headers
    )
    assert get_resp.status_code == 200

    # Update
    patch_resp = await async_client.patch(
        f"/v1/scenarios/{master_scenario_id}/entities/{entity_id}",
        json={"description": "The cairn's undying guardian."},
        headers=headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["description"] == "The cairn's undying guardian."

    # Delete
    delete_resp = await async_client.delete(
        f"/v1/scenarios/{master_scenario_id}/entities/{entity_id}", headers=headers
    )
    assert delete_resp.status_code == 204

    get_after_delete = await async_client.get(
        f"/v1/scenarios/{master_scenario_id}/entities/{entity_id}", headers=headers
    )
    assert get_after_delete.status_code == 404


@pytest.mark.asyncio
async def test_entity_access_denied_for_non_creator(
    async_client: AsyncClient, dev_user2, master_scenario_id: str
):
    headers2 = {"x-dev-user-id": str(dev_user2.user_id)}
    response = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/entities",
        json={"entity_type": "item", "canonical_name": "Ember Sigil"},
        headers=headers2,
    )
    assert response.status_code == 403
