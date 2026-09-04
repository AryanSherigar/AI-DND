"""Integration tests for scenario-scoped custom entity type template endpoints."""

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
async def test_entity_type_crud_flow(
    async_client: AsyncClient, dev_user, master_scenario_id: str
):
    headers = {"x-dev-user-id": str(dev_user.user_id)}

    create_resp = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/entity-types",
        json={
            "type_key": "vehicle",
            "display_label": "Vehicle",
            "attributes_schema": {
                "speed": {"type": "number", "initial": 10},
            },
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    entity_type = create_resp.json()
    entity_type_id = entity_type["scenario_entity_type_id"]
    assert entity_type["type_key"] == "vehicle"
    assert entity_type["display_label"] == "Vehicle"

    list_resp = await async_client.get(
        f"/v1/scenarios/{master_scenario_id}/entity-types", headers=headers
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()["items"]) == 1

    patch_resp = await async_client.patch(
        f"/v1/scenarios/{master_scenario_id}/entity-types/{entity_type_id}",
        json={"display_label": "Fast Vehicle"},
        headers=headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["display_label"] == "Fast Vehicle"

    delete_resp = await async_client.delete(
        f"/v1/scenarios/{master_scenario_id}/entity-types/{entity_type_id}",
        headers=headers,
    )
    assert delete_resp.status_code == 204


@pytest.mark.asyncio
async def test_entity_type_rejects_duplicate_key(
    async_client: AsyncClient, dev_user, master_scenario_id: str
):
    headers = {"x-dev-user-id": str(dev_user.user_id)}
    payload = {
        "type_key": "vehicle",
        "display_label": "Vehicle",
        "attributes_schema": {},
    }
    first = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/entity-types",
        json=payload,
        headers=headers,
    )
    assert first.status_code == 201

    second = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/entity-types",
        json=payload,
        headers=headers,
    )
    assert second.status_code == 422


@pytest.mark.asyncio
async def test_entity_type_rejects_builtin_key(
    async_client: AsyncClient, dev_user, master_scenario_id: str
):
    headers = {"x-dev-user-id": str(dev_user.user_id)}
    response = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/entity-types",
        json={
            "type_key": "character",
            "display_label": "Character",
            "attributes_schema": {},
        },
        headers=headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_entity_type_delete_blocked_while_in_use(
    async_client: AsyncClient, dev_user, master_scenario_id: str
):
    headers = {"x-dev-user-id": str(dev_user.user_id)}
    type_resp = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/entity-types",
        json={
            "type_key": "vehicle",
            "display_label": "Vehicle",
            "attributes_schema": {},
        },
        headers=headers,
    )
    entity_type_id = type_resp.json()["scenario_entity_type_id"]

    await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/entities",
        json={"entity_type": "vehicle", "canonical_name": "The Skiff"},
        headers=headers,
    )

    delete_resp = await async_client.delete(
        f"/v1/scenarios/{master_scenario_id}/entity-types/{entity_type_id}",
        headers=headers,
    )
    assert delete_resp.status_code == 409


@pytest.mark.asyncio
async def test_entity_type_access_denied_for_non_creator(
    async_client: AsyncClient, dev_user2, master_scenario_id: str
):
    headers2 = {"x-dev-user-id": str(dev_user2.user_id)}
    response = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/entity-types",
        json={
            "type_key": "vehicle",
            "display_label": "Vehicle",
            "attributes_schema": {},
        },
        headers=headers2,
    )
    assert response.status_code == 403
