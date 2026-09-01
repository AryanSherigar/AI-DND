"""Integration tests for Core API memory client."""

from uuid import uuid4

import pytest

from app.integrations import memory_client
from app.models.memory import (
    MemoryQueryRequest,
    MemoryTemplateCloneRequest,
    MemoryTemplateIngestRequest,
)


@pytest.mark.asyncio
async def test_query_memory_success() -> None:
    """Verify query_memory returns facts and accepts game_state payload."""
    memory_client.MOCK_ABSTAIN_RATE = 0.0
    request = MemoryQueryRequest(
        scenario_id=uuid4(),
        playthrough_id=uuid4(),
        participant_id=uuid4(),
        query_text="Who is the village elder?",
        checkpoint="start",
        game_state={"reputation": 10},
    )

    response = await memory_client.query_memory(request)
    assert response.abstained is False
    assert len(response.facts) == 1


@pytest.mark.asyncio
async def test_ingest_scenario_template() -> None:
    """Verify authoring-time scenario template memory ingestion."""
    scenario_id = uuid4()
    request = MemoryTemplateIngestRequest(
        scenario_id=scenario_id,
        mode="master",
        world_data={"entities": [{"name": "Elder"}]},
    )

    response = await memory_client.ingest_scenario_template(request)
    assert response.template_space_id is not None


@pytest.mark.asyncio
async def test_clone_template_memory_space() -> None:
    """Verify memory template cloning for a new playthrough."""
    scenario_id = uuid4()
    playthrough_id = uuid4()
    request = MemoryTemplateCloneRequest(
        scenario_id=scenario_id,
        playthrough_id=playthrough_id,
    )

    response = await memory_client.clone_template_memory_space(request)
    assert response.playthrough_space_id is not None
