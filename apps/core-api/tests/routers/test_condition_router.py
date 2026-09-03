"""Integration tests for active Condition REST endpoints."""

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
    create_resp = await async_client.post(
        "/v1/scenarios",
        json={
            "title": "The Hollow Cairn",
            "mode": "master",
            "complexity_tier": "master",
        },
        headers=headers,
    )
    scenario_id = create_resp.json()["scenario_id"]
    await async_client.patch(
        f"/v1/scenarios/{scenario_id}",
        json={
            "state_schema": {
                "flags": {
                    "type": "object",
                    "fields": {"entered_cairn": {"type": "boolean"}},
                }
            }
        },
        headers=headers,
    )
    return scenario_id


@pytest.mark.asyncio
async def test_condition_crud_flow(
    async_client: AsyncClient, dev_user, master_scenario_id: str
):
    headers = {"x-dev-user-id": str(dev_user.user_id)}

    create_resp = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/conditions",
        json={
            "label": "Kestrel Accompanies",
            "condition_expression": {
                "field": "flags.entered_cairn",
                "op": "==",
                "value": True,
            },
            "narrator_instruction": "Kestrel Vane now travels with the player.",
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    condition_id = create_resp.json()["condition_id"]

    list_resp = await async_client.get(
        f"/v1/scenarios/{master_scenario_id}/conditions", headers=headers
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()["items"]) == 1

    delete_resp = await async_client.delete(
        f"/v1/scenarios/{master_scenario_id}/conditions/{condition_id}", headers=headers
    )
    assert delete_resp.status_code == 204


@pytest.mark.asyncio
async def test_condition_unknown_field_rejected(
    async_client: AsyncClient, dev_user, master_scenario_id: str
):
    headers = {"x-dev-user-id": str(dev_user.user_id)}
    response = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/conditions",
        json={
            "label": "Bad Condition",
            "condition_expression": {
                "field": "nonexistent.field",
                "op": "==",
                "value": True,
            },
            "narrator_instruction": "x",
        },
        headers=headers,
    )
    assert response.status_code == 422
