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
async def test_entity_fact_count_reflects_facts_as_subject_or_object(
    async_client: AsyncClient, dev_user, master_scenario_id: str
):
    headers = {"x-dev-user-id": str(dev_user.user_id)}

    warden = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/entities",
        json={"entity_type": "character", "canonical_name": "The Warden"},
        headers=headers,
    )
    cairn = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/entities",
        json={"entity_type": "location", "canonical_name": "Hollow Cairn"},
        headers=headers,
    )
    warden_id = warden.json()["entity_id"]
    cairn_id = cairn.json()["entity_id"]

    assert warden.json()["fact_count"] == 0

    await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/facts",
        json={
            "subject_entity_id": warden_id,
            "predicate": "located_at",
            "object_entity_id": cairn_id,
        },
        headers=headers,
    )
    await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/facts",
        json={
            "subject_entity_id": warden_id,
            "predicate": "guards",
            "object_literal": "the gate",
        },
        headers=headers,
    )

    list_resp = await async_client.get(
        f"/v1/scenarios/{master_scenario_id}/entities", headers=headers
    )
    by_id = {item["entity_id"]: item for item in list_resp.json()["items"]}
    assert by_id[warden_id]["fact_count"] == 2
    assert by_id[cairn_id]["fact_count"] == 1

    get_resp = await async_client.get(
        f"/v1/scenarios/{master_scenario_id}/entities/{warden_id}", headers=headers
    )
    assert get_resp.json()["fact_count"] == 2


@pytest.mark.asyncio
async def test_entity_rejects_undefined_custom_type(
    async_client: AsyncClient, dev_user, master_scenario_id: str
):
    headers = {"x-dev-user-id": str(dev_user.user_id)}
    response = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/entities",
        json={"entity_type": "vehicle", "canonical_name": "The Skiff"},
        headers=headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_entity_accepts_defined_custom_type(
    async_client: AsyncClient, dev_user, master_scenario_id: str
):
    headers = {"x-dev-user-id": str(dev_user.user_id)}
    type_resp = await async_client.post(
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
    assert type_resp.status_code == 201

    entity_resp = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/entities",
        json={"entity_type": "vehicle", "canonical_name": "The Skiff"},
        headers=headers,
    )
    assert entity_resp.status_code == 201
    assert entity_resp.json()["entity_type"] == "vehicle"


@pytest.mark.asyncio
async def test_entity_type_change_preview_flags_dropped_and_added_fields(
    async_client: AsyncClient, dev_user, master_scenario_id: str
):
    headers = {"x-dev-user-id": str(dev_user.user_id)}
    await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/entity-types",
        json={
            "type_key": "vehicle",
            "display_label": "Vehicle",
            "attributes_schema": {
                "speed": {"type": "number", "initial": 10},
                "fuel": {"type": "number", "initial": 100},
            },
        },
        headers=headers,
    )
    entity_resp = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/entities",
        json={
            "entity_type": "character",
            "canonical_name": "The Warden",
            "attributes_schema": {
                "health": {"type": "number", "initial": 150},
                "fuel": {"type": "number", "initial": 0},
            },
        },
        headers=headers,
    )
    entity_id = entity_resp.json()["entity_id"]

    preview_resp = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/entities/{entity_id}/type-change-preview",
        json={"new_entity_type": "vehicle"},
        headers=headers,
    )
    assert preview_resp.status_code == 200
    preview = preview_resp.json()
    assert preview["dropped_fields"] == ["health"]
    assert preview["retained_fields"] == ["fuel"]
    assert preview["added_fields"] == ["speed"]

    # Committing the type change does not auto-migrate attributes_schema.
    patch_resp = await async_client.patch(
        f"/v1/scenarios/{master_scenario_id}/entities/{entity_id}",
        json={"entity_type": "vehicle"},
        headers=headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["entity_type"] == "vehicle"
    assert "health" in patch_resp.json()["attributes_schema"]


@pytest.mark.asyncio
async def test_entity_type_change_preview_to_builtin_type_has_no_constraints(
    async_client: AsyncClient, dev_user, master_scenario_id: str
):
    headers = {"x-dev-user-id": str(dev_user.user_id)}
    entity_resp = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/entities",
        json={
            "entity_type": "location",
            "canonical_name": "Hollow Cairn",
            "attributes_schema": {
                "crowd_level": {"type": "number", "initial": 0},
            },
        },
        headers=headers,
    )
    entity_id = entity_resp.json()["entity_id"]

    preview_resp = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/entities/{entity_id}/type-change-preview",
        json={"new_entity_type": "character"},
        headers=headers,
    )
    assert preview_resp.status_code == 200
    preview = preview_resp.json()
    assert preview["dropped_fields"] == []
    assert preview["retained_fields"] == ["crowd_level"]


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
