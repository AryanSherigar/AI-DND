"""Autouse memory-layer stub for pipeline-level tests under tests/turn/.

These tests run the real turn pipeline against a real test Postgres, but
don't care about memory-layer behavior specifically. Without this fixture,
they would now hit the real (network) memory_client and fail/hang in any
environment without a running memory-layer instance. Tests that want to
assert something about memory-layer interaction (e.g. tests/turn/steps/
test_context_retrieval.py, test_memory_writer.py) already monkeypatch these
functions explicitly in-test, which simply overrides this fixture's stand-in
for the duration of that test.
"""

from uuid import uuid4

import pytest

from app.integrations import memory_client
from app.models.memory import (
    BatchStatus,
    MemoryIngestResponse,
    MemoryQueryResponse,
)


@pytest.fixture(autouse=True)
def _stub_memory_client(monkeypatch):
    async def fake_query_memory(request):
        return MemoryQueryResponse(facts=[], abstained=False, resolved_time_point=None)

    async def fake_ingest_batch(request):
        return MemoryIngestResponse(batch_id=uuid4())

    async def fake_get_batch_status(batch_id):
        return BatchStatus(
            batch_id=batch_id, status="succeeded", facts_created=0, retryable=False
        )

    async def fake_retry_batch(batch_id):
        return MemoryIngestResponse(batch_id=batch_id)

    monkeypatch.setattr(memory_client, "query_memory", fake_query_memory)
    monkeypatch.setattr(memory_client, "ingest_batch", fake_ingest_batch)
    monkeypatch.setattr(memory_client, "get_batch_status", fake_get_batch_status)
    monkeypatch.setattr(memory_client, "retry_batch", fake_retry_batch)
