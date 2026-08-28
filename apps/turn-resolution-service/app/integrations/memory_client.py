"""Memory layer client for Turn Resolution Service.

MOCK IMPLEMENTATION — Phase 0-3. Honors the real API contract exactly
(see app/models/memory.py) so it can be swapped for the real client in
Phase 4 with zero changes to any caller (context_retrieval.py,
memory_writer.py). Do not add mock-only fields or behavior that the real
service won't have — that defeats the point of the mock.

Contract reference: POST /v1/memory/query includes `game_state` (ADR-9),
used by the real service to evaluate `when_active` expressions on pre-authored
facts. This mock ignores game_state's contents (it has no facts to filter),
but accepts and forwards it correctly so callers and tests exercise the real
request shape.
"""

from __future__ import annotations

import random
from uuid import UUID, uuid4

from app.models.memory import (
    BatchStatus,
    Fact,
    MemoryIngestRequest,
    MemoryIngestResponse,
    MemoryQueryRequest,
    MemoryQueryResponse,
)

_MOCK_BATCH_STATUSES: dict[UUID, BatchStatus] = {}

MOCK_ABSTAIN_RATE = 0.0
MOCK_BATCH_FAILURE_RATE = 0.0


async def query_memory(request: MemoryQueryRequest) -> MemoryQueryResponse:
    """Mock retrieval. Returns plausible fake facts or an abstention."""
    if random.random() < MOCK_ABSTAIN_RATE:
        return MemoryQueryResponse(facts=[], abstained=True, resolved_time_point=None)

    fake_facts = [
        Fact(
            fact_id=uuid4(),
            subject="mock_entity",
            predicate="is_relevant_to",
            object=request.query_text[:40],
            valid_from=f"turn_{max(request.as_of_turn or 1, 1)}",
            valid_until=None,
            confidence=0.82,
        )
    ]
    return MemoryQueryResponse(
        facts=fake_facts,
        abstained=False,
        resolved_time_point=str(request.as_of_turn) if request.as_of_turn else None,
    )


async def ingest_batch(request: MemoryIngestRequest) -> MemoryIngestResponse:
    """Mock batched extraction submission."""
    batch_id = uuid4()
    failed = random.random() < MOCK_BATCH_FAILURE_RATE
    _MOCK_BATCH_STATUSES[batch_id] = BatchStatus(
        batch_id=batch_id,
        status="failed" if failed else "succeeded",
        facts_created=0 if failed else len(request.turns_batch) * 2,
        error="mock simulated failure" if failed else None,
        retryable=failed,
    )
    return MemoryIngestResponse(batch_id=batch_id)


async def get_batch_status(batch_id: UUID) -> BatchStatus:
    """Mock batch status check."""
    if batch_id not in _MOCK_BATCH_STATUSES:
        return BatchStatus(
            batch_id=batch_id, status="pending", facts_created=0, retryable=False
        )
    return _MOCK_BATCH_STATUSES[batch_id]


async def retry_batch(batch_id: UUID) -> MemoryIngestResponse:
    """Mock batch retry. Marks the batch succeeded on retry."""
    if batch_id in _MOCK_BATCH_STATUSES:
        old = _MOCK_BATCH_STATUSES[batch_id]
        _MOCK_BATCH_STATUSES[batch_id] = BatchStatus(
            batch_id=batch_id,
            status="succeeded",
            facts_created=max(old.facts_created, 2),
            error=None,
            retryable=False,
        )
    return MemoryIngestResponse(batch_id=batch_id)
