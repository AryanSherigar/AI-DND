"""Integration tests for the client log ingestion endpoint."""

import uuid
from datetime import UTC, datetime

import pytest
from httpx import AsyncClient


def _entry(**overrides: object) -> dict:
    base = {
        "level": "error",
        "event": "unhandled_frontend_error",
        "session_id": str(uuid.uuid4()),
        "client_timestamp": datetime.now(UTC).isoformat(),
        "fields": {"message": "boom"},
    }
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_ingest_client_logs_returns_202(async_client: AsyncClient):
    response = await async_client.post(
        "/v1/logs", json={"entries": [_entry(), _entry(event="page_viewed")]}
    )
    assert response.status_code == 202


@pytest.mark.asyncio
async def test_ingest_client_logs_accepts_unauthenticated_request(
    async_client: AsyncClient,
):
    response = await async_client.post("/v1/logs", json={"entries": [_entry()]})
    assert response.status_code == 202


@pytest.mark.asyncio
async def test_ingest_client_logs_rejects_oversized_batch(async_client: AsyncClient):
    response = await async_client.post(
        "/v1/logs", json={"entries": [_entry() for _ in range(101)]}
    )
    assert response.status_code == 422
