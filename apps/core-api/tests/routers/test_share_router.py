"""Integration tests for playthrough share-link and join endpoints."""

import uuid

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.scenario import Scenario
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
async def multiplayer_scenario(db_session: AsyncSession, dev_user):
    scenario = Scenario(
        creator_id=dev_user.user_id,
        title="The Grand Bazaar",
        mode="newbie",
        complexity_tier="newbie",
        player_count_support="both",
        status="published",
        narrator_persona="A jovial narrator.",
        world_data={"lore": "A bustling market."},
    )
    db_session.add(scenario)
    await db_session.flush()
    return scenario


@pytest.fixture
async def solo_scenario(db_session: AsyncSession, dev_user):
    scenario = Scenario(
        creator_id=dev_user.user_id,
        title="The Lonely Tower",
        mode="newbie",
        complexity_tier="newbie",
        player_count_support="solo",
        status="published",
        narrator_persona="A solitary narrator.",
        world_data={"lore": "A tower with one door."},
    )
    db_session.add(scenario)
    await db_session.flush()
    return scenario


async def _create_playthrough(
    async_client: AsyncClient, scenario: Scenario, user
) -> str:
    headers = {"x-dev-user-id": str(user.user_id)}
    response = await async_client.post(
        "/v1/playthroughs",
        json={"scenario_id": str(scenario.scenario_id), "setup_values": {}},
        headers=headers,
    )
    assert response.status_code == 201
    return response.json()["playthrough_id"]


@pytest.mark.asyncio
async def test_create_share_returns_token_and_url(
    async_client: AsyncClient, dev_user, multiplayer_scenario
):
    playthrough_id = await _create_playthrough(
        async_client, multiplayer_scenario, dev_user
    )
    headers = {"x-dev-user-id": str(dev_user.user_id)}

    response = await async_client.post(
        f"/v1/playthroughs/{playthrough_id}/share",
        json={"mode": "spectate"},
        headers=headers,
    )

    assert response.status_code == 201
    data = response.json()
    assert data["mode"] == "spectate"
    assert data["playthrough_id"] == playthrough_id
    assert data["share_token"] in data["url"]


@pytest.mark.asyncio
async def test_create_share_is_idempotent_per_mode(
    async_client: AsyncClient, dev_user, multiplayer_scenario
):
    playthrough_id = await _create_playthrough(
        async_client, multiplayer_scenario, dev_user
    )
    headers = {"x-dev-user-id": str(dev_user.user_id)}

    first = await async_client.post(
        f"/v1/playthroughs/{playthrough_id}/share",
        json={"mode": "join"},
        headers=headers,
    )
    second = await async_client.post(
        f"/v1/playthroughs/{playthrough_id}/share",
        json={"mode": "join"},
        headers=headers,
    )

    assert first.json()["share_token"] == second.json()["share_token"]


@pytest.mark.asyncio
async def test_create_share_denied_for_non_participant(
    async_client: AsyncClient, dev_user, dev_user2, multiplayer_scenario
):
    playthrough_id = await _create_playthrough(
        async_client, multiplayer_scenario, dev_user
    )
    headers2 = {"x-dev-user-id": str(dev_user2.user_id)}

    response = await async_client.post(
        f"/v1/playthroughs/{playthrough_id}/share",
        json={"mode": "spectate"},
        headers=headers2,
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_join_playthrough_adds_participant(
    async_client: AsyncClient, dev_user, dev_user2, multiplayer_scenario
):
    playthrough_id = await _create_playthrough(
        async_client, multiplayer_scenario, dev_user
    )
    headers = {"x-dev-user-id": str(dev_user.user_id)}
    share_resp = await async_client.post(
        f"/v1/playthroughs/{playthrough_id}/share",
        json={"mode": "join"},
        headers=headers,
    )
    share_token = share_resp.json()["share_token"]

    headers2 = {"x-dev-user-id": str(dev_user2.user_id)}
    join_resp = await async_client.post(
        "/v1/playthroughs/join",
        json={"share_token": share_token},
        headers=headers2,
    )

    assert join_resp.status_code == 200
    assert join_resp.json()["playthrough_id"] == playthrough_id

    # The newly joined participant can now fetch the playthrough.
    get_resp = await async_client.get(
        f"/v1/playthroughs/{playthrough_id}", headers=headers2
    )
    assert get_resp.status_code == 200


@pytest.mark.asyncio
async def test_join_playthrough_rejects_solo_scenario(
    async_client: AsyncClient, dev_user, dev_user2, solo_scenario
):
    playthrough_id = await _create_playthrough(async_client, solo_scenario, dev_user)
    headers = {"x-dev-user-id": str(dev_user.user_id)}
    share_resp = await async_client.post(
        f"/v1/playthroughs/{playthrough_id}/share",
        json={"mode": "join"},
        headers=headers,
    )
    share_token = share_resp.json()["share_token"]

    headers2 = {"x-dev-user-id": str(dev_user2.user_id)}
    join_resp = await async_client.post(
        "/v1/playthroughs/join",
        json={"share_token": share_token},
        headers=headers2,
    )

    assert join_resp.status_code == 409


@pytest.mark.asyncio
async def test_join_playthrough_rejects_unknown_token(
    async_client: AsyncClient, dev_user2
):
    headers2 = {"x-dev-user-id": str(dev_user2.user_id)}
    response = await async_client.post(
        "/v1/playthroughs/join",
        json={"share_token": "not-a-real-token"},
        headers=headers2,
    )

    assert response.status_code == 404
