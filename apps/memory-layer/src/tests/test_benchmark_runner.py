"""Unit tests for the LongMemEval benchmark runner."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from context_memory.core.models import ContextRecord
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
from evaluation.benchmark_runner import evaluate_dataset, evaluate_instance


class BenchmarkRunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.chunk_store = InMemoryChunkStore()
        self.job_store = InMemoryJobStore()
        self.manifest_store = InMemoryGraphManifestStore()
        self.embedding_store = InMemoryEmbeddingStore()
        self.search_index_store = InMemorySearchIndexStore()
        self.allocator = InMemoryGraphIdAllocator()
        self.transport = RecordingGraphTransport()
        self.extractor = DeterministicExtractor()
        self.extraction_store = InMemoryExtractionStore()
        self.extraction_service = ExtractionService(
            self.extractor, self.extraction_store
        )
        self.entity_registry = EntityRegistry(allocator=self.allocator)
        self.plan_builder = GraphPlanBuilder(allocator=self.allocator)
        self.graph_writer = GraphWriter(
            manifest_store=self.manifest_store, transport=self.transport
        )
        self.embedder = DeterministicEmbedder()

        self.orchestrator = IngestionOrchestrator(
            chunk_store=self.chunk_store,
            job_store=self.job_store,
            extraction_service=self.extraction_service,
            graph_plan_builder=self.plan_builder,
            graph_writer=self.graph_writer,
            resolve_entity=self.entity_registry.resolve_entity,
            embedder=self.embedder,
            embedding_store=self.embedding_store,
            search_index_store=self.search_index_store,
        )

        self.mock_retrieval = MagicMock()
        self.mock_retrieval.retrieve_and_answer.return_value = "Max is the dog's name."

        self.sample_instance = {
            "question_id": "test_q_001",
            "haystack_session_ids": ["session-001"],
            "haystack_dates": ["2022/01/01 (Sat) 09:00"],
            "haystack_sessions": [
                [{"role": "user", "content": "I adopted a dog named Max."}]
            ],
            "question": "What is the dog's name?",
            "question_type": "single-session-user",
            "question_date": "2022/01/03 (Mon) 10:00",
            "answer": "Max",
        }

    def test_evaluate_instance(self) -> None:
        res = evaluate_instance(
            self.sample_instance, self.orchestrator, self.mock_retrieval
        )
        self.assertEqual(res["question_id"], "test_q_001")
        self.assertEqual(res["hypothesis"], "Max is the dog's name.")
        self.mock_retrieval.retrieve_and_answer.assert_called_once()

    def test_evaluate_dataset_writes_jsonl(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "predictions.jsonl"
            instances = [
                self.sample_instance,
                {
                    "question_id": "test_q_002",
                    "haystack_session_ids": ["session-002"],
                    "haystack_dates": ["2022/01/02 (Sun) 10:00"],
                    "haystack_sessions": [
                        [{"role": "user", "content": "My favorite fruit is apple."}]
                    ],
                    "question": "What is my favorite fruit?",
                    "question_type": "single-session-user",
                    "question_date": "2022/01/03 (Mon) 10:00",
                    "answer": "apple",
                },
            ]

            results = evaluate_dataset(
                instances=instances,
                orchestrator=self.orchestrator,
                retrieval_engine=self.mock_retrieval,
                output_path=out_path,
            )

            self.assertEqual(len(results), 2)
            self.assertTrue(out_path.exists())

            lines = out_path.read_text(encoding="utf-8").strip().split("\n")
            self.assertEqual(len(lines), 2)

            rec1 = json.loads(lines[0])
            self.assertEqual(rec1["question_id"], "test_q_001")
            self.assertEqual(rec1["hypothesis"], "Max is the dog's name.")

            rec2 = json.loads(lines[1])
            self.assertEqual(rec2["question_id"], "test_q_002")
            self.assertEqual(rec2["hypothesis"], "Max is the dog's name.")

    def test_evaluate_dataset_writes_structured_performance_metrics(self) -> None:
        """Every instance gets one `instance_summary` record (turns, fact
        counts, the three top-level stage timings) plus one `stage` record
        per `timed_operation` call anywhere in the pipeline for that
        instance -- see `core/logging.py`'s metrics sink and
        `evaluate_instance`'s docstring."""
        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "predictions.jsonl"
            evaluate_dataset(
                instances=[self.sample_instance],
                orchestrator=self.orchestrator,
                retrieval_engine=self.mock_retrieval,
                output_path=out_path,
            )

            metrics_path = out_path.with_suffix(out_path.suffix + ".metrics.jsonl")
            self.assertTrue(metrics_path.exists())
            records = [
                json.loads(line)
                for line in metrics_path.read_text(encoding="utf-8").strip().split("\n")
            ]

            summaries = [r for r in records if r["record_type"] == "instance_summary"]
            self.assertEqual(len(summaries), 1)
            summary = summaries[0]
            self.assertEqual(summary["question_id"], "test_q_001")
            self.assertEqual(summary["question_type"], "single-session-user")
            self.assertEqual(summary["turns"], 1)
            self.assertEqual(summary["completed_chunks"], 1)
            self.assertGreaterEqual(summary["accepted_facts"], 0)
            for key in ("prefetch_s", "ingest_s", "retrieve_s", "total_s"):
                self.assertIn(key, summary)
                self.assertIsInstance(summary[key], float)

            stages = [r for r in records if r["record_type"] == "stage"]
            self.assertGreater(
                len(stages), 0
            )  # orchestrator.run_batch alone triggers several timed_operation calls
            self.assertTrue(all(r["question_id"] == "test_q_001" for r in stages))
            self.assertTrue(
                all(
                    "elapsed_ms" in r and "operation" in r and "outcome" in r
                    for r in stages
                )
            )
            operation_names = {r["operation"] for r in stages}
            self.assertIn("orchestrator.run_batch", operation_names)

    def test_evaluate_dataset_disables_metrics_collection_when_done(self) -> None:
        """Collection is process-wide global state -- must not leak into
        whatever runs after `evaluate_dataset` returns."""
        from context_memory.core.logging import (
            drain_metrics,
            get_logger,
            timed_operation,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            out_path = Path(tmpdir) / "predictions.jsonl"
            evaluate_dataset(
                instances=[self.sample_instance],
                orchestrator=self.orchestrator,
                retrieval_engine=self.mock_retrieval,
                output_path=out_path,
            )
        with timed_operation(get_logger("test.leak"), "after_run_op"):
            pass
        self.assertEqual(
            drain_metrics(), []
        )  # collection was disabled -- this op was never captured


class _RecordingBatchExtractor:
    """Fake with `extract_batch` (unlike DeterministicExtractor): records the
    groups it was called with so tests can assert on how PrefetchingExtractor
    partitions records into batches, without touching a real LLM."""

    extractor_name = "recording-batch-fixture"
    extractor_version = "v1"

    def __init__(self) -> None:
        self.batch_calls: list[list[str]] = []
        self.single_calls: list[str] = []

    def extract(self, record: ContextRecord) -> tuple:
        self.single_calls.append(record.record_id)
        return (f"draft-for-{record.record_id}",)

    def extract_batch(self, records) -> dict:
        self.batch_calls.append([r.record_id for r in records])
        return {r.record_id: (f"draft-for-{r.record_id}",) for r in records}


def _make_record(record_id: str) -> ContextRecord:
    from datetime import datetime, timezone

    return ContextRecord(
        record_id=record_id,
        session_id="session:001",
        actor_role="user",
        occurred_at=datetime.now(timezone.utc),
        content_type="text/plain",
        content="hello",
    )


class PrefetchingExtractorTests(unittest.TestCase):
    """docs/fixes_and_evaluation_findings.md §7: batch_size > 1 groups records
    into fewer, bigger extract_batch() calls instead of one extract() call per
    record; batch_size == 1 (the default) must reproduce today's behavior
    exactly, including against an extractor that has no extract_batch at all."""

    def test_batch_size_one_uses_the_unbatched_per_record_path_even_when_extract_batch_exists(
        self,
    ) -> None:
        from evaluation.benchmark_runner import PrefetchingExtractor

        inner = _RecordingBatchExtractor()
        prefetcher = PrefetchingExtractor(
            inner, max_workers=2, progress_every=1000, batch_size=1
        )
        records = [_make_record("r1"), _make_record("r2"), _make_record("r3")]
        prefetcher.prefetch(records)
        # batch_size=1 is the default (behavior-preserving) path -- must go
        # through extract() once per record, never extract_batch, even though
        # this fake exposes both.
        self.assertEqual(sorted(inner.single_calls), ["r1", "r2", "r3"])
        self.assertEqual(inner.batch_calls, [])

    def test_batch_size_above_one_groups_records_and_populates_the_cache(self) -> None:
        from evaluation.benchmark_runner import PrefetchingExtractor

        inner = _RecordingBatchExtractor()
        prefetcher = PrefetchingExtractor(
            inner, max_workers=2, progress_every=1000, batch_size=2
        )
        records = [_make_record(f"r{i}") for i in range(5)]
        prefetcher.prefetch(records)

        # 5 records at batch_size=2 -> 3 groups (2, 2, 1), never one-per-record.
        self.assertEqual(len(inner.batch_calls), 3)
        self.assertEqual(sorted(len(g) for g in inner.batch_calls), [1, 2, 2])
        covered = {rid for group in inner.batch_calls for rid in group}
        self.assertEqual(covered, {f"r{i}" for i in range(5)})

        for record in records:
            self.assertEqual(
                prefetcher.extract(record), (f"draft-for-{record.record_id}",)
            )

    def test_batch_size_above_one_falls_back_to_unbatched_path_when_inner_lacks_extract_batch(
        self,
    ) -> None:
        from evaluation.benchmark_runner import PrefetchingExtractor

        inner = DeterministicExtractor({"r1": ("solo-draft",)})
        prefetcher = PrefetchingExtractor(
            inner, max_workers=2, progress_every=1000, batch_size=4
        )
        records = [_make_record("r1")]
        prefetcher.prefetch(
            records
        )  # must not raise -- no extract_batch on DeterministicExtractor
        self.assertEqual(prefetcher.extract(records[0]), ("solo-draft",))

    def test_a_failed_batch_marks_every_record_in_that_group_as_failed_not_silently_empty(
        self,
    ) -> None:
        """§2 fix: a batch call that genuinely fails must surface as an
        exception on consumption -- `prefetch()` itself still swallows it
        (so one bad group doesn't abort every other group's prefetch), but
        `.extract()` re-raises rather than handing back `()`, which used to
        be indistinguishable from "the model found nothing.\""""
        from evaluation.benchmark_runner import PrefetchingExtractor

        class _FlakyBatchExtractor(_RecordingBatchExtractor):
            def extract_batch(self, records):
                raise RuntimeError("simulated provider failure for this batch")

        inner = _FlakyBatchExtractor()
        prefetcher = PrefetchingExtractor(
            inner, max_workers=2, progress_every=1000, batch_size=2
        )
        records = [_make_record("r1"), _make_record("r2")]
        prefetcher.prefetch(
            records
        )  # must not raise -- failure is deferred to consumption
        with self.assertRaises(RuntimeError):
            prefetcher.extract(records[0])
        with self.assertRaises(RuntimeError):
            prefetcher.extract(records[1])


if __name__ == "__main__":
    unittest.main()
