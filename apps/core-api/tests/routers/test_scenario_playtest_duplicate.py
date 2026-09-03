"""Integration tests for the playtest and duplicate scenario endpoints."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.playthrough import Playthrough
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
    scenario_id = response.json()["scenario_id"]
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


async def _seed_master_world(
    async_client: AsyncClient, headers: dict, scenario_id: str
) -> dict[str, str]:
    """Create one entity, one fact, one condition, one end condition, and one
    invariant on scenario_id, returning their IDs for post-duplicate assertions."""
    warden_resp = await async_client.post(
        f"/v1/scenarios/{scenario_id}/entities",
        json={"entity_type": "character", "canonical_name": "The Warden"},
        headers=headers,
    )
    cairn_resp = await async_client.post(
        f"/v1/scenarios/{scenario_id}/entities",
        json={"entity_type": "location", "canonical_name": "Hollow Cairn"},
        headers=headers,
    )
    warden_id = warden_resp.json()["entity_id"]
    cairn_id = cairn_resp.json()["entity_id"]

    fact_resp = await async_client.post(
        f"/v1/scenarios/{scenario_id}/facts",
        json={
            "subject_entity_id": warden_id,
            "predicate": "guards",
            "object_entity_id": cairn_id,
        },
        headers=headers,
    )
    condition_resp = await async_client.post(
        f"/v1/scenarios/{scenario_id}/conditions",
        json={
            "label": "Warden Is Wary",
            "condition_expression": {
                "field": "player.health",
                "op": ">=",
                "value": 0,
            },
            "narrator_instruction": "The Warden watches.",
        },
        headers=headers,
    )
    end_condition_resp = await async_client.post(
        f"/v1/scenarios/{scenario_id}/end_conditions",
        json={
            "condition_expression": {"field": "player.health", "op": "<=", "value": 0},
            "outcome_tag": "lose",
            "outcome_title": "Consumed",
            "outcome_text": "Ashfall waits.",
        },
        headers=headers,
    )
    invariant_resp = await async_client.post(
        f"/v1/scenarios/{scenario_id}/invariants",
        json={
            "label": "Health cannot go negative",
            "invariant_expression": {
                "field": "player.health",
                "op": ">=",
                "value": 0,
            },
            "applies_to": "global",
            "narrator_text": "Health cannot fall below zero.",
        },
        headers=headers,
    )

    return {
        "warden_id": warden_id,
        "cairn_id": cairn_id,
        "fact_id": fact_resp.json()["fact_id"],
        "condition_id": condition_resp.json()["condition_id"],
        "end_condition_id": end_condition_resp.json()["end_condition_id"],
        "invariant_id": invariant_resp.json()["invariant_id"],
    }


@pytest.mark.asyncio
async def test_playtest_creates_is_playtest_playthrough(
    async_client: AsyncClient,
    dev_user,
    master_scenario_id: str,
    db_session: AsyncSession,
):
    headers = {"x-dev-user-id": str(dev_user.user_id)}

    response = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/playtest", headers=headers
    )
    assert response.status_code == 201
    data = response.json()
    assert data["is_playtest"] is True
    assert data["scenario_id"] == master_scenario_id

    stmt = select(Playthrough).where(
        Playthrough.playthrough_id == uuid.UUID(data["playthrough_id"])
    )
    playthrough = (await db_session.execute(stmt)).scalars().first()
    assert playthrough is not None
    assert playthrough.is_playtest is True


@pytest.mark.asyncio
async def test_playtest_rejects_non_owner(
    async_client: AsyncClient, dev_user2, master_scenario_id: str
):
    headers = {"x-dev-user-id": str(dev_user2.user_id)}
    response = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/playtest", headers=headers
    )
    assert response.status_code in (403, 404)


@pytest.mark.asyncio
async def test_playtest_excluded_from_rating_eligibility(
    async_client: AsyncClient,
    dev_user,
    master_scenario_id: str,
    db_session: AsyncSession,
):
    headers = {"x-dev-user-id": str(dev_user.user_id)}
    response = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/playtest", headers=headers
    )
    playthrough_id = response.json()["playthrough_id"]

    stmt = select(Playthrough).where(
        Playthrough.playthrough_id == uuid.UUID(playthrough_id)
    )
    playthrough = (await db_session.execute(stmt)).scalars().first()
    playthrough.turn_count = 15
    await db_session.flush()

    review_resp = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/reviews",
        json={"rating": 5, "comment": "Great!"},
        headers=headers,
    )
    assert review_resp.status_code == 403


@pytest.mark.asyncio
async def test_duplicate_deep_copies_master_mode_resources(
    async_client: AsyncClient, dev_user, master_scenario_id: str
):
    headers = {"x-dev-user-id": str(dev_user.user_id)}
    seeded = await _seed_master_world(async_client, headers, master_scenario_id)

    dup_resp = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/duplicate", headers=headers
    )
    assert dup_resp.status_code == 201
    new_scenario = dup_resp.json()
    assert new_scenario["scenario_id"] != master_scenario_id
    assert new_scenario["status"] == "draft"
    assert new_scenario["creator_id"] == str(dev_user.user_id)

    new_scenario_id = new_scenario["scenario_id"]

    entities_resp = await async_client.get(
        f"/v1/scenarios/{new_scenario_id}/entities", headers=headers
    )
    entity_ids = {e["entity_id"] for e in entities_resp.json()["items"]}
    assert len(entity_ids) == 2
    assert seeded["warden_id"] not in entity_ids
    assert seeded["cairn_id"] not in entity_ids

    facts_resp = await async_client.get(
        f"/v1/scenarios/{new_scenario_id}/facts", headers=headers
    )
    facts = facts_resp.json()["items"]
    assert len(facts) == 1
    assert facts[0]["fact_id"] != seeded["fact_id"]
    assert facts[0]["subject_entity_id"] in entity_ids
    assert facts[0]["object_entity_id"] in entity_ids

    conditions_resp = await async_client.get(
        f"/v1/scenarios/{new_scenario_id}/conditions", headers=headers
    )
    assert len(conditions_resp.json()["items"]) == 1
    assert conditions_resp.json()["items"][0]["condition_id"] != seeded["condition_id"]

    end_conditions_resp = await async_client.get(
        f"/v1/scenarios/{new_scenario_id}/end_conditions", headers=headers
    )
    assert len(end_conditions_resp.json()["items"]) == 1
    assert (
        end_conditions_resp.json()["items"][0]["end_condition_id"]
        != seeded["end_condition_id"]
    )

    invariants_resp = await async_client.get(
        f"/v1/scenarios/{new_scenario_id}/invariants", headers=headers
    )
    assert len(invariants_resp.json()["items"]) == 1
    assert invariants_resp.json()["items"][0]["invariant_id"] != seeded["invariant_id"]

    original_resp = await async_client.get(
        f"/v1/scenarios/{master_scenario_id}/entities", headers=headers
    )
    original_entity_ids = {e["entity_id"] for e in original_resp.json()["items"]}
    assert original_entity_ids == {seeded["warden_id"], seeded["cairn_id"]}


@pytest.mark.asyncio
async def test_duplicate_rejects_non_owner(
    async_client: AsyncClient, dev_user2, master_scenario_id: str
):
    headers = {"x-dev-user-id": str(dev_user2.user_id)}
    response = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/duplicate", headers=headers
    )
    assert response.status_code in (403, 404)
