"""Oracle retrieval eval -- LLM-free regression gate for retrieval changes.

LongMemEval ships ground-truth evidence labels (`answer_session_ids`). This scores
whether the facts that reached the reader came from those sessions, using
Recall@K / MRR / Precision@K. No judge model, so it is deterministic and runs in
seconds -- unlike the QA-accuracy harness, which needs an LLM judge (~330s) and is
nondeterministic.

Join: reader fact id -> extracted_memory_candidates.candidate_id
      -> source_record_id -> evidence_chunks.session_id -> split(':')[0]

Usage:
    set -a && source src/.env && set +a
    PYTHONPATH=src .venv/bin/python3 scripts/eval_retrieval_oracle.py \
        --instances <run30b.json> [--limit N] [--k 10]
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, "src")

import psycopg

from context_memory.client.hydradb_http import HydraHttpTransport
from context_memory.core.config import Config
from context_memory.core.journal import StepJournal
from context_memory.core.logging import drain_metrics, enable_metrics_collection
from context_memory.ingestion.embedding import SentenceTransformerEmbedder
from context_memory.ingestion.sources.longmemeval import parse_longmemeval_timestamp
from evaluation.benchmark_runner import create_pipeline

_SESSION_SQL = """
SELECT c.candidate_id, split_part(e.session_id, ':', 1)
FROM extracted_memory_candidates c
JOIN extraction_attempts a ON a.attempt_id = c.attempt_id
JOIN evidence_chunks e
  ON e.context_id = a.context_id AND e.source_record_id = c.source_record_id
WHERE a.context_id = %s
"""


def load_fact_sessions(conn, context_id: str) -> dict[str, str]:
    with conn.cursor() as cur:
        cur.execute(_SESSION_SQL, (context_id,))
        return {str(r[0]): str(r[1]) for r in cur.fetchall()}


def score(ranked_sessions: list[str], gold: set[str], k: int) -> dict[str, float]:
    """Recall@k is over gold sessions actually hit; MRR uses the first hit's rank."""
    topk = ranked_sessions[:k]
    hits = [i for i, s in enumerate(topk, start=1) if s in gold]
    found = {s for s in topk if s in gold}
    return {
        "recall_at_k": len(found) / len(gold) if gold else 0.0,
        "hit_at_k": 1.0 if found else 0.0,
        "precision_at_k": len(hits) / len(topk) if topk else 0.0,
        "mrr": 1.0 / hits[0] if hits else 0.0,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--instances", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--k", type=int, default=10)
    ap.add_argument("--database-url", default=os.getenv(
        "CONTEXT_MEMORY_DATABASE_URL",
        "postgresql://context_memory@127.0.0.1:54329/context_memory"))
    ap.add_argument("--hydradb-url", default=os.getenv(
        "CONTEXT_MEMORY_HYDRADB_URL", "http://127.0.0.1:8080"))
    args = ap.parse_args()

    instances = json.load(open(args.instances))
    if args.limit:
        instances = instances[: args.limit]

    config = Config()
    # autocommit=True, matching composition.py's own connection -- StepJournal.record's
    # `with self._connection.transaction():` becomes a SAVEPOINT (not a real commit)
    # on a connection already sitting in an open implicit transaction from an earlier,
    # untransacted query on the same connection (seeder/graph_expander's plain SELECTs
    # do exactly this), and that outer transaction only reaches disk if something later
    # explicitly commits it. Nothing here ever did -- confirmed live: journal.record()
    # was being called correctly, with distinct idempotency keys, every time, but only
    # 1-2 of a fresh 30-instance run's ~90 expected rows survived to a later, separate
    # connection's read. Non-autocommit here was always latent (every other query this
    # script issues is a read), until wiring in the journal made it a real bug.
    conn = psycopg.connect(args.database_url, autocommit=True)
    transport = HydraHttpTransport(
        base_url=args.hydradb_url,
        bearer_token=os.getenv("CONTEXT_MEMORY_HYDRADB_TOKEN"),
        timeout_seconds=config.hydradb_request_timeout_seconds,
    )
    embedder = SentenceTransformerEmbedder(model_name=config.embedding_model_name)
    journal = StepJournal(conn) if config.step_journal_enabled else None
    _, engine, _ = create_pipeline(
        conn, transport, config.get_extractor_client(), embedder, config=config, journal=journal)

    print(f"harness_config: {json.dumps(config.harness_snapshot())}")

    enable_metrics_collection()
    totals: dict[str, float] = defaultdict(float)
    by_type: dict[str, list[float]] = defaultdict(list)
    rows = []

    for i, inst in enumerate(instances, start=1):
        qid = str(inst["question_id"])
        context_id = f"longmemeval:{qid}"
        gold = {str(s) for s in inst.get("answer_session_ids", [])}
        raw_date = inst.get("question_date")
        qdate = (parse_longmemeval_timestamp(raw_date, "question_date")
                 if raw_date else datetime.now(timezone.utc))

        drain_metrics()
        try:
            engine.retrieve_and_answer(context_id, str(inst.get("question", "")), qdate)
        except Exception as exc:
            print(f"[{i}/{len(instances)}] {qid[:34]} FAILED: {exc}", file=sys.stderr)
            continue

        fact_ids: list[str] = []
        for rec in drain_metrics():
            if rec.get("reader_fact_ids"):
                fact_ids = list(rec["reader_fact_ids"])
        if not fact_ids:
            print(f"[{i}/{len(instances)}] {qid[:34]} no reader_fact_ids", file=sys.stderr)

        fact_to_session = load_fact_sessions(conn, context_id)
        # dedupe to session order-of-first-appearance; ranking is over sessions
        seen: set[str] = set()
        ranked: list[str] = []
        for fid in fact_ids:
            s = fact_to_session.get(fid)
            if s and s not in seen:
                seen.add(s)
                ranked.append(s)

        m = score(ranked, gold, args.k)
        qtype = str(inst.get("question_type", "?"))
        for key, val in m.items():
            totals[key] += val
        by_type[qtype].append(m["hit_at_k"])
        rows.append({"question_id": qid, "question_type": qtype,
                     "gold": sorted(gold), "ranked": ranked[: args.k], **m})
        print(f"[{i}/{len(instances)}] {qid[:34]:34s} hit={m['hit_at_k']:.0f} "
              f"recall={m['recall_at_k']:.2f} mrr={m['mrr']:.2f}")

    n = len(rows)
    if not n:
        print("no instances scored", file=sys.stderr)
        return 1

    # hit@k saturates at k>=2 on this sample, so the sweep is what makes the gate
    # discriminative: watch hit@1, recall@1 and MRR for regressions.
    print(f"\n=== oracle retrieval eval (n={n}) ===")
    print(f"  {'k':>3} {'hit@k':>8} {'recall@k':>9} {'prec@k':>8}")
    for k in (1, 3, 5, args.k):
        agg = [score(r["ranked"], set(r["gold"]), k) for r in rows]
        print(f"  {k:>3} {sum(a['hit_at_k'] for a in agg) / n:>8.3f} "
              f"{sum(a['recall_at_k'] for a in agg) / n:>9.3f} "
              f"{sum(a['precision_at_k'] for a in agg) / n:>8.3f}")
    print(f"\n  MRR {totals['mrr'] / n:.4f}")
    print(f"\n  by question_type (hit@{args.k}):")
    for qtype in sorted(by_type):
        vals = by_type[qtype]
        print(f"    {qtype:28s} {sum(vals) / len(vals):.2f}  (n={len(vals)})")

    out = os.path.splitext(args.instances)[0] + f".oracle-k{args.k}.json"
    with open(out, "w") as fh:
        json.dump({"k": args.k, "n": n,
                   "harness_config": config.harness_snapshot(),
                   "summary": {k: totals[k] / n for k in
                               ("hit_at_k", "recall_at_k", "precision_at_k", "mrr")},
                   "rows": rows}, fh, indent=2)
    print(f"\nwrote {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
