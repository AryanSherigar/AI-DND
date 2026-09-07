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
    """Create entities, facts, conditions, entity types, maps, pins,
    connections, and minigames on scenario_id, returning their IDs for assertions."""
    entity_type_resp = await async_client.post(
        f"/v1/scenarios/{scenario_id}/entity-types",
        json={
            "type_key": "artifact",
            "display_label": "Magical Artifact",
            "attributes_schema": {"power": {"type": "number"}},
        },
        headers=headers,
    )
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
    crypt_resp = await async_client.post(
        f"/v1/scenarios/{scenario_id}/entities",
        json={"entity_type": "location", "canonical_name": "Forgotten Crypt"},
        headers=headers,
    )
    warden_id = warden_resp.json()["entity_id"]
    cairn_id = cairn_resp.json()["entity_id"]
    crypt_id = crypt_resp.json()["entity_id"]

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
    map_resp = await async_client.post(
        f"/v1/scenarios/{scenario_id}/maps",
        json={"name": "Upper Realm", "display_order": 0},
        headers=headers,
    )
    map_id = map_resp.json()["map_id"]

    pin1_resp = await async_client.post(
        f"/v1/scenarios/{scenario_id}/maps/{map_id}/pins",
        json={
            "entity_id": cairn_id,
            "x": 0.2,
            "y": 0.4,
            "is_start_location": True,
        },
        headers=headers,
    )
    pin2_resp = await async_client.post(
        f"/v1/scenarios/{scenario_id}/maps/{map_id}/pins",
        json={
            "entity_id": crypt_id,
            "x": 0.6,
            "y": 0.8,
            "is_start_location": False,
        },
        headers=headers,
    )
    conn_resp = await async_client.post(
        f"/v1/scenarios/{scenario_id}/map-connections",
        json={
            "entity_id_a": cairn_id,
            "entity_id_b": crypt_id,
            "label": "Stone Bridge",
        },
        headers=headers,
    )
    minigame_resp = await async_client.post(
        f"/v1/scenarios/{scenario_id}/minigames",
        json={
            "label": "Dodge Falling Rocks",
            "minigame_type": "dodge",
            "dodge_config": {"difficulty": 3},
            "outcome_mode": "binary",
            "win_mutation": {"path": "player.health", "op": "set", "value": 100},
            "lose_mutation": {"path": "player.health", "op": "decrement", "value": 15},
        },
        headers=headers,
    )

    return {
        "entity_type_id": entity_type_resp.json()["scenario_entity_type_id"],
        "warden_id": warden_id,
        "cairn_id": cairn_id,
        "crypt_id": crypt_id,
        "fact_id": fact_resp.json()["fact_id"],
        "condition_id": condition_resp.json()["condition_id"],
        "end_condition_id": end_condition_resp.json()["end_condition_id"],
        "invariant_id": invariant_resp.json()["invariant_id"],
        "map_id": map_id,
        "pin1_id": pin1_resp.json()["pin_id"],
        "pin2_id": pin2_resp.json()["pin_id"],
        "connection_id": conn_resp.json()["connection_id"],
        "minigame_id": minigame_resp.json()["minigame_id"],
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
    assert len(entity_ids) == 3
    assert seeded["warden_id"] not in entity_ids
    assert seeded["cairn_id"] not in entity_ids
    assert seeded["crypt_id"] not in entity_ids

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

    # Verify entity types are deep-copied
    entity_types_resp = await async_client.get(
        f"/v1/scenarios/{new_scenario_id}/entity-types", headers=headers
    )
    entity_types = entity_types_resp.json()["items"]
    assert len(entity_types) == 1
    assert entity_types[0]["scenario_entity_type_id"] != seeded["entity_type_id"]
    assert entity_types[0]["type_key"] == "artifact"

    # Verify maps are deep-copied
    maps_resp = await async_client.get(
        f"/v1/scenarios/{new_scenario_id}/maps", headers=headers
    )
    maps = maps_resp.json()["items"]
    assert len(maps) == 1
    assert maps[0]["map_id"] != seeded["map_id"]
    assert maps[0]["name"] == "Upper Realm"
    new_map_id = maps[0]["map_id"]

    # Verify pins are deep-copied with remapped map_id and entity_id
    pins_resp = await async_client.get(
        f"/v1/scenarios/{new_scenario_id}/maps/{new_map_id}/pins", headers=headers
    )
    pins = pins_resp.json()["items"]
    assert len(pins) == 2
    pin_ids = {p["pin_id"] for p in pins}
    assert seeded["pin1_id"] not in pin_ids
    assert seeded["pin2_id"] not in pin_ids
    assert all(p["entity_id"] in entity_ids for p in pins)
    assert all(p["map_id"] == new_map_id for p in pins)
    start_pins = [p for p in pins if p["is_start_location"]]
    assert len(start_pins) == 1

    # Verify map connections are deep-copied with sorted entity pairs
    conns_resp = await async_client.get(
        f"/v1/scenarios/{new_scenario_id}/map-connections", headers=headers
    )
    conns = conns_resp.json()["items"]
    assert len(conns) == 1
    assert conns[0]["connection_id"] != seeded["connection_id"]
    assert conns[0]["label"] == "Stone Bridge"
    assert conns[0]["entity_id_a"] in entity_ids
    assert conns[0]["entity_id_b"] in entity_ids
    assert uuid.UUID(conns[0]["entity_id_a"]) < uuid.UUID(conns[0]["entity_id_b"])

    # Verify minigames are deep-copied
    minigames_resp = await async_client.get(
        f"/v1/scenarios/{new_scenario_id}/minigames", headers=headers
    )
    minigames = minigames_resp.json()["items"]
    assert len(minigames) == 1
    assert minigames[0]["minigame_id"] != seeded["minigame_id"]
    assert minigames[0]["label"] == "Dodge Falling Rocks"
    assert minigames[0]["minigame_type"] == "dodge"

    original_resp = await async_client.get(
        f"/v1/scenarios/{master_scenario_id}/entities", headers=headers
    )
    original_entity_ids = {e["entity_id"] for e in original_resp.json()["items"]}
    assert original_entity_ids == {
        seeded["warden_id"],
        seeded["cairn_id"],
        seeded["crypt_id"],
    }


@pytest.mark.asyncio
async def test_duplicate_rejects_non_owner(
    async_client: AsyncClient, dev_user2, master_scenario_id: str
):
    headers = {"x-dev-user-id": str(dev_user2.user_id)}
    response = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/duplicate", headers=headers
    )
    assert response.status_code in (403, 404)
