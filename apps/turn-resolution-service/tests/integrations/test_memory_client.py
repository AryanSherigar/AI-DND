"""Integration tests for Turn Resolution Service memory client."""

from uuid import uuid4

import pytest

from app.integrations import memory_client
from app.models.memory import (
    MemoryIngestRequest,
    MemoryQueryRequest,
    TurnBatchEntry,
)


@pytest.mark.asyncio
async def test_query_memory_success() -> None:
    """Verify query_memory returns facts and accepts game_state payload."""
    memory_client.MOCK_ABSTAIN_RATE = 0.0
    request = MemoryQueryRequest(
        scenario_id=uuid4(),
        playthrough_id=uuid4(),
        participant_id=uuid4(),
        query_text="Where is the silver key?",
        checkpoint="entrance",
        game_state={"inventory": ["map"], "health": 100},
    )

    response = await memory_client.query_memory(request)
    assert response.abstained is False
    assert len(response.facts) == 1
    assert response.facts[0].subject == "mock_entity"
    assert response.facts[0].object == "Where is the silver key?"[:40]


@pytest.mark.asyncio
async def test_query_memory_abstention() -> None:
    """Verify query_memory abstains when MOCK_ABSTAIN_RATE is 1.0."""
    memory_client.MOCK_ABSTAIN_RATE = 1.0
    request = MemoryQueryRequest(
        scenario_id=uuid4(),
        playthrough_id=uuid4(),
        participant_id=uuid4(),
        query_text="Unknown secret",
        checkpoint="entrance",
        game_state={},
    )

    response = await memory_client.query_memory(request)
    assert response.abstained is True
    assert response.facts == []
    memory_client.MOCK_ABSTAIN_RATE = 0.0


@pytest.mark.asyncio
async def test_ingest_batch_and_status() -> None:
    """Verify ingest_batch creates batch status and get_batch_status reads it."""
    memory_client.MOCK_BATCH_FAILURE_RATE = 0.0
    request = MemoryIngestRequest(
        scenario_id=uuid4(),
        playthrough_id=uuid4(),
        turns_batch=[
            TurnBatchEntry(
                turn_number=1,
                text="Player enters cave",
                participant_id=uuid4(),
            )
        ],
    )

    response = await memory_client.ingest_batch(request)
    status = await memory_client.get_batch_status(response.batch_id)
    assert status.status == "succeeded"
    assert status.facts_created == 2
    assert status.error is None


@pytest.mark.asyncio
async def test_ingest_batch_failure_and_retry() -> None:
    """Verify simulated batch failure and subsequent retry flow."""
    memory_client.MOCK_BATCH_FAILURE_RATE = 1.0
    request = MemoryIngestRequest(
        scenario_id=uuid4(),
        playthrough_id=uuid4(),
        turns_batch=[
            TurnBatchEntry(
                turn_number=1,
                text="Player fights goblin",
                participant_id=uuid4(),
            )
        ],
    )

    response = await memory_client.ingest_batch(request)
    status = await memory_client.get_batch_status(response.batch_id)
    assert status.status == "failed"
    assert status.retryable is True

    retry_response = await memory_client.retry_batch(response.batch_id)
    assert retry_response.batch_id == response.batch_id

    updated_status = await memory_client.get_batch_status(response.batch_id)
    assert updated_status.status == "succeeded"
    assert updated_status.retryable is False

    memory_client.MOCK_BATCH_FAILURE_RATE = 0.0
