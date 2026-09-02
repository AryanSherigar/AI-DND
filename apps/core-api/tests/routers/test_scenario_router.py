"""Integration tests for Scenario REST endpoints."""

import asyncio
import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.scenario_repo import ScenarioRepo
from app.repositories.user_repo import UserRepo


async def _poll_until_settled(
    async_client: AsyncClient, scenario_id: str, headers: dict, attempts: int = 20
) -> dict:
    """Poll GET /v1/scenarios/{id} until publish settles, mirroring a real client."""
    for _ in range(attempts):
        resp = await async_client.get(f"/v1/scenarios/{scenario_id}", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        if data["status"] != "publishing":
            return data
        await asyncio.sleep(0.05)
    raise AssertionError(f"publish never settled for scenario {scenario_id}")


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


@pytest.mark.asyncio
async def test_publish_flow_success(async_client: AsyncClient, dev_user):
    headers = {"x-dev-user-id": str(dev_user.user_id)}
    create_resp = await async_client.post(
        "/v1/scenarios",
        json={
            "title": "Publishable Tale",
            "mode": "newbie",
            "complexity_tier": "newbie",
            "content_tag": "all-ages",
        },
        headers=headers,
    )
    scenario_id = create_resp.json()["scenario_id"]

    publish_resp = await async_client.post(
        f"/v1/scenarios/{scenario_id}/publish", headers=headers
    )
    assert publish_resp.status_code == 202
    assert publish_resp.json()["status"] in ("publishing", "published")

    settled = await _poll_until_settled(async_client, scenario_id, headers)
    assert settled["status"] == "published"
    assert settled["published_at"] is not None
    assert settled["publish_error"] is None

    # Now visible in the public discovery feed.
    discovery_resp = await async_client.get("/v1/scenarios")
    assert discovery_resp.status_code == 200
    ids = [item["scenario_id"] for item in discovery_resp.json()["items"]]
    assert scenario_id in ids


@pytest.mark.asyncio
async def test_publish_flow_content_check_failure_reverts_to_draft(
    async_client: AsyncClient, dev_user
):
    headers = {"x-dev-user-id": str(dev_user.user_id)}
    create_resp = await async_client.post(
        "/v1/scenarios",
        json={"title": "Untagged Tale", "mode": "newbie", "complexity_tier": "newbie"},
        headers=headers,
    )
    scenario_id = create_resp.json()["scenario_id"]

    publish_resp = await async_client.post(
        f"/v1/scenarios/{scenario_id}/publish", headers=headers
    )
    assert publish_resp.status_code == 202

    settled = await _poll_until_settled(async_client, scenario_id, headers)
    assert settled["status"] == "draft"
    assert settled["published_at"] is None
    assert settled["publish_error"] is not None

    # Not visible in the public discovery feed.
    discovery_resp = await async_client.get("/v1/scenarios")
    ids = [item["scenario_id"] for item in discovery_resp.json()["items"]]
    assert scenario_id not in ids


@pytest.mark.asyncio
async def test_publish_rejected_while_already_publishing(
    async_client: AsyncClient, db_session: AsyncSession, dev_user
):
    # FastAPI's BackgroundTasks run to completion before the ASGI response is
    # sent (verified: not a real race under the in-process test transport),
    # so a live "publishing" window can't be caught by racing two real HTTP
    # calls here. Instead, force the in-flight state directly via the repo
    # (arrange), then exercise the real endpoint's guard (act/assert).
    headers = {"x-dev-user-id": str(dev_user.user_id)}
    create_resp = await async_client.post(
        "/v1/scenarios",
        json={
            "title": "Double Publish",
            "mode": "newbie",
            "complexity_tier": "newbie",
            "content_tag": "all-ages",
        },
        headers=headers,
    )
    scenario_id = create_resp.json()["scenario_id"]

    repo = ScenarioRepo(db_session)
    scenario = await repo.get_by_id(uuid.UUID(scenario_id))
    scenario.status = "publishing"
    await repo.update(scenario)

    resp = await async_client.post(
        f"/v1/scenarios/{scenario_id}/publish", headers=headers
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_patch_rejected_while_publishing(
    async_client: AsyncClient, db_session: AsyncSession, dev_user
):
    headers = {"x-dev-user-id": str(dev_user.user_id)}
    create_resp = await async_client.post(
        "/v1/scenarios",
        json={
            "title": "Mid Publish Edit",
            "mode": "newbie",
            "complexity_tier": "newbie",
            "content_tag": "all-ages",
        },
        headers=headers,
    )
    scenario_id = create_resp.json()["scenario_id"]

    repo = ScenarioRepo(db_session)
    scenario = await repo.get_by_id(uuid.UUID(scenario_id))
    scenario.status = "publishing"
    await repo.update(scenario)

    patch_resp = await async_client.patch(
        f"/v1/scenarios/{scenario_id}",
        json={"title": "Sneaky Edit"},
        headers=headers,
    )
    assert patch_resp.status_code == 409
