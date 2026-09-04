"""Integration tests for Fact REST endpoints."""

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


@pytest.fixture
async def warden_and_cairn_ids(
    async_client: AsyncClient, dev_user, master_scenario_id: str
) -> tuple[str, str]:
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
    return warden.json()["entity_id"], cairn.json()["entity_id"]


@pytest.mark.asyncio
async def test_fact_crud_flow(
    async_client: AsyncClient, dev_user, master_scenario_id: str, warden_and_cairn_ids
):
    headers = {"x-dev-user-id": str(dev_user.user_id)}
    warden_id, cairn_id = warden_and_cairn_ids

    create_resp = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/facts",
        json={
            "subject_entity_id": warden_id,
            "predicate": "located_at",
            "object_entity_id": cairn_id,
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    fact_id = create_resp.json()["fact_id"]

    list_resp = await async_client.get(
        f"/v1/scenarios/{master_scenario_id}/facts", headers=headers
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()["items"]) == 1

    patch_resp = await async_client.patch(
        f"/v1/scenarios/{master_scenario_id}/facts/{fact_id}",
        json={"hidden": True},
        headers=headers,
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["hidden"] is True

    delete_resp = await async_client.delete(
        f"/v1/scenarios/{master_scenario_id}/facts/{fact_id}", headers=headers
    )
    assert delete_resp.status_code == 204


@pytest.mark.asyncio
async def test_fact_object_exclusivity_rejected(
    async_client: AsyncClient, dev_user, master_scenario_id: str, warden_and_cairn_ids
):
    headers = {"x-dev-user-id": str(dev_user.user_id)}
    warden_id, cairn_id = warden_and_cairn_ids

    response = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/facts",
        json={
            "subject_entity_id": warden_id,
            "predicate": "located_at",
            "object_entity_id": cairn_id,
            "object_literal": "also set",
        },
        headers=headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_fact_list_filters_by_entity_id(
    async_client: AsyncClient, dev_user, master_scenario_id: str, warden_and_cairn_ids
):
    headers = {"x-dev-user-id": str(dev_user.user_id)}
    warden_id, cairn_id = warden_and_cairn_ids

    linked = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/facts",
        json={
            "subject_entity_id": warden_id,
            "predicate": "located_at",
            "object_entity_id": cairn_id,
        },
        headers=headers,
    )
    assert linked.status_code == 201

    unrelated = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/facts",
        json={
            "subject_entity_id": cairn_id,
            "predicate": "described_as",
            "object_literal": "ancient and cold",
        },
        headers=headers,
    )
    assert unrelated.status_code == 201

    filtered_by_warden = await async_client.get(
        f"/v1/scenarios/{master_scenario_id}/facts",
        params={"entity_id": warden_id},
        headers=headers,
    )
    assert filtered_by_warden.status_code == 200
    warden_items = filtered_by_warden.json()["items"]
    assert len(warden_items) == 1
    assert warden_items[0]["subject_entity_id"] == warden_id

    filtered_by_cairn = await async_client.get(
        f"/v1/scenarios/{master_scenario_id}/facts",
        params={"entity_id": cairn_id},
        headers=headers,
    )
    assert filtered_by_cairn.status_code == 200
    assert len(filtered_by_cairn.json()["items"]) == 2

    unfiltered = await async_client.get(
        f"/v1/scenarios/{master_scenario_id}/facts", headers=headers
    )
    assert len(unfiltered.json()["items"]) == 2


@pytest.mark.asyncio
async def test_fact_invalid_entity_reference_rejected(
    async_client: AsyncClient, dev_user, master_scenario_id: str
):
    headers = {"x-dev-user-id": str(dev_user.user_id)}
    response = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/facts",
        json={
            "subject_entity_id": str(uuid.uuid4()),
            "predicate": "guards",
            "object_literal": "x",
        },
        headers=headers,
    )
    assert response.status_code == 422
