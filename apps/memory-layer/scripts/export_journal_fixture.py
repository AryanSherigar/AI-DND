"""Phase 8: export a recorded request/turn's journal_steps rows into a
replayable fixture file. Point it at a correlation_id from a real run
(a trace, or `journal_steps` directly) -- a production behavior becomes a
deterministic, no-LLM regression test without hand-reconstructing what the
model said.

Usage:
    set -a && source src/.env && set +a
    PYTHONPATH=src .venv/bin/python3 scripts/export_journal_fixture.py \
        --correlation-id <id> --out <path.json>
"""
from __future__ import annotations

import argparse
import sys

sys.path.insert(0, "src")

import psycopg

from context_memory.core.config import Config
from context_memory.core.replay import export_journal_fixture


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--correlation-id", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    config = Config()
    connection = psycopg.connect(config.database_url, autocommit=True)
    count = export_journal_fixture(connection, correlation_id=args.correlation_id, path=args.out)
    print(f"wrote {count} step(s) to {args.out}")


if __name__ == "__main__":
    main()
