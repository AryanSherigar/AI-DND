"""Integration tests for Rule Invariant REST endpoints."""

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
                "player": {"type": "object", "fields": {"health": {"type": "number"}}}
            }
        },
        headers=headers,
    )
    return scenario_id


@pytest.mark.asyncio
async def test_invariant_crud_flow(
    async_client: AsyncClient, dev_user, master_scenario_id: str
):
    headers = {"x-dev-user-id": str(dev_user.user_id)}

    create_resp = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/invariants",
        json={
            "label": "Health cannot go negative",
            "invariant_expression": {"field": "player.health", "op": ">=", "value": 0},
            "applies_to": "global",
            "narrator_text": "Health cannot fall below zero.",
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    invariant_id = create_resp.json()["invariant_id"]

    list_resp = await async_client.get(
        f"/v1/scenarios/{master_scenario_id}/invariants", headers=headers
    )
    assert list_resp.status_code == 200
    assert len(list_resp.json()["items"]) == 1

    delete_resp = await async_client.delete(
        f"/v1/scenarios/{master_scenario_id}/invariants/{invariant_id}", headers=headers
    )
    assert delete_resp.status_code == 204


@pytest.mark.asyncio
async def test_invariant_invalid_applies_to_rejected(
    async_client: AsyncClient, dev_user, master_scenario_id: str
):
    headers = {"x-dev-user-id": str(dev_user.user_id)}
    response = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/invariants",
        json={
            "label": "Bad",
            "invariant_expression": {"field": "player.health", "op": ">=", "value": 0},
            "applies_to": "not-a-real-scope",
            "narrator_text": "x",
        },
        headers=headers,
    )
    assert response.status_code == 422
