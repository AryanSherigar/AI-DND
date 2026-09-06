"""LongMemEval Benchmark Runner.

Ingests LongMemEval historical sessions into the context memory system
and executes retrieval queries against the ingested context, writing
predictions in the official JSONL format: {"question_id": "...", "hypothesis": "..."}.

Bare `§N` references below are sections of docs/fixes_and_evaluation_findings.md.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from context_memory.client.hydradb_http import HydraHttpTransport
from context_memory.composition import build_ingestion_and_retrieval
from context_memory.core.config import Config
from context_memory.core.journal import StepJournal
from context_memory.core.llm_client import LLMClient
from context_memory.core.logging import disable_metrics_collection, drain_metrics, enable_metrics_collection
from context_memory.ingestion.embedding import SentenceTransformerEmbedder
from context_memory.ingestion.model_adapters import LLMExtractor
from context_memory.ingestion.orchestrator import IngestionOrchestrator
from context_memory.ingestion.sources.longmemeval import adapt_longmemeval_instance, parse_longmemeval_timestamp
from context_memory.retrieval import HybridRetrievalEngine


class PrefetchingExtractor:
    """Wraps a real `Extractor` and runs `.extract()` for many records concurrently
    ahead of `orchestrator.run_batch()`'s serial loop, then serves results from a
    warm cache — so the loop's per-turn cost drops from a full network round trip
    to a dict lookup.

    Why this is safe when parallelizing the batch loop itself is not: every store
    in this pipeline (`chunk_store`, `job_store`, `manifest_store`, ...) shares one
    `psycopg` connection, which is not safe for concurrent access from multiple
    threads. Extraction has no such shared state — it's a pure LLM network call,
    and the OpenAI SDK client is thread-safe for concurrent requests. This class
    only moves *that* call earlier; `orchestrator.run_batch()` still runs exactly
    as sequentially as before, and never touches Postgres/HydraDB concurrently.
    """

    def __init__(self, inner: Any, max_workers: int = 8, progress_every: int = 25, batch_size: int = 1) -> None:
        self._inner = inner
        self._max_workers = max_workers
        self._progress_every = progress_every
        # Opt-in batched extraction (Config.extraction_batch_size, see
        # docs/fixes_and_evaluation_findings.md §7): only takes effect when >1
        # AND `inner` actually exposes `extract_batch` (LLMExtractor does;
        # FakeExtractor and any other test double correctly fall back to the
        # unbatched per-record path below instead of erroring).
        self._batch_size = max(1, batch_size)
        self._cache: dict[str, Any] = {}
        # ExtractionService gates on these two attributes (see extraction.py's
        # `extract()`) — proxy them through so the wrapper is transparent to it.
        self.extractor_name = getattr(inner, "extractor_name", None)
        self.extractor_version = getattr(inner, "extractor_version", None)

    def _report_progress(self, done: int, total: int, failed: int, started: float) -> None:
        elapsed = time.perf_counter() - started
        rate = done / elapsed if elapsed > 0 else 0.0
        eta = (total - done) / rate if rate > 0 else 0.0
        print(
            f"      prefetch {done}/{total} ({100 * done / total:.0f}%)"
            f" {rate * 60:.1f} calls/min elapsed {elapsed / 60:.1f}m"
            f" eta {eta / 60:.1f}m" + (f" failed={failed}" if failed else ""),
            flush=True,
        )

    def prefetch(self, records: Sequence[Any]) -> None:
        """Runs extraction for every record concurrently and warms the cache.
        Call this once per instance's records before `orchestrator.run_batch()`.

        Emits periodic progress with a live throughput-based ETA. This phase can
        dominate an instance's wall clock — a provider token-per-minute ceiling
        (Groq's free tier is 8k TPM) throttles it far below what the per-call
        latency alone suggests, and the SDK absorbs the resulting 429s as silent
        backoff. Without progress output there is no way to tell a slow run from
        a wedged one, which is exactly the hole this closes.
        """
        if not records:
            return
        total = len(records)
        done = failed = 0
        reported = 0
        started = time.perf_counter()

        use_batching = self._batch_size > 1 and hasattr(self._inner, "extract_batch")
        if use_batching:
            groups = [records[i : i + self._batch_size] for i in range(0, total, self._batch_size)]
            print(
                f"    prefetching {total} extractions in {len(groups)} batches of up to "
                f"{self._batch_size} ({self._max_workers} workers)...",
                flush=True,
            )
            with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
                futures = {pool.submit(self._inner.extract_batch, group): group for group in groups}
                for future in as_completed(futures):
                    group = futures[future]
                    try:
                        self._cache.update(future.result())
                    except Exception as exc:
                        # §2 fix: was caching `()` per record here -- silently
                        # indistinguishable from "no facts in these turns."
                        # Cache the exception itself instead; `.extract()`
                        # below re-raises it on consumption, so it actually
                        # reaches run_chunk's own error handling, which this
                        # comment already claimed (incorrectly, until now).
                        failed += len(group)
                        record_ids = [r.record_id for r in group]
                        print(f"  prefetch batch extraction failed for {record_ids}: {exc}", file=sys.stderr, flush=True)
                        for record in group:
                            self._cache[record.record_id] = exc
                    done += len(group)
                    if done - reported >= self._progress_every or done == total:
                        reported = done
                        self._report_progress(done, total, failed, started)
            return

        print(f"    prefetching {total} extractions ({self._max_workers} workers)...", flush=True)
        with ThreadPoolExecutor(max_workers=self._max_workers) as pool:
            futures = {pool.submit(self._inner.extract, record): record.record_id for record in records}
            for future in as_completed(futures):
                record_id = futures[future]
                try:
                    self._cache[record_id] = future.result()
                except Exception as exc:
                    # §2 fix: cache the exception, not `()` -- see the
                    # batched branch above for why.
                    failed += 1
                    print(f"  prefetch extraction failed for {record_id}: {exc}", file=sys.stderr, flush=True)
                    self._cache[record_id] = exc
                done += 1
                if done % self._progress_every == 0 or done == total:
                    self._report_progress(done, total, failed, started)

    def extract(self, record: Any) -> Any:
        if record.record_id in self._cache:
            cached = self._cache.pop(record.record_id)
            if isinstance(cached, BaseException):
                # §2 fix: a prefetch failure surfaces here as a real
                # exception on consumption, same as an uncached direct call
                # would raise -- never silently returned as an empty result.
                raise cached
            return cached
        # Cache miss (shouldn't happen if prefetch() covered the batch) — fall
        # back to a direct synchronous call so correctness never depends on
        # prefetch coverage, only speed does.
        return self._inner.extract(record)


def _report_rate_limits(llm_client: LLMClient) -> int | None:
    """Prints the provider's advertised rate limits up front and returns the
    tokens-per-minute limit (or None if unavailable/unparseable).

    A tokens-per-minute ceiling, not per-call latency, is what actually
    bounds throughput here (measured live, pre-migration: Groq's free tier
    advertised 8k TPM via `x-ratelimit-limit-*` response headers on its
    OpenAI-compatible endpoint). Vertex AI's `google-genai` client has no
    equivalent raw-response/header probe this can read -- quota there is a
    project/region-level GCP setting, not something a client call surfaces
    per-request. Left as a best-effort no-op (returns `None` immediately)
    rather than a call against a header shape Vertex doesn't have: a run
    can still look mysteriously slow under quota pressure, but this can no
    longer explain why on this provider.
    """
    return None


def create_pipeline(
    pool: Any,
    hydra_transport: Any,
    llm_client: LLMClient,
    embedder: Any,
    extraction_store: Any | None = None,
    extractor: Any | None = None,
    extraction_workers: int = 0,
    progress_every: int = 25,
    config: Config | None = None,
    journal: StepJournal | None = None,
) -> tuple[IngestionOrchestrator, HybridRetrievalEngine, Any]:
    """Wires standard production ingestion orchestrator and hybrid retrieval engine.

    Returns `(orchestrator, retrieval_engine, extractor)` — the extractor is
    returned so the caller can call `.prefetch(records)` on it before
    `orchestrator.run_batch()` when `extraction_workers > 0` (see
    `PrefetchingExtractor`); it's a no-op passthrough otherwise.

    `journal`, when given, journals every LLM call the same way production
    traffic through `build_memory_engine` already does -- benchmark/eval
    runs are the highest-volume real usage this codebase has and had no
    audit trail at all until this parameter existed, an omission `create_pipeline`
    living outside `composition.py`'s "the one place wiring happens" made easy
    to miss (see that module's own docstring for the drift this already caused
    once, for the rerank client)."""
    config = config or Config()

    if extractor is None:
        extractor = LLMExtractor(config.get_extractor_client(), config)

    if extraction_workers > 0:
        extractor = PrefetchingExtractor(
            extractor, max_workers=extraction_workers, progress_every=progress_every,
            batch_size=config.extraction_batch_size,
        )

    orchestrator, retrieval_engine, extractor = build_ingestion_and_retrieval(
        pool=pool,
        hydra_transport=hydra_transport,
        embedder=embedder,
        config=config,
        reader_llm_client=llm_client,
        extractor=extractor,
        extraction_store=extraction_store,
        journal=journal,
    )
    return orchestrator, retrieval_engine, extractor


def evaluate_instance(
    instance: Mapping[str, Any],
    orchestrator: IngestionOrchestrator,
    retrieval_engine: HybridRetrievalEngine,
    extractor: Any | None = None,
    metrics_writer: Any | None = None,
) -> dict[str, str]:
    """Ingest one benchmark instance and retrieve its hypothesis.

    `metrics_writer`, when given, is called once per structured metrics
    record produced for this instance -- one `record_type="instance_summary"`
    (turns, fact counts, and the three top-level stage timings below) plus
    one `record_type="stage"` per `core.logging.timed_operation` call this
    instance triggered anywhere in the pipeline (every ingestion and
    retrieval stage, transparently -- see `core/logging.py`'s metrics
    sink). Callers that don't care about this (existing tests, ad-hoc
    scripts) just omit it and get the exact same behavior as before.
    """
    question_id = str(instance["question_id"])
    question = str(instance.get("question", ""))
    raw_date = instance.get("question_date")

    if raw_date:
        question_date = parse_longmemeval_timestamp(raw_date, "question_date")
    else:
        question_date = datetime.now(timezone.utc)

    drain_metrics()  # discard anything stale from setup/wiring so this instance's slice starts clean

    # 1. Ingest historical context batch synchronously. When a PrefetchingExtractor
    # is in play, warm every turn's extraction concurrently first — run_batch's own
    # loop stays serial (it must: shared psycopg connection), but its per-turn LLM
    # round trip becomes a cache hit.
    batch = adapt_longmemeval_instance(instance, ingestion_id=f"run:{question_id}")
    prefetch_s = 0.0
    if extractor is not None and hasattr(extractor, "prefetch"):
        t_prefetch = time.perf_counter()
        extractor.prefetch(batch.records)
        prefetch_s = time.perf_counter() - t_prefetch
        print(f"    prefetched {len(batch.records)} extractions in {prefetch_s:.1f}s")

    t_ingest = time.perf_counter()
    batch_result = orchestrator.run_batch(batch)
    ingest_s = time.perf_counter() - t_ingest
    accepted_facts = sum(r.accepted_fact_count for r in batch_result.results)

    # 2. Retrieve answer
    t_retrieve = time.perf_counter()
    hypothesis = retrieval_engine.retrieve_and_answer(
        context_id=batch.context_id,
        question=question,
        question_date=question_date,
    )
    retrieve_s = time.perf_counter() - t_retrieve

    turns = len(batch.records)
    print(
        f"    ingest {ingest_s:.1f}s over {turns} turns ({ingest_s / max(turns, 1):.2f}s/turn)"
        f" | retrieve {retrieve_s:.1f}s"
    )

    if metrics_writer is not None:
        metrics_writer({
            "record_type": "instance_summary",
            "question_id": question_id,
            "question_type": instance.get("question_type"),
            "turns": turns,
            "completed_chunks": batch_result.completed_count,
            "accepted_facts": accepted_facts,
            "prefetch_s": round(prefetch_s, 3),
            "ingest_s": round(ingest_s, 3),
            "retrieve_s": round(retrieve_s, 3),
            "total_s": round(prefetch_s + ingest_s + retrieve_s, 3),
        })
        for stage_record in drain_metrics():
            stage_record["record_type"] = "stage"
            stage_record["question_id"] = question_id
            metrics_writer(stage_record)

    return {
        "question_id": question_id,
        "hypothesis": hypothesis,
    }


def evaluate_dataset(
    instances: Sequence[Mapping[str, Any]],
    orchestrator: IngestionOrchestrator,
    retrieval_engine: HybridRetrievalEngine,
    output_path: Path,
    limit: int | None = None,
    offset: int = 0,
    extractor: Any | None = None,
    metrics_path: Path | None = None,
) -> list[dict[str, str]]:
    """Evaluates a list of benchmark instances, streaming hypotheses to JSONL.

    `metrics_path` (default: `<output_path>` with `.metrics.jsonl` appended)
    gets one JSON line per `record_type="instance_summary"` and per
    `record_type="stage"` (see `evaluate_instance`) -- every
    `timed_operation` call across the whole ingest+retrieve pipeline for
    every instance, already parsed, tagged with `question_id`, flushed
    per-instance same as the hypotheses file. This replaces needing to
    grep/regex the text `--log-level INFO` output to answer "where did the
    time go" for a real run -- that text log is unaffected and still
    prints; this is a second, structured, directly-loadable (jq/pandas)
    sink of exactly the same underlying measurements.
    """
    selected_instances = instances[offset:]
    if limit is not None:
        selected_instances = selected_instances[:limit]

    total = len(selected_instances)
    print(f"Starting benchmark run: {total} instances (offset={offset}, limit={limit})")
    print(f"Writing outputs to: {output_path}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if offset > 0 and output_path.exists() else "w"

    if metrics_path is None:
        metrics_path = output_path.with_suffix(output_path.suffix + ".metrics.jsonl")
    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    metrics_mode = "a" if offset > 0 and metrics_path.exists() else "w"
    print(f"Writing per-stage performance metrics to: {metrics_path}")

    results: list[dict[str, str]] = []
    start_time = time.perf_counter()

    enable_metrics_collection()
    try:
        with output_path.open(mode, encoding="utf-8") as out_file, metrics_path.open(metrics_mode, encoding="utf-8") as metrics_file:
            def write_metric(record: dict[str, Any]) -> None:
                metrics_file.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")
                metrics_file.flush()

            for idx, instance in enumerate(selected_instances, start=1):
                q_id = instance.get("question_id", f"unknown-{idx}")
                t0 = time.perf_counter()
                try:
                    record = evaluate_instance(instance, orchestrator, retrieval_engine, extractor, metrics_writer=write_metric)
                    results.append(record)
                    out_file.write(json.dumps(record, ensure_ascii=False) + "\n")
                    out_file.flush()
                    dur = time.perf_counter() - t0
                    print(f"[{idx}/{total}] question_id={q_id} ({dur:.2f}s) -> hypothesis={record['hypothesis'][:60]!r}...")
                except Exception as exc:
                    dur = time.perf_counter() - t0
                    print(f"[{idx}/{total}] question_id={q_id} ({dur:.2f}s) ERROR: {exc}", file=sys.stderr)
                    fallback_record = {"question_id": str(q_id), "hypothesis": "I do not have enough information to answer."}
                    results.append(fallback_record)
                    out_file.write(json.dumps(fallback_record, ensure_ascii=False) + "\n")
                    out_file.flush()
                    write_metric({"record_type": "instance_error", "question_id": str(q_id), "duration_s": round(dur, 3), "error": str(exc)})
    finally:
        disable_metrics_collection()

    total_dur = time.perf_counter() - start_time
    avg_speed = total / total_dur if total_dur > 0 else 0.0
    print(f"Finished benchmark run: {len(results)} evaluated in {total_dur:.2f}s ({avg_speed:.2f} questions/s)")
    return results


def parse_args(args: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Path to local LongMemEval JSON dataset")
    parser.add_argument("--output", required=True, type=Path, help="Path to write the output hypotheses JSONL")
    parser.add_argument("--limit", type=int, default=None, help="Maximum benchmark instances to evaluate")
    parser.add_argument("--offset", type=int, default=0, help="Starting index in the dataset (for resuming)")
    parser.add_argument(
        "--database-url",
        default=os.environ.get("CONTEXT_MEMORY_DATABASE_URL", "postgresql://context_memory@127.0.0.1:54329/context_memory"),
        help="PostgreSQL connection string",
    )
    parser.add_argument(
        "--hydradb-url",
        default=os.environ.get("CONTEXT_MEMORY_HYDRADB_URL", "http://127.0.0.1:8080"),
        help="HydraDB HTTP endpoint URL",
    )
    parser.add_argument(
        "--hydradb-token",
        default=os.environ.get("CONTEXT_MEMORY_HYDRADB_TOKEN", ""),
        help="Optional HydraDB bearer token",
    )
    parser.add_argument(
        "--hydradb-database",
        default=os.environ.get("CONTEXT_MEMORY_HYDRADB_DATABASE", "default"),
        help="HydraDB database name",
    )
    parser.add_argument(
        "--extractor",
        choices=["llm", "deterministic"],
        default="llm",
        help="Extractor implementation to use",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=25,
        help="Emit a prefetch progress line every N completed extractions.",
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help=(
            "Root log level. INFO surfaces the per-stage [START]/[DONE] latency lines "
            "from `core.logging.timed_operation` — without it (the default) every stage "
            "timing in the pipeline is silently suppressed and runs are unprofilable."
        ),
    )
    parser.add_argument(
        "--extraction-workers",
        type=int,
        default=8,
        help=(
            "Concurrent extraction LLM calls to prefetch per instance (0 disables, "
            "restoring fully serial behavior). Only extraction is parallelized — "
            "graph/Postgres writes stay serial because the pipeline shares one "
            "psycopg connection."
        ),
    )
    return parser.parse_args(args)


def main() -> int:
    args = parse_args()

    import logging as _logging
    from context_memory.core.logging import setup_logging
    setup_logging(level=getattr(_logging, args.log_level))

    if not args.input.exists():
        print(f"Error: input file {args.input} does not exist.", file=sys.stderr)
        return 1

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    if not isinstance(payload, list):
        print("Error: input dataset must contain a JSON array of instances.", file=sys.stderr)
        return 1

    from psycopg_pool import ConnectionPool

    # Built from Config, not ad-hoc env parsing. This function used to read
    # FIREWORKS_BASE_URL/FIREWORKS_API_KEY/EXTRACTOR_MODEL directly, which
    # predates the provider-neutral LLM_BASE_URL/LLM_API_KEY/LLM_MODEL names
    # in Config -- confirmed live, this was a real bug, not a hypothetical:
    # every "Groq"/"qwen" pilot run through this CLI during the provider
    # switch actually sent `model=accounts/fireworks/models/deepseek-v4-flash`
    # to Fireworks, because this parsing was never updated to match. Config is
    # the single source of truth for exactly this reason; a second copy of the
    # same resolution logic is how it drifted out of sync in the first place.
    config = Config()
    llm_client = config.get_extractor_client()

    print(f"Connecting to PostgreSQL at {args.database_url}...")
    with ConnectionPool(
        args.database_url,
        min_size=config.postgres_pool_min_size,
        max_size=config.postgres_pool_max_size,
        timeout=config.postgres_pool_timeout_seconds,
        kwargs={"autocommit": True},
        open=True,
    ) as pg_pool:
        pg_pool.wait(timeout=config.postgres_pool_timeout_seconds)
        from pathlib import Path
        from context_memory.persistence.migrations import apply_migrations
        migrations_dir = Path(__file__).resolve().parents[2] / "db" / "migrations"
        if migrations_dir.exists():
            with pg_pool.connection() as pg_conn:
                apply_migrations(pg_conn, migrations_dir)

        hydra_client = HydraHttpTransport(
            base_url=args.hydradb_url,
            bearer_token=args.hydradb_token or None,
            database=args.hydradb_database,
            timeout_seconds=config.hydradb_request_timeout_seconds,
        )
        embedder = SentenceTransformerEmbedder(model_name=config.embedding_model_name)

        if args.extractor == "deterministic":
            from context_memory.ingestion.fakes import DeterministicExtractor
            extractor_impl = DeterministicExtractor()
        else:
            from context_memory.ingestion.model_adapters import LLMExtractor
            extractor_impl = LLMExtractor(llm_client, config)

        tpm = _report_rate_limits(llm_client)
        if tpm is not None and args.extraction_workers > 0:
            # More workers than the token budget can actually feed doesn't buy
            # throughput -- measured live: 4 workers still degraded from 63 to
            # 43 calls/min over one run as the SDK absorbed 429s, because the
            # ceiling is tokens/min, not concurrent connections. 2000 tokens
            # per worker is a deliberately conservative per-worker share (real
            # extraction calls ran ~660-1500 prompt tokens in this session);
            # this only ever lowers --extraction-workers, never raises it.
            safe_workers = max(1, tpm // 2000)
            if args.extraction_workers > safe_workers:
                print(
                    f"Clamping --extraction-workers {args.extraction_workers} -> {safe_workers} "
                    f"(based on {tpm} tokens/min)"
                )
                args.extraction_workers = safe_workers

        orchestrator, retrieval_engine, active_extractor = create_pipeline(
            pool=pg_pool,
            hydra_transport=hydra_client,
            llm_client=llm_client,
            embedder=embedder,
            extractor=extractor_impl,
            extraction_workers=args.extraction_workers,
            progress_every=args.progress_every,
            config=config,
        )
        if args.extraction_workers > 0:
            print(f"Extraction prefetch enabled: {args.extraction_workers} concurrent calls per instance")
        if config.ingestion_write_batch_size > 1:
            print(f"Graph/embedding write batching enabled: {config.ingestion_write_batch_size} chunks per flush")

        evaluate_dataset(
            instances=payload,
            orchestrator=orchestrator,
            retrieval_engine=retrieval_engine,
            output_path=args.output,
            limit=args.limit,
            offset=args.offset,
            extractor=active_extractor,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
