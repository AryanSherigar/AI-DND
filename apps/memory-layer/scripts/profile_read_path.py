"""Per-stage latency profile of the retrieval read path.

Splits wall-clock into LLM vs mechanical time so latency work targets the real
bottleneck. Baseline at time of writing: 10.2s/query total, 4.5s LLM,
5.7s mechanical -- of which `hydradb.read` alone was 134 calls / 2.7s per query.

Usage:
    set -a && source src/.env && set +a
    PYTHONPATH=src .venv/bin/python3 scripts/profile_read_path.py \
        --instances benchmarks/longmemeval/sample30.json --limit 8
"""

from __future__ import annotations

import argparse
import collections
import json
import os
import sys
import time
from datetime import UTC, datetime

sys.path.insert(0, "src")

import psycopg

from context_memory.client.hydradb_http import HydraHttpTransport
from context_memory.core.config import Config
from context_memory.core.logging import drain_metrics, enable_metrics_collection
from context_memory.ingestion.embedding import VertexEmbedder
from context_memory.ingestion.sources.longmemeval import parse_longmemeval_timestamp
from evaluation.benchmark_runner import create_pipeline


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--instances", required=True)
    ap.add_argument("--limit", type=int, default=8)
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

    instances = json.load(open(args.instances))[: args.limit]

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

    enable_metrics_collection()
    wall: list[float] = []
    for inst in instances:
        raw_date = inst.get("question_date")
        qdate = (
            parse_longmemeval_timestamp(raw_date, "question_date")
            if raw_date
            else datetime.now(UTC)
        )
        started = time.perf_counter()
        try:
            engine.retrieve_and_answer(
                f"longmemeval:{inst['question_id']}",
                str(inst.get("question", "")),
                qdate,
            )
        except Exception as exc:
            print(f"  {inst['question_id'][:34]} FAILED: {exc}", file=sys.stderr)
            continue
        wall.append(time.perf_counter() - started)

    agg: dict[str, list[float]] = collections.defaultdict(list)
    for rec in drain_metrics():
        if rec.get("elapsed_ms") is not None:
            agg[str(rec.get("operation", "?"))].append(rec["elapsed_ms"])

    n = max(len(wall), 1)
    print(f"\n{'operation':62s} {'calls':>6s} {'tot_ms':>9s} {'ms/query':>9s}")
    print("-" * 90)
    llm_ms = 0.0
    for op in sorted(agg, key=lambda o: -sum(agg[o])):
        total = sum(agg[op])
        if op.startswith("llm."):
            llm_ms += total
        print(f"{op[:62]:62s} {len(agg[op]):6d} {total:9.0f} {total / n:9.0f}")

    total_wall = sum(wall) * 1000
    print("-" * 90)
    print(f"{'WALL CLOCK total':62s} {n:6d} {total_wall:9.0f} {total_wall / n:9.0f}")
    print(f"{'  of which LLM calls':62s} {'':6s} {llm_ms:9.0f} {llm_ms / n:9.0f}")
    print(
        f"{'  MECHANICAL remainder':62s} {'':6s} "
        f"{total_wall - llm_ms:9.0f} {(total_wall - llm_ms) / n:9.0f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
