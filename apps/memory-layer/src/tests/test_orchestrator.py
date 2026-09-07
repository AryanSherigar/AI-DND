from __future__ import annotations

import unittest
from datetime import datetime, timezone

from context_memory.core.enums import IngestionJobState
from context_memory.core.models import (
    ContextBatch,
    ContextRecord,
    EntityCandidate,
    ExtractionDraft,
    SourceDescriptor,
)
from context_memory.core.validation import chunk_from_record
from context_memory.ingestion.entity_registry import EntityRegistry
from context_memory.ingestion.extraction import (
    ExtractionService,
    InMemoryExtractionStore,
)
from context_memory.ingestion.fakes import (
    DeterministicEmbedder,
    DeterministicExtractor,
    InMemoryChunkStore,
    InMemoryEmbeddingStore,
    InMemoryGraphIdAllocator,
    InMemoryGraphManifestStore,
    InMemoryJobStore,
    InMemorySearchIndexStore,
    RecordingGraphTransport,
)
from context_memory.ingestion.graph_plan_builder import GraphPlanBuilder
from context_memory.ingestion.graph_writer import GraphWriter
from context_memory.ingestion.orchestrator import IngestionOrchestrator


class _FailNTimesTransport:
    """Fails its first `fail_count` writes, then behaves like RecordingGraphTransport."""

    def __init__(self, fail_count: int) -> None:
        self._remaining_failures = fail_count
        self._inner = RecordingGraphTransport()

    def write(self, cypher, rows, idempotency_key):
        if self._remaining_failures > 0:
            self._remaining_failures -= 1
            raise ConnectionError("simulated transient graph-node network failure")
        return self._inner.write(cypher, rows, idempotency_key)

    def read(self, cypher, parameters, bookmark):
        return self._inner.read(cypher, parameters, bookmark)


class OrchestratorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.chunk_store = InMemoryChunkStore()
        self.job_store = InMemoryJobStore()
        self.allocator = InMemoryGraphIdAllocator()
        self.manifest_store = InMemoryGraphManifestStore()
        self.embedding_store = InMemoryEmbeddingStore()
        self.search_index_store = InMemorySearchIndexStore()
        self.entity_registry = EntityRegistry(self.allocator)

    def batch_and_record(
        self, content: str = "Max the dog likes walks", session_id: str = "session-001"
    ):
        record = ContextRecord(
            record_id="record-001",
            session_id=session_id,
            occurred_at=datetime(2026, 1, 10, 9, tzinfo=timezone.utc),
            content=content,
        )
        batch = ContextBatch(
            "ingestion-001",
            "context-001",
            SourceDescriptor("fixture", "fixture-001"),
            (record,),
        )
        return batch, record

    def orchestrator(self, transport) -> IngestionOrchestrator:
        extractor = DeterministicExtractor(
            {
                "record-001": (
                    ExtractionDraft(
                        "fact-001",
                        "Max likes walks",
                        0,
                        3,
                        0.9,
                        entities=(EntityCandidate("Max", "pet"),),
                    ),
                )
            }
        )
        extraction_service = ExtractionService(extractor, InMemoryExtractionStore())
        graph_writer = GraphWriter(self.manifest_store, transport)
        plan_builder = GraphPlanBuilder(self.allocator)

        def resolve_entity(context_id: str, surface: str, entity_type: str):
            return self.entity_registry.resolve(
                context_id=context_id, surface=surface, entity_type=entity_type
            ).entity

        return IngestionOrchestrator(
            chunk_store=self.chunk_store,
            job_store=self.job_store,
            extraction_service=extraction_service,
            graph_plan_builder=plan_builder,
            graph_writer=graph_writer,
            resolve_entity=resolve_entity,
            embedder=DeterministicEmbedder(),
            embedding_store=self.embedding_store,
            search_index_store=self.search_index_store,
        )

    def test_happy_path_reaches_completed(self) -> None:
        batch, record = self.batch_and_record()
        orchestrator = self.orchestrator(RecordingGraphTransport())
        result = orchestrator.run_record(batch, record)
        self.assertEqual(result.state, IngestionJobState.COMPLETED)
        self.assertEqual(result.accepted_fact_count, 1)
        job = self.job_store.get(result.chunk_id)
        self.assertEqual(job.state, IngestionJobState.COMPLETED)
        # Verify search index was populated
        self.assertIn("fact-001", self.search_index_store._rows)
        self.assertEqual(self.search_index_store._rows["fact-001"], "Max likes walks")

    def test_happy_path_writes_graph_and_embedding(self) -> None:
        batch, record = self.batch_and_record()
        transport = RecordingGraphTransport()
        orchestrator = self.orchestrator(transport)
        orchestrator.run_record(batch, record)
        self.assertTrue(any("Session" in cypher for cypher, _, _ in transport.writes))
        self.assertTrue(any("Turn" in cypher for cypher, _, _ in transport.writes))
        self.assertTrue(any("Fact" in cypher for cypher, _, _ in transport.writes))
        self.assertTrue(any("Entity" in cypher for cypher, _, _ in transport.writes))
        self.assertEqual(len(self.embedding_store._rows), 1)

    def test_no_entities_no_facts_still_completes(self) -> None:
        record = ContextRecord(
            record_id="record-001",
            session_id="session-001",
            occurred_at=datetime(2026, 1, 10, 9, tzinfo=timezone.utc),
            content="unrelated text",
        )
        batch = ContextBatch(
            "ingestion-001",
            "context-001",
            SourceDescriptor("fixture", "fixture-001"),
            (record,),
        )
        extractor = DeterministicExtractor({"record-001": ()})  # nothing extracted
        extraction_service = ExtractionService(extractor, InMemoryExtractionStore())
        transport = RecordingGraphTransport()
        orchestrator = IngestionOrchestrator(
            chunk_store=self.chunk_store,
            job_store=self.job_store,
            extraction_service=extraction_service,
            graph_plan_builder=GraphPlanBuilder(self.allocator),
            graph_writer=GraphWriter(self.manifest_store, transport),
            resolve_entity=lambda *a: None,
            embedder=DeterministicEmbedder(),
            embedding_store=self.embedding_store,
            search_index_store=self.search_index_store,
        )
        result = orchestrator.run_record(batch, record)
        self.assertEqual(result.state, IngestionJobState.COMPLETED)
        self.assertEqual(result.accepted_fact_count, 0)
        # Session + Turn still written even with zero facts.
        self.assertTrue(any("Session" in cypher for cypher, _, _ in transport.writes))

    def test_transient_failure_is_retryable_and_retry_succeeds(self) -> None:
        batch, record = self.batch_and_record()
        transport = _FailNTimesTransport(fail_count=1)
        orchestrator = self.orchestrator(transport)
        first = orchestrator.run_record(batch, record)
        self.assertEqual(first.state, IngestionJobState.RETRYABLE_FAILED)
        self.assertIsNotNone(first.error)

        chunk = self.chunk_store.get(batch.context_id, first.chunk_id)
        job = self.job_store.get(first.chunk_id)
        retry = orchestrator.run_chunk(batch, record, chunk, job.state)
        self.assertEqual(retry.state, IngestionJobState.COMPLETED)

    def test_completed_job_is_not_reprocessed(self) -> None:
        batch, record = self.batch_and_record()
        orchestrator = self.orchestrator(RecordingGraphTransport())
        first = orchestrator.run_record(batch, record)
        chunk = self.chunk_store.get(batch.context_id, first.chunk_id)
        job = self.job_store.get(first.chunk_id)
        self.assertEqual(job.state, IngestionJobState.COMPLETED)
        result_again = orchestrator.run_chunk(batch, record, chunk, job.state)
        self.assertEqual(result_again.state, IngestionJobState.COMPLETED)
        self.assertEqual(
            result_again.accepted_fact_count, 0
        )  # short-circuited, extraction never re-ran

    def test_extraction_provider_failure_is_retryable_not_a_silent_completion(
        self,
    ) -> None:
        """§2 fix: an extractor call that itself fails (provider timeout,
        malformed response) must land the chunk in RETRYABLE_FAILED, not
        COMPLETED with accepted_fact_count=0 -- which used to be
        indistinguishable from a message that genuinely had no facts."""
        from context_memory.core.errors import ExtractionProviderError

        class _FlakyExtractor:
            extractor_name = "llm-extractor"
            extractor_version = "v1"

            def extract(self, record):
                raise ExtractionProviderError("simulated provider timeout")

        batch, record = self.batch_and_record()
        extraction_service = ExtractionService(
            _FlakyExtractor(), InMemoryExtractionStore()
        )
        transport = RecordingGraphTransport()
        orchestrator = IngestionOrchestrator(
            chunk_store=self.chunk_store,
            job_store=self.job_store,
            extraction_service=extraction_service,
            graph_plan_builder=GraphPlanBuilder(self.allocator),
            graph_writer=GraphWriter(self.manifest_store, transport),
            resolve_entity=lambda *a: None,
            embedder=DeterministicEmbedder(),
            embedding_store=self.embedding_store,
            search_index_store=self.search_index_store,
        )
        result = orchestrator.run_record(batch, record)
        self.assertEqual(result.state, IngestionJobState.RETRYABLE_FAILED)
        self.assertIn("simulated provider timeout", result.error)
        # Never wrote anything -- the whole chunk is genuinely retryable, not
        # a partial write masquerading as a completed, fact-free chunk.
        self.assertEqual(transport.writes, [])

    def test_verification_fails_the_chunk_when_embedding_row_is_missing(self) -> None:
        """§8 fix: `InMemoryEmbeddingStore.contains()` -- a real independent
        check, not just "no write call raised" -- catches a store that
        silently dropped the row."""

        class DroppingEmbeddingStore(InMemoryEmbeddingStore):
            def put(self, embedding):
                return embedding  # accepted the call, never actually stored it

        batch, record = self.batch_and_record()
        extractor = DeterministicExtractor(
            {
                "record-001": (
                    ExtractionDraft(
                        "fact-001",
                        "Max likes walks",
                        0,
                        3,
                        0.9,
                        entities=(EntityCandidate("Max", "pet"),),
                    ),
                )
            }
        )
        extraction_service = ExtractionService(extractor, InMemoryExtractionStore())
        transport = RecordingGraphTransport()
        orchestrator = IngestionOrchestrator(
            chunk_store=self.chunk_store,
            job_store=self.job_store,
            extraction_service=extraction_service,
            graph_plan_builder=GraphPlanBuilder(self.allocator),
            graph_writer=GraphWriter(self.manifest_store, transport),
            resolve_entity=lambda cid, surface, etype: (
                self.entity_registry.resolve(
                    context_id=cid, surface=surface, entity_type=etype
                ).entity
            ),
            embedder=DeterministicEmbedder(),
            embedding_store=DroppingEmbeddingStore(),
            search_index_store=self.search_index_store,
        )
        result = orchestrator.run_record(batch, record)
        self.assertEqual(result.state, IngestionJobState.RETRYABLE_FAILED)
        self.assertIn("embedding verification failed", result.error)

    def test_verification_fails_the_chunk_when_search_index_row_is_missing(
        self,
    ) -> None:
        class DroppingSearchIndexStore(InMemorySearchIndexStore):
            def put(self, context_id, fact_id, raw_text):
                pass  # accepted the call, never actually stored it

        batch, record = self.batch_and_record()
        extractor = DeterministicExtractor(
            {
                "record-001": (
                    ExtractionDraft(
                        "fact-001",
                        "Max likes walks",
                        0,
                        3,
                        0.9,
                        entities=(EntityCandidate("Max", "pet"),),
                    ),
                )
            }
        )
        extraction_service = ExtractionService(extractor, InMemoryExtractionStore())
        transport = RecordingGraphTransport()
        orchestrator = IngestionOrchestrator(
            chunk_store=self.chunk_store,
            job_store=self.job_store,
            extraction_service=extraction_service,
            graph_plan_builder=GraphPlanBuilder(self.allocator),
            graph_writer=GraphWriter(self.manifest_store, transport),
            resolve_entity=lambda cid, surface, etype: (
                self.entity_registry.resolve(
                    context_id=cid, surface=surface, entity_type=etype
                ).entity
            ),
            embedder=DeterministicEmbedder(),
            embedding_store=self.embedding_store,
            search_index_store=DroppingSearchIndexStore(),
        )
        result = orchestrator.run_record(batch, record)
        self.assertEqual(result.state, IngestionJobState.RETRYABLE_FAILED)
        self.assertIn("search index verification failed", result.error)

    def test_safe_transition_logs_loudly_instead_of_swallowing_silently(self) -> None:
        """§8 fix: was a bare `except Exception: pass`."""

        class UnrecordableJobStore(InMemoryJobStore):
            def transition(self, chunk_id, new_state, *, error=None):
                raise RuntimeError("job row locked by another process")

        batch, record = self.batch_and_record()
        orchestrator = self.orchestrator(RecordingGraphTransport())
        orchestrator._job_store = UnrecordableJobStore()
        with self.assertLogs(
            "context_memory.ingestion.orchestrator", level="ERROR"
        ) as logs:
            orchestrator._safe_transition(
                "chunk-x", IngestionJobState.RETRYABLE_FAILED, "original failure"
            )
        self.assertTrue(
            any("RECONCILIATION REQUIRED" in message for message in logs.output)
        )

    def test_terminal_failed_blocks_auto_retry(self) -> None:
        batch, record = self.batch_and_record()
        orchestrator = self.orchestrator(RecordingGraphTransport())
        chunk = self.chunk_store.put(chunk_from_record(batch, record))
        self.job_store.seed(chunk.chunk_id, chunk.context_id)
        self.job_store.transition(
            chunk.chunk_id, IngestionJobState.RETRYABLE_FAILED, error="forced"
        )
        self.job_store.transition(
            chunk.chunk_id, IngestionJobState.TERMINAL_FAILED, error="forced terminal"
        )
        job = self.job_store.get(chunk.chunk_id)
        result = orchestrator.run_chunk(batch, record, chunk, job.state)
        self.assertEqual(result.state, IngestionJobState.TERMINAL_FAILED)
        self.assertIn("blocked", result.error)


class GroupedRunBatchTests(unittest.TestCase):
    """`run_batch`'s batched-write path (Config.ingestion_write_batch_size /
    IngestionOrchestrator's `write_batch_size`) -- see
    docs/fixes_and_evaluation_findings.md §3.9. `run_chunk`/`run_record`
    (exercised above) are untouched by this; these tests are specifically
    for `_run_group`'s cross-chunk batching."""

    def setUp(self) -> None:
        self.chunk_store = InMemoryChunkStore()
        self.job_store = InMemoryJobStore()
        self.allocator = InMemoryGraphIdAllocator()
        self.manifest_store = InMemoryGraphManifestStore()
        self.embedding_store = InMemoryEmbeddingStore()
        self.search_index_store = InMemorySearchIndexStore()
        self.entity_registry = EntityRegistry(self.allocator)

    def make_batch(
        self, n: int, session_id: str = "session-001"
    ) -> tuple[ContextBatch, list[ContextRecord]]:
        records = [
            ContextRecord(
                record_id=f"record-{i:03d}",
                session_id=session_id,
                occurred_at=datetime(2026, 1, 10, 9, i, tzinfo=timezone.utc),
                content=f"Fact number {i} about the user",
            )
            for i in range(n)
        ]
        batch = ContextBatch(
            "ingestion-001",
            "context-001",
            SourceDescriptor("fixture", "fixture-001"),
            tuple(records),
        )
        return batch, records

    def orchestrator(
        self, transport, write_batch_size: int, candidates_by_record: dict | None = None
    ) -> IngestionOrchestrator:
        candidates_by_record = candidates_by_record or {}
        extractor = DeterministicExtractor(candidates_by_record)
        extraction_service = ExtractionService(extractor, InMemoryExtractionStore())
        graph_writer = GraphWriter(self.manifest_store, transport)
        plan_builder = GraphPlanBuilder(self.allocator)

        def resolve_entity(context_id: str, surface: str, entity_type: str):
            return self.entity_registry.resolve(
                context_id=context_id, surface=surface, entity_type=entity_type
            ).entity

        return IngestionOrchestrator(
            chunk_store=self.chunk_store,
            job_store=self.job_store,
            extraction_service=extraction_service,
            graph_plan_builder=plan_builder,
            graph_writer=graph_writer,
            resolve_entity=resolve_entity,
            embedder=DeterministicEmbedder(),
            embedding_store=self.embedding_store,
            search_index_store=self.search_index_store,
            write_batch_size=write_batch_size,
        )

    def candidates_for(self, records: list[ContextRecord]) -> dict:
        return {
            record.record_id: (
                ExtractionDraft(
                    f"fact-{record.record_id}",
                    f"Fact text for {record.record_id}",
                    0,
                    3,
                    0.9,
                    entities=(EntityCandidate("Max", "pet"),),
                ),
            )
            for record in records
        }

    def test_grouped_batch_completes_all_chunks_in_order(self) -> None:
        batch, records = self.make_batch(4)
        transport = RecordingGraphTransport()
        orchestrator = self.orchestrator(
            transport,
            write_batch_size=10,
            candidates_by_record=self.candidates_for(records),
        )
        result = orchestrator.run_batch(batch)
        self.assertEqual(result.completed_count, 4)
        self.assertEqual(
            [r.state for r in result.results], [IngestionJobState.COMPLETED] * 4
        )
        self.assertEqual([r.accepted_fact_count for r in result.results], [1, 1, 1, 1])
        # order matches input record order, not completion/processing order
        expected_chunk_ids = [
            chunk_from_record(batch, record).chunk_id for record in records
        ]
        self.assertEqual([r.chunk_id for r in result.results], expected_chunk_ids)
        for i, record in enumerate(records):
            self.assertIn(f"fact-{record.record_id}", self.search_index_store._rows)

    def test_grouped_batch_uses_fewer_write_calls_than_per_chunk(self) -> None:
        """4 chunks, same node/relationship shapes -- batched should collapse
        to the same call count one chunk alone would need (buckets merge),
        not scale with chunk count."""
        batch, records = self.make_batch(4)
        candidates = self.candidates_for(records)

        transport_batched = RecordingGraphTransport()
        self.orchestrator(
            transport_batched, write_batch_size=10, candidates_by_record=candidates
        ).run_batch(batch)

        # Reset state and run the same batch unbatched (write_batch_size=1) for comparison.
        self.setUp()
        batch2, records2 = self.make_batch(4)
        candidates2 = self.candidates_for(records2)
        transport_unbatched = RecordingGraphTransport()
        self.orchestrator(
            transport_unbatched, write_batch_size=1, candidates_by_record=candidates2
        ).run_batch(batch2)

        self.assertLess(len(transport_batched.writes), len(transport_unbatched.writes))

    def test_grouped_batch_respects_group_boundary(self) -> None:
        """write_batch_size=2 over 4 records makes two groups of 2 -- more
        write calls than one group of 4, fewer than fully unbatched."""
        batch, records = self.make_batch(4)
        candidates = self.candidates_for(records)

        transport_one_group = RecordingGraphTransport()
        self.orchestrator(
            transport_one_group, write_batch_size=10, candidates_by_record=candidates
        ).run_batch(batch)

        self.setUp()
        batch2, records2 = self.make_batch(4)
        candidates2 = self.candidates_for(records2)
        transport_two_groups = RecordingGraphTransport()
        self.orchestrator(
            transport_two_groups, write_batch_size=2, candidates_by_record=candidates2
        ).run_batch(batch2)

        self.assertLess(
            len(transport_one_group.writes), len(transport_two_groups.writes)
        )

    def test_already_completed_chunk_is_excluded_from_batch_but_group_mates_still_process(
        self,
    ) -> None:
        batch, records = self.make_batch(3)
        candidates = self.candidates_for(records)
        transport = RecordingGraphTransport()
        orchestrator = self.orchestrator(
            transport, write_batch_size=10, candidates_by_record=candidates
        )

        # Pre-complete the first chunk via the solo path.
        first_result = orchestrator.run_record(batch, records[0])
        self.assertEqual(first_result.state, IngestionJobState.COMPLETED)

        # Now run the whole batch (including the already-completed first record).
        result = orchestrator.run_batch(batch)
        self.assertEqual(result.completed_count, 3)
        self.assertEqual(
            result.results[0].accepted_fact_count, 0
        )  # short-circuited, not re-extracted
        self.assertEqual(result.results[1].accepted_fact_count, 1)
        self.assertEqual(result.results[2].accepted_fact_count, 1)

    def test_batched_graph_write_failure_marks_whole_group_retryable_not_lost(
        self,
    ) -> None:
        class _AlwaysFailsTransport:
            def write(self, cypher, rows, idempotency_key):
                raise ConnectionError("simulated transient graph-node failure")

            def read(self, cypher, parameters, bookmark):
                return []

        batch, records = self.make_batch(3)
        candidates = self.candidates_for(records)
        orchestrator = self.orchestrator(
            _AlwaysFailsTransport(),
            write_batch_size=10,
            candidates_by_record=candidates,
        )
        result = orchestrator.run_batch(batch)
        # All three failed together (one batched write covering the group), none silently dropped.
        self.assertEqual(len(result.results), 3)
        self.assertTrue(
            all(r.state == IngestionJobState.RETRYABLE_FAILED for r in result.results)
        )
        self.assertTrue(all(r.error is not None for r in result.results))

    def test_group_of_one_matches_run_record(self) -> None:
        batch, records = self.make_batch(1)
        candidates = self.candidates_for(records)
        transport = RecordingGraphTransport()
        orchestrator = self.orchestrator(
            transport, write_batch_size=10, candidates_by_record=candidates
        )
        result = orchestrator.run_batch(batch)
        self.assertEqual(result.completed_count, 1)
        self.assertEqual(result.results[0].accepted_fact_count, 1)


class CompensationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.chunk_store = InMemoryChunkStore()
        self.job_store = InMemoryJobStore()
        self.allocator = InMemoryGraphIdAllocator()
        self.manifest_store = InMemoryGraphManifestStore()
        self.embedding_store = InMemoryEmbeddingStore()
        self.search_index_store = InMemorySearchIndexStore()
        self.entity_registry = EntityRegistry(self.allocator)

    def batch_and_record(
        self,
        content: str = "Max the dog likes walks",
        session_id: str = "session-001",
        record_id: str = "record-001",
    ) -> tuple[ContextBatch, ContextRecord]:
        record = ContextRecord(
            record_id=record_id,
            session_id=session_id,
            occurred_at=datetime(2026, 1, 10, 9, tzinfo=timezone.utc),
            content=content,
        )
        batch = ContextBatch(
            "ingestion-001",
            "context-001",
            SourceDescriptor("fixture", "fixture-001"),
            (record,),
        )
        return batch, record

    def orchestrator(
        self,
        transport: object,
        *,
        embedder: object | None = None,
        embedding_store: object | None = None,
        search_index_store: object | None = None,
        update_classifier: object | None = None,
        find_existing_facts: object | None = None,
        write_batch_size: int = 1,
        candidates_by_record: dict | None = None,
    ) -> IngestionOrchestrator:
        drafts = candidates_by_record or {
            "record-001": (
                ExtractionDraft(
                    "fact-001",
                    "Max likes walks",
                    0,
                    3,
                    0.9,
                    entities=(EntityCandidate("Max", "pet"),),
                ),
            )
        }
        extractor = DeterministicExtractor(drafts)
        extraction_service = ExtractionService(extractor, InMemoryExtractionStore())
        graph_writer = GraphWriter(self.manifest_store, transport)
        plan_builder = GraphPlanBuilder(self.allocator)

        def resolve_entity(context_id: str, surface: str, entity_type: str):
            return self.entity_registry.resolve(
                context_id=context_id, surface=surface, entity_type=entity_type
            ).entity

        return IngestionOrchestrator(
            chunk_store=self.chunk_store,
            job_store=self.job_store,
            extraction_service=extraction_service,
            graph_plan_builder=plan_builder,
            graph_writer=graph_writer,
            resolve_entity=resolve_entity,
            embedder=embedder or DeterministicEmbedder(),
            embedding_store=embedding_store or self.embedding_store,
            search_index_store=search_index_store or self.search_index_store,
            update_classifier=update_classifier,
            find_existing_facts=find_existing_facts,
            write_batch_size=write_batch_size,
        )

    def test_run_chunk_embedding_failure_compensates_graph(self) -> None:
        """When embedding generation fails after graph write, orchestrator soft-archives Fact node."""

        class _FailingEmbedder:
            def embed(self, text: str):
                raise RuntimeError("simulated embedder model crash")

        batch, record = self.batch_and_record()
        transport = RecordingGraphTransport()
        orchestrator = self.orchestrator(transport, embedder=_FailingEmbedder())

        result = orchestrator.run_record(batch, record)
        self.assertEqual(result.state, IngestionJobState.RETRYABLE_FAILED)
        self.assertIn("embedder model crash", result.error or "")

        # Initial write had is_current=True, archived=False
        initial_fact_writes = [
            row
            for cypher, rows, _ in transport.writes
            if "SET n:Fact" in cypher
            for row in rows
            if row.get("logical_key") == "fact:fact-001" and not row.get("archived")
        ]
        self.assertEqual(len(initial_fact_writes), 1)

        # Compensating write occurred with archived=True, is_current=False
        compensating_writes = [
            row
            for cypher, rows, _ in transport.writes
            if "SET n:Fact" in cypher
            for row in rows
            if row.get("logical_key") == "fact:fact-001" and row.get("archived") is True
        ]
        self.assertEqual(len(compensating_writes), 1)
        self.assertFalse(compensating_writes[0]["is_current"])

    def test_run_chunk_verification_failure_compensates_graph_and_deactivates_stores(
        self,
    ) -> None:
        """When verification fails (e.g. dropped embedding), graph is compensated and search index is deactivated."""

        class _DroppingEmbeddingStore(InMemoryEmbeddingStore):
            def contains(
                self, context_id: str, subject_kind: str, subject_id: str
            ) -> bool:
                return False  # triggers verification failure

        batch, record = self.batch_and_record()
        transport = RecordingGraphTransport()
        orchestrator = self.orchestrator(
            transport,
            embedding_store=_DroppingEmbeddingStore(),
        )

        result = orchestrator.run_record(batch, record)
        self.assertEqual(result.state, IngestionJobState.RETRYABLE_FAILED)
        self.assertIn("embedding verification failed", result.error or "")

        # Compensating write occurred in graph
        archived_writes = [
            row
            for cypher, rows, _ in transport.writes
            if "SET n:Fact" in cypher
            for row in rows
            if row.get("logical_key") == "fact:fact-001" and row.get("archived") is True
        ]
        self.assertEqual(len(archived_writes), 1)

        # Search index was deactivated
        self.assertFalse(self.search_index_store.contains(batch.context_id, "fact-001"))

    def test_run_chunk_compensation_restores_superseded_prior_fact(self) -> None:
        """When a superseding fact's verification fails, the prior fact's is_current is restored to True."""
        from context_memory.core.resolution import (
            FactState,
            TemporalRelation,
            TemporalUpdateDecision,
        )

        class _Classifier:
            def classify(self, new_fact, prior_fact):
                return TemporalUpdateDecision(
                    TemporalRelation.STATE_CHANGE,
                    "test",
                    prior_superseded_at=new_fact.observed_at,
                )

        entity_id = self.allocator.allocate_graph_id(
            "entity", "context-001", "entity:max"
        )
        prior_fact = FactState(
            "fact-old",
            entity_id,
            "likes",
            "Max likes walking",
            datetime(2025, 1, 1, tzinfo=timezone.utc),
        )

        def find_existing(context_id, subject_id, predicate_key):
            if subject_id == entity_id and predicate_key == "likes":
                return [prior_fact]
            return []

        class _DroppingSearchIndexStore(InMemorySearchIndexStore):
            def contains(self, context_id: str, fact_id: str) -> bool:
                return False  # triggers verification failure

        batch, record = self.batch_and_record()
        transport = RecordingGraphTransport()
        orchestrator = self.orchestrator(
            transport,
            search_index_store=_DroppingSearchIndexStore(),
            update_classifier=_Classifier(),
            find_existing_facts=find_existing,
            candidates_by_record={
                "record-001": (
                    ExtractionDraft(
                        "fact-new",
                        "Max likes running",
                        0,
                        3,
                        0.9,
                        entities=(EntityCandidate("Max", "pet"),),
                        action="UPDATE",
                        predicate_key="likes",
                    ),
                )
            },
        )

        result = orchestrator.run_record(batch, record)
        self.assertEqual(result.state, IngestionJobState.RETRYABLE_FAILED)

        # Compensating write soft-archives fact-new AND restores fact-old
        restored_priors = [
            row
            for cypher, rows, _ in transport.writes
            if "SET n:Fact" in cypher
            for row in rows
            if row.get("logical_key") == "fact:fact-old"
            and row.get("is_current") is True
        ]
        self.assertEqual(len(restored_priors), 1)
        self.assertEqual(restored_priors[0]["superseded_at"], 9999999999)

        archived_new = [
            row
            for cypher, rows, _ in transport.writes
            if "SET n:Fact" in cypher
            for row in rows
            if row.get("logical_key") == "fact:fact-new" and row.get("archived") is True
        ]
        self.assertEqual(len(archived_new), 1)
        self.assertFalse(archived_new[0]["is_current"])

    def test_run_group_embedding_failure_compensates_all_pending_chunks(self) -> None:
        """Batched run failure at embedding stage compensates every chunk written in the batch."""

        class _FailingEmbedder:
            def embed(self, text: str):
                raise RuntimeError("simulated batched embedding failure")

            def embed_batch(self, texts):
                raise RuntimeError("simulated batched embedding failure")

        records = [
            ContextRecord(
                record_id=f"record-{i:03d}",
                session_id="session-001",
                occurred_at=datetime(2026, 1, 10, 9, i, tzinfo=timezone.utc),
                content=f"Fact number {i}",
            )
            for i in range(3)
        ]
        batch = ContextBatch(
            "ingestion-001",
            "context-001",
            SourceDescriptor("fixture", "fixture-001"),
            tuple(records),
        )
        candidates = {
            r.record_id: (
                ExtractionDraft(
                    f"fact-{r.record_id}",
                    f"text for {r.record_id}",
                    0,
                    3,
                    0.9,
                    entities=(EntityCandidate("Max", "pet"),),
                ),
            )
            for r in records
        }
        transport = RecordingGraphTransport()
        orchestrator = self.orchestrator(
            transport,
            embedder=_FailingEmbedder(),
            write_batch_size=10,
            candidates_by_record=candidates,
        )

        batch_result = orchestrator.run_batch(batch)
        self.assertEqual(batch_result.completed_count, 0)
        self.assertTrue(
            all(
                r.state == IngestionJobState.RETRYABLE_FAILED
                for r in batch_result.results
            )
        )

        # Check all 3 facts were compensated with archived=True
        archived_facts = {
            row["logical_key"]
            for cypher, rows, _ in transport.writes
            if "SET n:Fact" in cypher
            for row in rows
            if row.get("archived") is True
        }
        self.assertEqual(
            archived_facts,
            {"fact:fact-record-000", "fact:fact-record-001", "fact:fact-record-002"},
        )

    def test_run_group_verification_failure_compensates_only_failed_chunk(self) -> None:
        """In a group of 2, if chunk 1 fails verification, only chunk 1 is compensated; chunk 0 completes."""
        records = [
            ContextRecord(
                record_id=f"record-{i:03d}",
                session_id="session-001",
                occurred_at=datetime(2026, 1, 10, 9, i, tzinfo=timezone.utc),
                content=f"Fact number {i}",
            )
            for i in range(2)
        ]
        batch = ContextBatch(
            "ingestion-001",
            "context-001",
            SourceDescriptor("fixture", "fixture-001"),
            tuple(records),
        )
        candidates = {
            r.record_id: (
                ExtractionDraft(
                    f"fact-{r.record_id}",
                    f"text for {r.record_id}",
                    0,
                    3,
                    0.9,
                    entities=(EntityCandidate("Max", "pet"),),
                ),
            )
            for r in records
        }

        class _SelectiveSearchIndexStore(InMemorySearchIndexStore):
            def contains(self, context_id: str, fact_id: str) -> bool:
                if fact_id == "fact-record-001":
                    return False
                return super().contains(context_id, fact_id)

        transport = RecordingGraphTransport()
        orchestrator = self.orchestrator(
            transport,
            search_index_store=_SelectiveSearchIndexStore(),
            write_batch_size=10,
            candidates_by_record=candidates,
        )

        batch_result = orchestrator.run_batch(batch)
        self.assertEqual(batch_result.completed_count, 1)
        self.assertEqual(batch_result.results[0].state, IngestionJobState.COMPLETED)
        self.assertEqual(
            batch_result.results[1].state, IngestionJobState.RETRYABLE_FAILED
        )

        # Only fact-record-001 is archived
        archived_facts = {
            row["logical_key"]
            for cypher, rows, _ in transport.writes
            if "SET n:Fact" in cypher
            for row in rows
            if row.get("archived") is True
        }
        self.assertEqual(archived_facts, {"fact:fact-record-001"})

    def test_retry_after_compensation_succeeds_without_collision(self) -> None:
        """After compensation, retrying the chunk with working infrastructure succeeds cleanly."""

        class _FlakyEmbedder:
            def __init__(self) -> None:
                self.should_fail = True

            def embed(self, text: str):
                if self.should_fail:
                    raise RuntimeError("flaky embedder failure")
                return (0.1, 0.2, 0.3)

        flaky = _FlakyEmbedder()
        batch, record = self.batch_and_record()
        transport = RecordingGraphTransport()
        orchestrator = self.orchestrator(transport, embedder=flaky)

        first_run = orchestrator.run_record(batch, record)
        self.assertEqual(first_run.state, IngestionJobState.RETRYABLE_FAILED)

        # Repair embedder and retry
        flaky.should_fail = False
        chunk = self.chunk_store.get(batch.context_id, first_run.chunk_id)
        job = self.job_store.get(first_run.chunk_id)
        retry_run = orchestrator.run_chunk(batch, record, chunk, job.state)

        self.assertEqual(retry_run.state, IngestionJobState.COMPLETED)
        self.assertEqual(retry_run.accepted_fact_count, 1)
        self.assertTrue(self.search_index_store.contains(batch.context_id, "fact-001"))


if __name__ == "__main__":
    unittest.main()
