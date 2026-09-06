"""Harness diagnostic: "can cost be attributed per action?" (see the harness
plan's own checklist). Answers it directly from real `journal_steps` data
instead of a one-off profiling run -- every recorded LLM call, aggregated
by role, with p50/p95/mean and share of total LLM time.

This is deliberately narrower than `profile_read_path.py`: it only sees
what Phase 5 actually journals (LLM calls), not HydraDB reads or
embeddings (both explicitly deferred in Phase 5) -- so it answers "where
does LLM time go" precisely, and says nothing about mechanical/graph cost.
Use both together, not one instead of the other.

Usage:
    set -a && source src/.env && set +a
    PYTHONPATH=src .venv/bin/python3 scripts/latency_attribution.py [--since-hours N]
"""
from __future__ import annotations

import argparse
import statistics
import sys

sys.path.insert(0, "src")

import psycopg

from context_memory.core.config import Config


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--since-hours", type=float, default=24.0)
    parser.add_argument("--database-url", default=None)
    args = parser.parse_args()

    config = Config()
    conn = psycopg.connect(args.database_url or config.database_url)
    with conn.cursor() as cursor:
        cursor.execute(
            "SELECT step_type, call_role, elapsed_ms FROM journal_steps "
            "WHERE step_type LIKE 'llm.%%' AND outcome = 'ok' "
            "AND created_at > now() - (%s || ' hours')::interval",
            (args.since_hours,),
        )
        rows = cursor.fetchall()

    if not rows:
        print(f"no journal_steps rows in the last {args.since_hours}h -- nothing to attribute")
        return 1

    by_role: dict[str, list[float]] = {}
    for step_type, call_role, elapsed_ms in rows:
        key = call_role or step_type
        by_role.setdefault(key, []).append(elapsed_ms)

    total_ms = sum(v for values in by_role.values() for v in values)
    print(f"=== latency attribution (n={len(rows)} LLM calls, last {args.since_hours}h) ===\n")
    print(f"  {'role':<20} {'calls':>6} {'mean_ms':>9} {'p50_ms':>8} {'p95_ms':>8} {'share':>7}")
    for role, values in sorted(by_role.items(), key=lambda kv: -sum(kv[1])):
        values.sort()
        mean = statistics.mean(values)
        p50 = values[len(values) // 2]
        p95 = values[int(len(values) * 0.95)] if len(values) > 1 else values[0]
        share = sum(values) / total_ms
        print(f"  {role:<20} {len(values):>6} {mean:>9.0f} {p50:>8.0f} {p95:>8.0f} {share:>6.1%}")

    print(f"\n  total LLM time attributed: {total_ms / 1000:.1f}s across {len(rows)} calls")
    print("  NOTE: HydraDB reads and embeddings are not journaled (Phase 5 deferred both) --")
    print("  this table covers LLM cost only. See profile_read_path.py for the mechanical side.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
