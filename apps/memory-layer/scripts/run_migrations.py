"""Standalone migration runner, invoked as a pre-start step (the
memory-layer-migration-runner compose service) before memory-layer's
uvicorn process starts accepting traffic.

Usage:
    PYTHONPATH=src .venv/bin/python3 scripts/run_migrations.py
"""

from __future__ import annotations

import sys

sys.path.insert(0, "src")

from context_memory.composition import run_migrations


def main() -> None:
    applied = run_migrations()
    if applied:
        print(f"Applied migrations: {', '.join(applied)}")
    else:
        print("No pending migrations.")


if __name__ == "__main__":
    main()
