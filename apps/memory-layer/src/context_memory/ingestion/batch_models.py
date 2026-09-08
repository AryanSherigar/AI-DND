"""Domain types for batched turn ingestion (Milestone 2 of the AI-DND bridge).

AI-DND's `POST /v1/memory/ingest` wants an async submit (`batch_id` handle) +
poll (`GET /v1/memory/batch/{id}/status`) + retry shape. mem1's own
`ingestion_jobs` state machine and `IngestionOrchestrator.run_batch`'s
idempotent replay already do the actual work (see `MemoryEngine.submit_batch`
/`get_batch_status`/`retry_batch`) -- these are just the wire-adjacent request/
response shapes for that, kept out of `core/models.py` (that file's
`ContextBatch`/`ContextRecord` are the stricter, contract-versioned v1
ingestion schema; these are a thinner batch-tracking layer built on top).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from context_memory.core.models import BatchStatus


@dataclass(frozen=True)
class TurnBatchEntry:
    turn_number: int
    text: str
    participant_id: str
    # §4 fix: when the caller has a real event time for this turn, honor it
    # exactly. When absent (every caller today), `MemoryEngine.submit_batch`
    # derives a deterministic synthetic time from `turn_number` alone --
    # never wall-clock-at-submission, which would make the same turn hash to
    # a different `occurred_at` on every catch-up resubmission (§1: the
    # immutable chunk store then sees "same chunk_id, different content" and
    # raises, instead of the idempotent no-op a replay should be).
    occurred_at: datetime | None = None


def dedupe_turn_entries(*groups: Iterable[TurnBatchEntry]) -> list[TurnBatchEntry]:
    """§1 fix: flattens several turn-entry groups (AI-DND's `turns_batch` +
    `recent_context_turns` -- the latter exists precisely so a catch-up
    request can re-send turns an earlier request may already have ingested,
    per ADR-5) into one list, keeping only the first occurrence of each
    turn_number -- an earlier group wins over a later duplicate. Without
    this, the same turn_number appearing in both arrays of one request
    produces two records with the same `record_id` in one `ContextBatch`,
    which `ContextBatch.__post_init__` rejects outright as a duplicate."""
    by_turn: dict[int, TurnBatchEntry] = {}
    for group in groups:
        for entry in group:
            by_turn.setdefault(entry.turn_number, entry)
    return list(by_turn.values())


__all__ = ["BatchStatus", "TurnBatchEntry", "dedupe_turn_entries"]
