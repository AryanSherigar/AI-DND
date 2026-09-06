"""Autouse memory-layer stub for router-level integration tests.

Mirrors tests/turn/conftest.py's rationale: these tests exercise the full
turn HTTP endpoint against a real test Postgres, but don't care about
memory-layer behavior specifically, so a network call to the real memory
layer must not be a precondition for them to pass.
"""

from uuid import uuid4

import pytest

from app.integrations import memory_client
from app.models.memory import MemoryIngestResponse, MemoryQueryResponse


@pytest.fixture(autouse=True)
def _stub_memory_client(monkeypatch):
    async def fake_query_memory(request):
        return MemoryQueryResponse(facts=[], abstained=False, resolved_time_point=None)

    async def fake_ingest_batch(request):
        return MemoryIngestResponse(batch_id=uuid4())

    monkeypatch.setattr(memory_client, "query_memory", fake_query_memory)
    monkeypatch.setattr(memory_client, "ingest_batch", fake_ingest_batch)
