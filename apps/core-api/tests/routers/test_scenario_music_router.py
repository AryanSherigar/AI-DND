"""Integration tests for scenario mood-music REST endpoints."""

import uuid

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations import music_gen_client, storage_client
from app.repositories.user_repo import UserRepo


@pytest.fixture
async def dev_user(db_session: AsyncSession):
    return await UserRepo(db_session).create(
        auth_provider_id=f"dev-auth-{uuid.uuid4()}", display_name="Dev Creator"
    )


@pytest.fixture
def headers(dev_user):
    return {"x-dev-user-id": str(dev_user.user_id)}


@pytest.fixture
async def scenario_id(async_client: httpx.AsyncClient, headers) -> str:
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
def mock_upload_image(monkeypatch):
    async def _fake_upload_image(
        content: bytes, content_type: str, object_key: str
    ) -> str:
        return f"https://storage.googleapis.com/fake-bucket/{object_key}"

    monkeypatch.setattr(storage_client, "upload_image", _fake_upload_image)


@pytest.fixture
def mock_generate_music(monkeypatch):
    async def _fake_generate_music(prompt, mood, duration_seconds, timeout_seconds):
        metadata = music_gen_client.GeneratedTrackMetadata(
            key="D minor", bpm=90, duration_seconds=float(duration_seconds)
        )
        return b"fake-wav-bytes", metadata

    monkeypatch.setattr(music_gen_client, "generate_music", _fake_generate_music)


@pytest.mark.asyncio
async def test_list_scenario_music_synthesizes_all_6_defaults(
    async_client: httpx.AsyncClient, headers, scenario_id
):
    resp = await async_client.get(f"/v1/scenarios/{scenario_id}/music", headers=headers)
    assert resp.status_code == 200
    items = resp.json()["items"]
    assert len(items) == 6
    assert {item["mood"] for item in items} == {
        "peaceful",
        "mystery",
        "tension",
        "combat",
        "melancholy",
        "triumph",
    }
    assert all(item["source"] == "default" for item in items)


@pytest.mark.asyncio
async def test_set_default_track_persists(
    async_client: httpx.AsyncClient, headers, scenario_id
):
    resp = await async_client.post(
        f"/v1/scenarios/{scenario_id}/music/peaceful/default", headers=headers
    )
    assert resp.status_code == 200
    assert resp.json()["source"] == "default"

    list_resp = await async_client.get(
        f"/v1/scenarios/{scenario_id}/music", headers=headers
    )
    peaceful = next(
        item for item in list_resp.json()["items"] if item["mood"] == "peaceful"
    )
    assert peaceful["source"] == "default"


@pytest.mark.asyncio
async def test_upload_track_rejects_unsupported_format(
    async_client: httpx.AsyncClient, headers, scenario_id
):
    files = {"file": ("track.txt", b"not audio", "text/plain")}
    resp = await async_client.post(
        f"/v1/scenarios/{scenario_id}/music/tension/upload",
        headers=headers,
        files=files,
    )
    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_other_user_cannot_access_scenario_music(
    async_client: httpx.AsyncClient, scenario_id, db_session: AsyncSession
):
    other_user = await UserRepo(db_session).create(
        auth_provider_id=f"dev-auth-{uuid.uuid4()}", display_name="Someone Else"
    )
    other_headers = {"x-dev-user-id": str(other_user.user_id)}

    resp = await async_client.get(
        f"/v1/scenarios/{scenario_id}/music", headers=other_headers
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_generate_confirm_flow(
    async_client: httpx.AsyncClient,
    headers,
    scenario_id,
    mock_generate_music,
    mock_upload_image,
):
    generate_resp = await async_client.post(
        f"/v1/scenarios/{scenario_id}/music/generate",
        headers=headers,
        json={
            "mood": "combat",
            "prompt": "driving battle theme",
            "duration_seconds": 60,
        },
    )
    assert generate_resp.status_code == 202
    job_id = generate_resp.json()["job_id"]
    assert generate_resp.json()["status"] == "pending"

    job_resp = await async_client.get(
        f"/v1/scenarios/{scenario_id}/music/jobs/{job_id}", headers=headers
    )
    assert job_resp.status_code == 200
    job = job_resp.json()
    assert job["status"] == "succeeded"
    assert job["preview_url"] is not None
    assert job["key"] == "D minor"

    confirm_resp = await async_client.post(
        f"/v1/scenarios/{scenario_id}/music/jobs/{job_id}/confirm", headers=headers
    )
    assert confirm_resp.status_code == 200
    slot = confirm_resp.json()
    assert slot["mood"] == "combat"
    assert slot["source"] == "generated"
    assert slot["track_url"] == job["preview_url"]


@pytest.mark.asyncio
async def test_generate_respects_scenario_quota(
    async_client: httpx.AsyncClient,
    headers,
    scenario_id,
    mock_generate_music,
    mock_upload_image,
    monkeypatch,
):
    from app.services import music_service

    monkeypatch.setattr(music_service, "MAX_GENERATIONS_PER_SCENARIO", 1)

    first = await async_client.post(
        f"/v1/scenarios/{scenario_id}/music/generate",
        headers=headers,
        json={"mood": "combat", "prompt": "theme one", "duration_seconds": 60},
    )
    assert first.status_code == 202

    second = await async_client.post(
        f"/v1/scenarios/{scenario_id}/music/generate",
        headers=headers,
        json={"mood": "triumph", "prompt": "theme two", "duration_seconds": 60},
    )
    assert second.status_code == 429


@pytest.mark.asyncio
async def test_quota_endpoint_reports_usage(
    async_client: httpx.AsyncClient, headers, scenario_id
):
    resp = await async_client.get(
        f"/v1/scenarios/{scenario_id}/music/quota", headers=headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["scenario_generations_used"] == 0
    assert body["creator_generations_used_today"] == 0
