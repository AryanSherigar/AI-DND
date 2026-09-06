"""Integration tests for Minigame REST endpoints."""

import uuid
from collections.abc import Callable

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app as fastapi_app
from app.repositories.user_repo import UserRepo
from app.routers.minigames import get_http_client


@pytest.fixture
async def dev_user(db_session: AsyncSession):
    return await UserRepo(db_session).create(
        auth_provider_id=f"dev-auth-{uuid.uuid4()}", display_name="Dev Creator"
    )


@pytest.fixture
def headers(dev_user):
    return {"x-dev-user-id": str(dev_user.user_id)}


@pytest.fixture
async def master_scenario_id(async_client: httpx.AsyncClient, headers) -> str:
    response = await async_client.post(
        "/v1/scenarios",
        json={
            "title": "The Hollow Cairn",
            "mode": "master",
            "complexity_tier": "master",
        },
        headers=headers,
    )
    return response.json()["scenario_id"]


@pytest.fixture
async def newbie_scenario_id(async_client: httpx.AsyncClient, headers) -> str:
    response = await async_client.post(
        "/v1/scenarios",
        json={
            "title": "A Freeform Tale",
            "mode": "newbie",
            "complexity_tier": "newbie",
        },
        headers=headers,
    )
    return response.json()["scenario_id"]


@pytest.fixture(autouse=True)
def _clear_http_client_override():
    yield
    fastapi_app.dependency_overrides.pop(get_http_client, None)


def _override_http_client(handler: Callable[[httpx.Request], httpx.Response]) -> None:
    fastapi_app.dependency_overrides[get_http_client] = lambda: httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    )


def _binary_dodge_payload(**overrides) -> dict[str, object]:
    payload: dict[str, object] = {
        "label": "Warden's Onslaught",
        "minigame_type": "dodge",
        "outcome_mode": "binary",
        "win_mutation": {"path": "player.health", "op": "set", "value": 100},
        "lose_mutation": {"path": "player.health", "op": "decrement", "value": 15},
        "dodge_config": {"difficulty": 3},
    }
    payload.update(overrides)
    return payload


@pytest.mark.asyncio
async def test_create_minigame_rejected_on_newbie_mode_scenario(
    async_client: httpx.AsyncClient, headers, newbie_scenario_id: str
):
    response = await async_client.post(
        f"/v1/scenarios/{newbie_scenario_id}/minigames",
        json=_binary_dodge_payload(),
        headers=headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_minigame_succeeds_on_master_mode_scenario(
    async_client: httpx.AsyncClient, headers, master_scenario_id: str
):
    response = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/minigames",
        json=_binary_dodge_payload(),
        headers=headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["label"] == "Warden's Onslaught"
    assert body["minigame_type"] == "dodge"
    assert body["scenario_id"] == master_scenario_id


@pytest.mark.asyncio
async def test_binary_outcome_with_tiered_outcomes_rejected(
    async_client: httpx.AsyncClient, headers, master_scenario_id: str
):
    response = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/minigames",
        json=_binary_dodge_payload(
            tiered_outcomes=[
                {
                    "min_score": 0,
                    "max_score": 10,
                    "mutation": {"path": "player.health", "op": "set", "value": 0},
                }
            ]
        ),
        headers=headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_tiered_outcome_without_ranges_rejected(
    async_client: httpx.AsyncClient, headers, master_scenario_id: str
):
    response = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/minigames",
        json=_binary_dodge_payload(
            outcome_mode="tiered",
            win_mutation=None,
            lose_mutation=None,
            tiered_outcomes=[],
        ),
        headers=headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_dodge_type_with_replit_url_rejected(
    async_client: httpx.AsyncClient, headers, master_scenario_id: str
):
    response = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/minigames",
        json=_binary_dodge_payload(replit_embed_url="https://example.repl.co"),
        headers=headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_replit_embed_type_with_dodge_config_rejected(
    async_client: httpx.AsyncClient, headers, master_scenario_id: str
):
    _override_http_client(lambda request: httpx.Response(200))
    response = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/minigames",
        json=_binary_dodge_payload(
            minigame_type="replit_embed", replit_embed_url="https://example.repl.co"
        ),
        headers=headers,
    )
    assert response.status_code == 422


@pytest.mark.asyncio
async def test_replit_embed_unreachable_url_rejected(
    async_client: httpx.AsyncClient, headers, master_scenario_id: str
):
    _override_http_client(lambda request: httpx.Response(503))
    response = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/minigames",
        json=_binary_dodge_payload(
            minigame_type="replit_embed",
            dodge_config=None,
            replit_embed_url="https://example.repl.co",
        ),
        headers=headers,
    )
    assert response.status_code == 422
    assert "reach" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_replit_embed_reachable_url_accepted(
    async_client: httpx.AsyncClient, headers, master_scenario_id: str
):
    _override_http_client(lambda request: httpx.Response(200))
    response = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/minigames",
        json=_binary_dodge_payload(
            minigame_type="replit_embed",
            dodge_config=None,
            replit_embed_url="https://example.repl.co",
        ),
        headers=headers,
    )
    assert response.status_code == 201
    assert response.json()["replit_embed_url"] == "https://example.repl.co"


@pytest.mark.asyncio
async def test_list_minigames_priority_ordering_and_reorder(
    async_client: httpx.AsyncClient, headers, master_scenario_id: str
):
    first = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/minigames",
        json=_binary_dodge_payload(label="A", priority=0),
        headers=headers,
    )
    second = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/minigames",
        json=_binary_dodge_payload(label="B", priority=1),
        headers=headers,
    )
    first_id = first.json()["minigame_id"]
    second_id = second.json()["minigame_id"]

    list_resp = await async_client.get(
        f"/v1/scenarios/{master_scenario_id}/minigames", headers=headers
    )
    assert [m["minigame_id"] for m in list_resp.json()["items"]] == [
        first_id,
        second_id,
    ]

    reorder_resp = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/minigames/reorder",
        json={"ordered_minigame_ids": [second_id, first_id]},
        headers=headers,
    )
    assert reorder_resp.status_code == 200
    items = reorder_resp.json()["items"]
    assert [item["minigame_id"] for item in items] == [second_id, first_id]
    assert items[0]["priority"] == 0
    assert items[1]["priority"] == 1


@pytest.mark.asyncio
async def test_get_and_delete_minigame(
    async_client: httpx.AsyncClient, headers, master_scenario_id: str
):
    create_resp = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/minigames",
        json=_binary_dodge_payload(),
        headers=headers,
    )
    minigame_id = create_resp.json()["minigame_id"]

    get_resp = await async_client.get(
        f"/v1/scenarios/{master_scenario_id}/minigames/{minigame_id}", headers=headers
    )
    assert get_resp.status_code == 200

    delete_resp = await async_client.delete(
        f"/v1/scenarios/{master_scenario_id}/minigames/{minigame_id}", headers=headers
    )
    assert delete_resp.status_code == 204

    missing_resp = await async_client.get(
        f"/v1/scenarios/{master_scenario_id}/minigames/{minigame_id}", headers=headers
    )
    assert missing_resp.status_code == 404


@pytest.mark.asyncio
async def test_create_minigame_requires_authentication(
    async_client: httpx.AsyncClient, master_scenario_id: str
):
    response = await async_client.post(
        f"/v1/scenarios/{master_scenario_id}/minigames",
        json=_binary_dodge_payload(),
    )
    assert response.status_code == 401
