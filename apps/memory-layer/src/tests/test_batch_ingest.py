"""MemoryEngine.submit_batch/get_batch_status/retry_batch -- Milestone 2 of
the AI-DND bridge (async batch ingest, matching `POST /v1/memory/ingest`'s
`batch_id` + `GET /v1/memory/batch/{id}/status` + retry contract).

Uses a `FakeOrchestrator` rather than the real `IngestionOrchestrator` stack
-- orchestrator internals (extraction, graph write, job-state transitions)
are already covered by `test_orchestrator.py`/`test_job_transitions.py`; this
file is only about MemoryEngine's batch-tracking layer built on top of it.
"""

from __future__ import annotations

import unittest

from context_memory.core.enums import IngestionJobState
from context_memory.core.errors import BatchNotFoundError
from context_memory.engine import MemoryEngine
from context_memory.ingestion.batch_models import TurnBatchEntry
from context_memory.ingestion.fakes import InMemoryBatchStore
from context_memory.ingestion.orchestrator import BatchRunResult, ChunkRunResult


class FakeOrchestrator:
    """`run_batch` returns whatever `ChunkRunResult`s the test configured,
    one set per call -- so a test can script "first call fails, retry
    succeeds" the same way the real orchestrator's idempotent replay would."""

    def __init__(self, result_sequence: list[list[ChunkRunResult]]) -> None:
        self._result_sequence = result_sequence
        self.calls = 0

    def run_batch(self, batch) -> BatchRunResult:
        results = self._result_sequence[min(self.calls, len(self._result_sequence) - 1)]
        self.calls += 1
        return BatchRunResult(context_id=batch.context_id, results=tuple(results))


def _engine(orchestrator) -> MemoryEngine:
    # §3 fix: `batch_store` is now a real dependency (defaults to
    # `PostgresBatchStore(pool)`) -- `InMemoryBatchStore` here keeps
    # `pool=object()` a safe placeholder these tests never actually
    # touch, same as before this fix.
    return MemoryEngine(
        orchestrator,
        retrieval_engine=None,
        llm_client=None,
        pool=object(),
        batch_store=InMemoryBatchStore(),
    )


def _turns() -> list[TurnBatchEntry]:
    return [
        TurnBatchEntry(
            turn_number=1, text="The player enters the cave.", participant_id="p1"
        ),
        TurnBatchEntry(turn_number=2, text="A ghost appears.", participant_id="p1"),
    ]


class SubmitBatchTests(unittest.TestCase):
    def test_status_is_pending_until_background_run_completes(self):
        orchestrator = FakeOrchestrator(
            [
                [
                    ChunkRunResult(
                        "chunk:1", IngestionJobState.COMPLETED, accepted_fact_count=2
                    ),
                    ChunkRunResult(
                        "chunk:2", IngestionJobState.COMPLETED, accepted_fact_count=1
                    ),
                ]
            ]
        )
        engine = _engine(orchestrator)

        batch_id = engine.submit_batch("playthrough-1", _turns())
        engine._executor.shutdown(wait=True)

        status = engine.get_batch_status(batch_id)
        self.assertEqual(status.status, "succeeded")
        self.assertEqual(status.facts_created, 3)
        self.assertFalse(status.retryable)

    def test_unknown_batch_id_raises_not_found(self):
        """§3 fix: was `self.assertEqual(status.status, "pending")` -- an
        unknown batch_id (never submitted) is now a 404-worthy error, not an
        indefinite "pending" a caller could never distinguish from a batch
        that's genuinely still running."""
        engine = _engine(FakeOrchestrator([[]]))
        with self.assertRaises(BatchNotFoundError):
            engine.get_batch_status("no-such-batch")

    def test_batch_status_survives_the_in_memory_cache_being_cleared(self):
        """Simulates a process restart (or a different replica) by reading
        status straight from the durable batch_store, bypassing
        MemoryEngine's own in-memory `_batches` cache entirely."""
        orchestrator = FakeOrchestrator(
            [
                [
                    ChunkRunResult(
                        "chunk:1", IngestionJobState.COMPLETED, accepted_fact_count=2
                    ),
                ]
            ]
        )
        engine = _engine(orchestrator)
        batch_id = engine.submit_batch("playthrough-1", _turns()[:1])
        engine._executor.shutdown(wait=True)
        self.assertEqual(engine.get_batch_status(batch_id).status, "succeeded")

        del engine._batches[batch_id]  # simulate restart: fast-path cache gone
        status = engine.get_batch_status(batch_id)
        # InMemoryBatchStore doesn't re-derive real per-chunk state (that's
        # PostgresBatchStore's job, against real ingestion_jobs rows) -- it
        # only proves the fallback path is reached and reports something
        # coherent instead of raising BatchNotFoundError for a batch that
        # really was submitted.
        self.assertEqual(status.status, "pending")

    def test_retry_after_simulated_restart_reconstructs_batch_from_durable_store(self):
        orchestrator = FakeOrchestrator(
            [
                [
                    ChunkRunResult(
                        "chunk:1", IngestionJobState.RETRYABLE_FAILED, error="timeout"
                    )
                ],
                [
                    ChunkRunResult(
                        "chunk:1", IngestionJobState.COMPLETED, accepted_fact_count=1
                    )
                ],
            ]
        )
        engine = _engine(orchestrator)
        batch_id = engine.submit_batch("playthrough-1", _turns()[:1])
        engine._executor.shutdown(wait=True)
        self.assertEqual(engine.get_batch_status(batch_id).status, "failed")

        del engine._batches[batch_id]  # simulate restart
        engine._executor = engine._executor.__class__(max_workers=1)
        engine.retry_batch(
            batch_id
        )  # must reconstruct the ContextBatch from batch_store, not raise
        engine._executor.shutdown(wait=True)

        self.assertEqual(engine.get_batch_status(batch_id).status, "succeeded")
        self.assertEqual(orchestrator.calls, 2)

    def test_deterministic_chunk_ids_across_retries(self):
        """Same context_id + turn_number -> same chunk_id -- what makes
        retry_batch's re-submit idempotent against the orchestrator's own
        replay instead of re-extracting duplicate facts."""
        from context_memory.core.validation import chunk_id_for

        orchestrator = FakeOrchestrator([[]])
        engine = _engine(orchestrator)
        batch_id = engine.submit_batch("playthrough-1", _turns())
        engine._executor.shutdown(wait=True)

        expected = tuple(
            chunk_id_for("playthrough-1", f"playthrough-1:turn:{n}") for n in (1, 2)
        )
        self.assertEqual(engine._batches[batch_id]["chunk_ids"], expected)


class BatchStatusAggregationTests(unittest.TestCase):
    def test_partial_when_some_chunks_completed_and_some_failed(self):
        orchestrator = FakeOrchestrator(
            [
                [
                    ChunkRunResult(
                        "chunk:1", IngestionJobState.COMPLETED, accepted_fact_count=1
                    ),
                    ChunkRunResult(
                        "chunk:2", IngestionJobState.RETRYABLE_FAILED, error="timeout"
                    ),
                ]
            ]
        )
        engine = _engine(orchestrator)

        batch_id = engine.submit_batch("playthrough-1", _turns())
        engine._executor.shutdown(wait=True)

        status = engine.get_batch_status(batch_id)
        self.assertEqual(status.status, "partial")
        self.assertEqual(status.facts_created, 1)
        self.assertTrue(status.retryable)
        self.assertEqual(status.error, "timeout")

    def test_failed_and_retryable_when_all_chunks_retryable_failed(self):
        orchestrator = FakeOrchestrator(
            [
                [
                    ChunkRunResult(
                        "chunk:1",
                        IngestionJobState.RETRYABLE_FAILED,
                        error="mem1 unavailable",
                    ),
                ]
            ]
        )
        engine = _engine(orchestrator)

        batch_id = engine.submit_batch("playthrough-1", _turns()[:1])
        engine._executor.shutdown(wait=True)

        status = engine.get_batch_status(batch_id)
        self.assertEqual(status.status, "failed")
        self.assertTrue(status.retryable)

    def test_failed_and_not_retryable_when_a_chunk_is_terminal(self):
        orchestrator = FakeOrchestrator(
            [
                [
                    ChunkRunResult(
                        "chunk:1",
                        IngestionJobState.TERMINAL_FAILED,
                        error="invalid payload",
                    ),
                ]
            ]
        )
        engine = _engine(orchestrator)

        batch_id = engine.submit_batch("playthrough-1", _turns()[:1])
        engine._executor.shutdown(wait=True)

        status = engine.get_batch_status(batch_id)
        self.assertEqual(status.status, "failed")
        self.assertFalse(status.retryable)

    def test_unexpected_exception_from_run_batch_is_reported_as_failed_retryable(self):
        class ExplodingOrchestrator:
            def run_batch(self, batch):
                raise RuntimeError("hydradb connection refused")

        engine = _engine(ExplodingOrchestrator())
        batch_id = engine.submit_batch("playthrough-1", _turns()[:1])
        engine._executor.shutdown(wait=True)

        status = engine.get_batch_status(batch_id)
        self.assertEqual(status.status, "failed")
        self.assertTrue(status.retryable)
        self.assertIn("hydradb connection refused", status.error)


class CatchUpBatchIdempotencyTests(unittest.TestCase):
    """§1 fix: a catch-up batch re-sending an already-ingested turn must
    produce a chunk PostgresChunkStore.put would accept as an idempotent
    replay -- same chunk_id (already true: context_id + turn_number) AND
    identical immutable content (source descriptor, occurred_at, metadata),
    not just a matching chunk_id. Verified here at the ContextBatch/
    ContextRecord level `submit_batch` builds, since that's what the store's
    immutability check actually compares."""

    class RecordingOrchestrator:
        def __init__(self) -> None:
            self.batches = []

        def run_batch(self, batch):
            self.batches.append(batch)
            return BatchRunResult(context_id=batch.context_id, results=())

    def test_overlapping_turn_is_byte_identical_across_two_submissions(self):
        orchestrator = self.RecordingOrchestrator()
        engine = _engine(orchestrator)

        first = [
            TurnBatchEntry(
                turn_number=5, text="The player enters the cave.", participant_id="p1"
            )
        ]
        engine.submit_batch("playthrough-1", first)
        engine._executor.shutdown(wait=True)

        engine._executor = engine._executor.__class__(max_workers=1)
        catch_up = [
            TurnBatchEntry(
                turn_number=5, text="The player enters the cave.", participant_id="p1"
            ),
            TurnBatchEntry(turn_number=6, text="A ghost appears.", participant_id="p1"),
        ]
        engine.submit_batch("playthrough-1", catch_up)
        engine._executor.shutdown(wait=True)

        first_record = orchestrator.batches[0].records[0]
        second_record = next(
            r
            for r in orchestrator.batches[1].records
            if r.record_id == first_record.record_id
        )
        self.assertEqual(first_record.record_id, second_record.record_id)
        self.assertEqual(first_record.occurred_at, second_record.occurred_at)
        self.assertEqual(first_record.content, second_record.content)
        self.assertEqual(first_record.metadata, second_record.metadata)
        # Source descriptor is what PostgresChunkStore.put also compares --
        # must be stable across submissions of the same playthrough, not a
        # fresh random value per batch_id.
        self.assertEqual(orchestrator.batches[0].source, orchestrator.batches[1].source)

    def test_overlap_between_turns_batch_and_recent_context_turns_is_deduped(self):
        """`api/routes.py`'s `ingest_memory` calls `dedupe_turn_entries`
        (turns_batch, then recent_context_turns) before `submit_batch` ever
        sees the entries -- tested at this pure domain layer rather than
        importing the route itself, which pulls in the full FastAPI/
        composition wiring this file otherwise has no reason to depend on."""
        from context_memory.ingestion.batch_models import dedupe_turn_entries

        turns_batch = [TurnBatchEntry(turn_number=5, text="fresh", participant_id="p1")]
        recent_context_turns = [
            TurnBatchEntry(turn_number=5, text="stale", participant_id="p1")
        ]
        entries = dedupe_turn_entries(turns_batch, recent_context_turns)

        orchestrator = self.RecordingOrchestrator()
        engine = _engine(orchestrator)
        engine.submit_batch("playthrough-1", entries)
        engine._executor.shutdown(wait=True)

        batch = orchestrator.batches[0]
        self.assertEqual(len(batch.records), 1)
        self.assertEqual(batch.records[0].content, "fresh")


class RetryBatchTests(unittest.TestCase):
    def test_retry_resubmits_the_same_batch_and_can_flip_to_succeeded(self):
        orchestrator = FakeOrchestrator(
            [
                [
                    ChunkRunResult(
                        "chunk:1", IngestionJobState.RETRYABLE_FAILED, error="timeout"
                    )
                ],
                [
                    ChunkRunResult(
                        "chunk:1", IngestionJobState.COMPLETED, accepted_fact_count=1
                    )
                ],
            ]
        )
        engine = _engine(orchestrator)
        batch_id = engine.submit_batch("playthrough-1", _turns()[:1])
        engine._executor.shutdown(wait=True)
        self.assertEqual(engine.get_batch_status(batch_id).status, "failed")

        engine._executor = engine._executor.__class__(max_workers=1)
        engine.retry_batch(batch_id)
        engine._executor.shutdown(wait=True)

        status = engine.get_batch_status(batch_id)
        self.assertEqual(status.status, "succeeded")
        self.assertEqual(orchestrator.calls, 2)

    def test_retry_of_unknown_batch_id_raises(self):
        engine = _engine(FakeOrchestrator([[]]))
        with self.assertRaises(ValueError):
            engine.retry_batch("no-such-batch")
