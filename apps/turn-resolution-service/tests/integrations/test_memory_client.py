"""Unit tests for the real memory_client.py, with HTTP mocked via respx."""

from uuid import uuid4

import httpx
import pytest
import respx

from app.config import settings
from app.exceptions.turn_exceptions import (
    MemoryBatchNotFoundError,
    MemoryLayerUnavailableError,
)
from app.integrations import memory_client
from app.models.memory import (
    MemoryIngestRequest,
    MemoryQueryRequest,
    TurnBatchEntry,
)


@pytest.fixture(autouse=True)
def _reset_client_singleton(monkeypatch):
    """Ensure each test builds a fresh client against the current settings."""
    monkeypatch.setattr(memory_client, "_client", None)
    yield
    monkeypatch.setattr(memory_client, "_client", None)


def _query_request() -> MemoryQueryRequest:
    return MemoryQueryRequest(
        scenario_id=uuid4(),
        playthrough_id=uuid4(),
        participant_id=uuid4(),
        query_text="Where is the silver key?",
        checkpoint="entrance",
        game_state={"inventory": ["map"], "health": 100},
        as_of_turn=3,
    )


@pytest.mark.asyncio
async def test_query_memory_success_maps_fields() -> None:
    fact_id = str(uuid4())
    payload = {
        "facts": [
            {
                "fact_id": fact_id,
                "subject": "silver_key",
                "predicate": "located_in",
                "object": "the vault",
                "valid_from": "turn_1",
                "valid_until": None,
                "confidence": 0.9,
                "hidden": True,
                "when_active": {"field": "flags.vault_open", "op": "==", "value": True},
            }
        ],
        "abstained": False,
        "resolved_time_point": "3",
    }
    with respx.mock(base_url=settings.memory_service_url) as router:
        router.post("/v1/memory/query").mock(
            return_value=httpx.Response(200, json=payload)
        )
        response = await memory_client.query_memory(_query_request())

    assert response.abstained is False
    assert len(response.facts) == 1
    fact = response.facts[0]
    assert str(fact.fact_id) == fact_id
    assert fact.hidden is True
    assert fact.when_active == {"field": "flags.vault_open", "op": "==", "value": True}


@pytest.mark.asyncio
async def test_query_memory_timeout_raises_unavailable() -> None:
    with respx.mock(base_url=settings.memory_service_url) as router:
        router.post("/v1/memory/query").mock(side_effect=httpx.TimeoutException("slow"))
        with pytest.raises(MemoryLayerUnavailableError):
            await memory_client.query_memory(_query_request())


@pytest.mark.asyncio
async def test_query_memory_connect_error_raises_unavailable() -> None:
    with respx.mock(base_url=settings.memory_service_url) as router:
        router.post("/v1/memory/query").mock(side_effect=httpx.ConnectError("refused"))
        with pytest.raises(MemoryLayerUnavailableError):
            await memory_client.query_memory(_query_request())


@pytest.mark.asyncio
async def test_query_memory_server_error_raises_unavailable() -> None:
    with respx.mock(base_url=settings.memory_service_url) as router:
        router.post("/v1/memory/query").mock(return_value=httpx.Response(503))
        with pytest.raises(MemoryLayerUnavailableError):
            await memory_client.query_memory(_query_request())


@pytest.mark.asyncio
async def test_query_memory_client_error_raises_unavailable() -> None:
    with respx.mock(base_url=settings.memory_service_url) as router:
        router.post("/v1/memory/query").mock(return_value=httpx.Response(400))
        with pytest.raises(MemoryLayerUnavailableError):
            await memory_client.query_memory(_query_request())


@pytest.mark.asyncio
async def test_ingest_batch_success() -> None:
    batch_id = str(uuid4())
    request = MemoryIngestRequest(
        scenario_id=uuid4(),
        playthrough_id=uuid4(),
        turns_batch=[
            TurnBatchEntry(
                turn_number=1, text="Player enters cave", participant_id=uuid4()
            )
        ],
    )
    with respx.mock(base_url=settings.memory_service_url) as router:
        router.post("/v1/memory/ingest").mock(
            return_value=httpx.Response(202, json={"batch_id": batch_id})
        )
        response = await memory_client.ingest_batch(request)

    assert str(response.batch_id) == batch_id


@pytest.mark.asyncio
async def test_get_batch_status_success() -> None:
    batch_id = uuid4()
    with respx.mock(base_url=settings.memory_service_url) as router:
        router.get(f"/v1/memory/batch/{batch_id}/status").mock(
            return_value=httpx.Response(
                200,
                json={
                    "batch_id": str(batch_id),
                    "status": "succeeded",
                    "facts_created": 4,
                    "error": None,
                    "retryable": False,
                },
            )
        )
        status = await memory_client.get_batch_status(batch_id)

    assert status.status == "succeeded"
    assert status.facts_created == 4


@pytest.mark.asyncio
async def test_get_batch_status_not_found_raises_batch_not_found() -> None:
    batch_id = uuid4()
    with respx.mock(base_url=settings.memory_service_url) as router:
        router.get(f"/v1/memory/batch/{batch_id}/status").mock(
            return_value=httpx.Response(404)
        )
        with pytest.raises(MemoryBatchNotFoundError):
            await memory_client.get_batch_status(batch_id)


@pytest.mark.asyncio
async def test_retry_batch_not_found_raises_batch_not_found() -> None:
    batch_id = uuid4()
    with respx.mock(base_url=settings.memory_service_url) as router:
        router.post(f"/v1/memory/batch/{batch_id}/retry").mock(
            return_value=httpx.Response(404)
        )
        with pytest.raises(MemoryBatchNotFoundError):
            await memory_client.retry_batch(batch_id)


@pytest.mark.asyncio
async def test_retry_batch_success() -> None:
    batch_id = uuid4()
    with respx.mock(base_url=settings.memory_service_url) as router:
        router.post(f"/v1/memory/batch/{batch_id}/retry").mock(
            return_value=httpx.Response(200, json={"batch_id": str(batch_id)})
        )
        response = await memory_client.retry_batch(batch_id)

    assert response.batch_id == batch_id


@pytest.mark.asyncio
async def test_auth_header_sent_when_api_key_configured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "memory_service_api_key", "test-key-123")
    monkeypatch.setattr(memory_client, "_client", None)

    with respx.mock(base_url=settings.memory_service_url) as router:
        route = router.post("/v1/memory/query").mock(
            return_value=httpx.Response(
                200, json={"facts": [], "abstained": True, "resolved_time_point": None}
            )
        )
        await memory_client.query_memory(_query_request())

    assert route.calls.last.request.headers["Authorization"] == "Bearer test-key-123"


@pytest.mark.asyncio
async def test_auth_header_absent_when_api_key_not_configured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "memory_service_api_key", "")
    monkeypatch.setattr(memory_client, "_client", None)

    with respx.mock(base_url=settings.memory_service_url) as router:
        route = router.post("/v1/memory/query").mock(
            return_value=httpx.Response(
                200, json={"facts": [], "abstained": True, "resolved_time_point": None}
            )
        )
        await memory_client.query_memory(_query_request())

    assert "Authorization" not in route.calls.last.request.headers
