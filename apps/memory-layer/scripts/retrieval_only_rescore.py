"""Retrieval-only re-scoring against already-ingested contexts.

Valid whenever a change is retrieval/reader-side only: stored facts are exactly
what the current pipeline would produce, so ingestion need not be re-run
(~330s here vs ~5h for a full re-ingest). Reuses a pinned rewrite cache so the
nondeterministic query rewriter cannot leak noise into the delta.

Emits hypotheses; score them with the official grader:
    cd <LongMemEval checkout>
    .venv/bin/python3 src/evaluation/evaluate_qa.py deepseek-v3.2 <out.jsonl> <ref.json>

Usage:
    set -a && source src/.env && set +a
    PYTHONPATH=src .venv/bin/python3 scripts/retrieval_only_rescore.py \
        --instances benchmarks/longmemeval/sample30.json --out run.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import UTC, datetime

sys.path.insert(0, "src")

import psycopg

from context_memory.client.hydradb_http import HydraHttpTransport
from context_memory.core.config import Config
from context_memory.ingestion.embedding import VertexEmbedder
from context_memory.ingestion.sources.longmemeval import parse_longmemeval_timestamp
from evaluation.benchmark_runner import create_pipeline

_DEFAULT_CACHE = "benchmarks/longmemeval/rewrite_cache.json"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--instances", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--rewrite-cache", default=_DEFAULT_CACHE)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument(
        "--database-url",
        default=os.getenv(
            "CONTEXT_MEMORY_DATABASE_URL",
            "postgresql://context_memory@127.0.0.1:54329/context_memory",
        ),
    )
    ap.add_argument(
        "--hydradb-url",
        default=os.getenv("CONTEXT_MEMORY_HYDRADB_URL", "http://127.0.0.1:8080"),
    )
    args = ap.parse_args()

    if args.rewrite_cache:
        os.environ["QUERY_REWRITE_CACHE_PATH"] = args.rewrite_cache

    instances = json.load(open(args.instances))
    if args.limit:
        instances = instances[: args.limit]

    config = Config()
    conn = psycopg.connect(args.database_url)
    transport = HydraHttpTransport(
        base_url=args.hydradb_url,
        bearer_token=os.getenv("CONTEXT_MEMORY_HYDRADB_TOKEN"),
        timeout_seconds=config.hydradb_request_timeout_seconds,
    )
    embedder = VertexEmbedder(
        api_key=config.embedding_api_key, model_name=config.embedding_model_name
    )
    _, engine, _ = create_pipeline(
        conn, transport, config.get_extractor_client(), embedder, config=config
    )

    started = time.perf_counter()
    total = len(instances)
    with open(args.out, "w") as out:
        for i, inst in enumerate(instances, start=1):
            qid = str(inst["question_id"])
            raw_date = inst.get("question_date")
            qdate = (
                parse_longmemeval_timestamp(raw_date, "question_date")
                if raw_date
                else datetime.now(UTC)
            )
            try:
                hypothesis = engine.retrieve_and_answer(
                    context_id=f"longmemeval:{qid}",
                    question=str(inst.get("question", "")),
                    question_date=qdate,
                )
            except Exception as exc:
                hypothesis = f"ERROR: {type(exc).__name__}: {exc}"
                print(f"  [{i}/{total}] {qid[:34]} FAILED: {exc}", file=sys.stderr)
            out.write(json.dumps({"question_id": qid, "hypothesis": hypothesis}) + "\n")
            out.flush()
            print(f"[{i}/{total}] {qid[:34]:34s} -> {hypothesis[:70]!r}")

    print(f"\ndone in {time.perf_counter() - started:.0f}s -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
