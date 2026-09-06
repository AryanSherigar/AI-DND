"""Unit tests for the real memory_client.py, with mem1's HTTP surface mocked via respx."""

import json
from uuid import UUID, uuid4

import httpx
import pytest
import respx

from app.config import settings
from app.exceptions.memory_exceptions import (
    MemoryBatchNotFoundError,
    MemoryLayerUnavailableError,
)
from app.integrations import memory_client
from app.models.memory import (
    EntityIngestPayload,
    FactIngestPayload,
    MemoryIngestRequest,
    MemoryQueryRequest,
    MemoryTemplateCloneRequest,
    MemoryTemplateIngestRequest,
    TurnBatchEntry,
)

BASE_URL = settings.memory_service_url


@pytest.fixture(autouse=True)
def _reset_client_singleton():
    memory_client._client = None
    yield
    memory_client._client = None


def _query_request() -> MemoryQueryRequest:
    return MemoryQueryRequest(
        scenario_id=uuid4(),
        playthrough_id=uuid4(),
        participant_id=uuid4(),
        query_text="Who is the village elder?",
        checkpoint="start",
        game_state={"reputation": 10},
    )


@pytest.mark.asyncio
@respx.mock
async def test_query_memory_success_maps_fields() -> None:
    fact_id = str(uuid4())
    route = respx.post(f"{BASE_URL}/v1/memory/query").mock(
        return_value=httpx.Response(
            200,
            json={
                "facts": [
                    {
                        "fact_id": fact_id,
                        "subject": "Elder",
                        "predicate": "lives_in",
                        "object": "the village",
                        "valid_from": None,
                        "valid_until": None,
                        "confidence": 0.9,
                        "hidden": True,
                    }
                ],
                "abstained": False,
                "resolved_time_point": "5",
            },
        )
    )

    response = await memory_client.query_memory(_query_request())

    assert route.called
    assert response.abstained is False
    fact = response.facts[0]
    assert fact.fact_id == UUID(fact_id)
    assert fact.hidden is True


@pytest.mark.asyncio
@respx.mock
async def test_query_memory_timeout_raises_unavailable() -> None:
    respx.post(f"{BASE_URL}/v1/memory/query").mock(
        side_effect=httpx.TimeoutException("slow")
    )

    with pytest.raises(MemoryLayerUnavailableError):
        await memory_client.query_memory(_query_request())


@pytest.mark.asyncio
@respx.mock
async def test_query_memory_connect_error_raises_unavailable() -> None:
    respx.post(f"{BASE_URL}/v1/memory/query").mock(
        side_effect=httpx.ConnectError("refused")
    )

    with pytest.raises(MemoryLayerUnavailableError):
        await memory_client.query_memory(_query_request())


@pytest.mark.asyncio
@respx.mock
async def test_query_memory_server_error_raises_unavailable() -> None:
    respx.post(f"{BASE_URL}/v1/memory/query").mock(return_value=httpx.Response(503))

    with pytest.raises(MemoryLayerUnavailableError):
        await memory_client.query_memory(_query_request())


@pytest.mark.asyncio
@respx.mock
async def test_query_memory_client_error_raises_unavailable() -> None:
    respx.post(f"{BASE_URL}/v1/memory/query").mock(return_value=httpx.Response(400))

    with pytest.raises(MemoryLayerUnavailableError):
        await memory_client.query_memory(_query_request())


@pytest.mark.asyncio
@respx.mock
async def test_ingest_batch_success() -> None:
    batch_id = str(uuid4())
    respx.post(f"{BASE_URL}/v1/memory/ingest").mock(
        return_value=httpx.Response(202, json={"batch_id": batch_id})
    )
    request = MemoryIngestRequest(
        scenario_id=uuid4(),
        playthrough_id=uuid4(),
        turns_batch=[TurnBatchEntry(turn_number=1, text="hi", participant_id=uuid4())],
    )

    response = await memory_client.ingest_batch(request)

    assert response.batch_id == UUID(batch_id)


@pytest.mark.asyncio
@respx.mock
async def test_get_batch_status_success() -> None:
    batch_id = uuid4()
    respx.get(f"{BASE_URL}/v1/memory/batch/{batch_id}/status").mock(
        return_value=httpx.Response(
            200,
            json={
                "batch_id": str(batch_id),
                "status": "succeeded",
                "facts_created": 3,
                "error": None,
                "retryable": False,
            },
        )
    )

    status = await memory_client.get_batch_status(batch_id)

    assert status.status == "succeeded"
    assert status.facts_created == 3


@pytest.mark.asyncio
@respx.mock
async def test_get_batch_status_not_found() -> None:
    batch_id = uuid4()
    respx.get(f"{BASE_URL}/v1/memory/batch/{batch_id}/status").mock(
        return_value=httpx.Response(404)
    )

    with pytest.raises(MemoryBatchNotFoundError):
        await memory_client.get_batch_status(batch_id)


@pytest.mark.asyncio
@respx.mock
async def test_retry_batch_success() -> None:
    batch_id = uuid4()
    respx.post(f"{BASE_URL}/v1/memory/batch/{batch_id}/retry").mock(
        return_value=httpx.Response(200, json={"batch_id": str(batch_id)})
    )

    response = await memory_client.retry_batch(batch_id)

    assert response.batch_id == batch_id


@pytest.mark.asyncio
@respx.mock
async def test_retry_batch_not_found() -> None:
    batch_id = uuid4()
    respx.post(f"{BASE_URL}/v1/memory/batch/{batch_id}/retry").mock(
        return_value=httpx.Response(404)
    )

    with pytest.raises(MemoryBatchNotFoundError):
        await memory_client.retry_batch(batch_id)


@pytest.mark.asyncio
@respx.mock
async def test_ingest_scenario_template_newbie_mode_sends_world_data_as_is() -> None:
    scenario_id = uuid4()
    route = respx.post(f"{BASE_URL}/v1/memory/template/ingest").mock(
        return_value=httpx.Response(200, json={"template_space_id": str(scenario_id)})
    )
    request = MemoryTemplateIngestRequest(
        scenario_id=scenario_id,
        mode="newbie",
        world_data={"lore_text": "Once upon a time."},
    )

    response = await memory_client.ingest_scenario_template(request)

    assert response.template_space_id == scenario_id
    body = json.loads(route.calls[0].request.content)
    assert body["mode"] == "newbie"
    assert body["world_data"] == {"lore_text": "Once upon a time."}


@pytest.mark.asyncio
@respx.mock
async def test_ingest_scenario_template_master_mode_translates_wire_shape() -> None:
    scenario_id = uuid4()
    warden_id = uuid4()
    sigil_id = uuid4()
    fact_id = uuid4()
    superseded_id = uuid4()
    route = respx.post(f"{BASE_URL}/v1/memory/template/ingest").mock(
        return_value=httpx.Response(200, json={"template_space_id": str(scenario_id)})
    )
    request = MemoryTemplateIngestRequest(
        scenario_id=scenario_id,
        mode="master",
        entities=[
            EntityIngestPayload(
                entity_id=warden_id,
                entity_type="character",
                canonical_name="The Warden",
            ),
            EntityIngestPayload(
                entity_id=sigil_id, entity_type="item", canonical_name="Ember Sigil"
            ),
        ],
        facts=[
            FactIngestPayload(
                fact_id=fact_id,
                subject_entity_id=warden_id,
                predicate="vulnerable_to",
                object_entity_id=sigil_id,
                hidden=True,
                superseded_fact_id=superseded_id,
            )
        ],
    )

    await memory_client.ingest_scenario_template(request)

    body = json.loads(route.calls[0].request.content)
    assert body["scenario_id"] == str(scenario_id)
    assert body["mode"] == "master"
    world_data = body["world_data"]
    assert {e["canonical_name"] for e in world_data["entities"]} == {
        "The Warden",
        "Ember Sigil",
    }
    wire_fact = world_data["facts"][0]
    assert wire_fact["subject_canonical_name"] == "The Warden"
    assert wire_fact["object_canonical_name"] == "Ember Sigil"
    assert wire_fact["predicate"] == "vulnerable_to"
    assert wire_fact["hidden"] is True
    assert wire_fact["external_fact_id"] == str(fact_id)
    assert wire_fact["superseded_fact_id"] == str(superseded_id)


@pytest.mark.asyncio
@respx.mock
async def test_ingest_scenario_template_master_mode_omits_superseded_fact_id_when_unset() -> (
    None
):
    scenario_id = uuid4()
    warden_id = uuid4()
    fact_id = uuid4()
    route = respx.post(f"{BASE_URL}/v1/memory/template/ingest").mock(
        return_value=httpx.Response(200, json={"template_space_id": str(scenario_id)})
    )
    request = MemoryTemplateIngestRequest(
        scenario_id=scenario_id,
        mode="master",
        entities=[
            EntityIngestPayload(
                entity_id=warden_id,
                entity_type="character",
                canonical_name="The Warden",
            )
        ],
        facts=[
            FactIngestPayload(
                fact_id=fact_id,
                subject_entity_id=warden_id,
                predicate="is_wary",
                object_literal="always",
            )
        ],
    )

    await memory_client.ingest_scenario_template(request)

    body = json.loads(route.calls[0].request.content)
    wire_fact = body["world_data"]["facts"][0]
    assert wire_fact["superseded_fact_id"] is None
    assert wire_fact["object_canonical_name"] is None
    assert wire_fact["object_literal"] == "always"


@pytest.mark.asyncio
@respx.mock
async def test_clone_template_memory_space_success() -> None:
    scenario_id = uuid4()
    playthrough_id = uuid4()
    respx.post(f"{BASE_URL}/v1/memory/playthrough/{playthrough_id}/init").mock(
        return_value=httpx.Response(
            200, json={"playthrough_space_id": str(playthrough_id)}
        )
    )
    request = MemoryTemplateCloneRequest(
        scenario_id=scenario_id, playthrough_id=playthrough_id
    )

    response = await memory_client.clone_template_memory_space(request)

    assert response.playthrough_space_id == playthrough_id


@pytest.mark.asyncio
@respx.mock
async def test_auth_header_sent_when_api_key_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "memory_service_api_key", "test-key")
    route = respx.post(f"{BASE_URL}/v1/memory/query").mock(
        return_value=httpx.Response(
            200, json={"facts": [], "abstained": True, "resolved_time_point": None}
        )
    )

    await memory_client.query_memory(_query_request())

    assert route.calls[0].request.headers["Authorization"] == "Bearer test-key"


@pytest.mark.asyncio
@respx.mock
async def test_auth_header_absent_when_api_key_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(settings, "memory_service_api_key", "")
    route = respx.post(f"{BASE_URL}/v1/memory/query").mock(
        return_value=httpx.Response(
            200, json={"facts": [], "abstained": True, "resolved_time_point": None}
        )
    )

    await memory_client.query_memory(_query_request())

    assert "Authorization" not in route.calls[0].request.headers
