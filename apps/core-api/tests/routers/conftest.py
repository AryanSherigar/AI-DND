"""Safety net so router-layer tests never make a real memory-layer HTTP call.

See tests/services/conftest.py for the full rationale -- same stub, scoped to
the routers test directory (e.g. tests/routers/test_playthrough_router.py,
test_share_router.py) which exercise playthrough creation through the real
HTTP router layer.
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
    ) -> MemoryTemplateCloneResponse:
        return MemoryTemplateCloneResponse(playthrough_space_id=request.playthrough_id)

    monkeypatch.setattr(
        memory_client, "ingest_scenario_template", _fake_ingest_scenario_template
    )
    monkeypatch.setattr(
        memory_client, "clone_template_memory_space", _fake_clone_template_memory_space
    )
