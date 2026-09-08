"""Safety net so service-layer tests never make a real memory-layer HTTP call.

Autouse: any test in this directory that exercises PublishService.run_publish_job
or PlaythroughService.create_playthrough (both real memory_client callers) gets
an always-succeeding stand-in unless it installs its own monkeypatch on top
(which simply overrides this fixture for that one test, restored at teardown
either way -- see test_playthrough_service.py's memory-clone-failure test and
test_publish_service.py's call-through spies).
"""

import pytest

from app.integrations import memory_client
from app.models.memory import (
    MemoryTemplateCloneRequest,
    MemoryTemplateCloneResponse,
    MemoryTemplateIngestRequest,
    MemoryTemplateIngestResponse,
)


@pytest.fixture(autouse=True)
def _stub_memory_client(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _fake_ingest_scenario_template(
        request: MemoryTemplateIngestRequest,
    ) -> MemoryTemplateIngestResponse:
        return MemoryTemplateIngestResponse(template_space_id=request.scenario_id)

    async def _fake_clone_template_memory_space(
        request: MemoryTemplateCloneRequest,
        canonical_names: dict[uuid.UUID, str] | None = None,
    ) -> MemoryTemplateCloneResponse:
        return MemoryTemplateCloneResponse(playthrough_space_id=request.playthrough_id)

    monkeypatch.setattr(
        memory_client, "ingest_scenario_template", _fake_ingest_scenario_template
    )
    monkeypatch.setattr(
        memory_client, "clone_template_memory_space", _fake_clone_template_memory_space
    )
