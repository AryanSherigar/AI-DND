"""Structured logging and latency measurement utilities for HydraDB Context Memory Engine."""

from __future__ import annotations

import logging
import sys
import threading
import time
from contextlib import contextmanager
from typing import Any, Generator


def setup_logging(
    level: int = logging.INFO,
    format_str: str = "%(asctime)s [%(levelname)s] [%(name)s:%(lineno)d] %(message)s",
) -> None:
    """Configures application-wide structured logging."""
    logging.basicConfig(
        level=level,
        format=format_str,
        handlers=[logging.StreamHandler(sys.stdout)],
        force=True,
    )


def get_logger(name: str) -> logging.Logger:
    """Returns a logger for the given module name."""
    return logging.getLogger(name)


# -- Structured metrics collection (opt-in, off by default) ----------------
#
# `timed_operation` already logs a human-readable [START]/[DONE]/[FAIL] line
# for every stage across the whole pipeline (ingestion and retrieval both go
# through it, unchanged by anything below). That's enough to eyeball one
# run, but every performance investigation this session ended up as a
# one-off script grep-and-regexing those text lines back into numbers --
# it works, but it's fragile (a wording change breaks the regex) and only
# ever gets built reactively, after the fact, for whatever question is
# being asked that day.
#
# This adds a second sink `timed_operation` feeds in parallel: a plain list
# of dicts, one per operation, with `elapsed_ms` and whatever metadata that
# call attached -- directly machine-readable (JSONL, one real dict per
# line, no parsing) instead of needing to be reconstructed after the fact.
# Opt-in and a module-level `None` when not enabled, so every existing
# caller -- unit tests, the live API path, anything that never asks for
# this -- pays exactly one `is None` check per call and nothing else; noop
# for everyone who doesn't use it. Not thread-local: a benchmark run's
# extraction prefetch pool and the orchestrator's own write groups can both
# be mid-flight in different threads at once, so this is one process-wide
# list behind a lock, not per-thread.
_metrics_lock = threading.Lock()
_metrics_sink: list[dict[str, Any]] | None = None


def enable_metrics_collection() -> None:
    """Starts collecting a structured record for every `timed_operation`
    call process-wide, in addition to the existing text log lines. Safe to
    call again to reset -- drops whatever was collected so far, same effect
    as `drain_metrics()` without needing the return value."""
    global _metrics_sink
    with _metrics_lock:
        _metrics_sink = []


def disable_metrics_collection() -> None:
    """Stops collecting; `timed_operation` goes back to zero-overhead."""
    global _metrics_sink
    with _metrics_lock:
        _metrics_sink = None


def drain_metrics() -> list[dict[str, Any]]:
    """Returns everything collected since the last `drain_metrics()` call
    (or since `enable_metrics_collection()`, if this is the first call) and
    clears the buffer. Call this once per unit of work you want a clean
    slice for -- e.g. once per LongMemEval instance -- rather than reading
    the growing list directly and losing track of what's new."""
    global _metrics_sink
    with _metrics_lock:
        if _metrics_sink is None:
            return []
        drained, _metrics_sink = _metrics_sink, []
        return drained


def _record_metric(operation_name: str, elapsed_ms: float, outcome: str, context: dict[str, Any]) -> None:
    if _metrics_sink is None:  # unlocked fast-path check -- the overwhelmingly common case, disabled
        return
    record: dict[str, Any] = {"operation": operation_name, "elapsed_ms": round(elapsed_ms, 3), "outcome": outcome, "wall_time": time.time()}
    record.update(context)
    with _metrics_lock:
        if _metrics_sink is not None:  # re-checked under lock: could have been disabled between the fast-path check and here
            _metrics_sink.append(record)


def record_event(operation_name: str, context: dict[str, Any]) -> None:
    """Public entry point into the same metrics sink `timed_operation`
    feeds, for a call site that wants to record structured facts about
    something that isn't itself a timed span (e.g. how many candidates
    each blocking signal in entity resolution produced) -- `elapsed_ms` is
    always 0 for these, `outcome` is always "done". Same no-op-when-
    disabled contract as everything else in this module."""
    _record_metric(operation_name, 0.0, "done", context)


@contextmanager
def timed_operation(
    logger: logging.Logger,
    operation_name: str,
    extra: dict[str, Any] | None = None,
    log_level: int = logging.INFO,
) -> Generator[dict[str, Any], None, None]:
    """Context manager measuring execution latency and logging outcome with diagnostics.

    Usage:
        with timed_operation(logger, "llm_fact_extraction", {"chunk_id": chunk.chunk_id}) as ctx:
            result = do_work()
            ctx["facts_extracted"] = len(result)

    Every call here also feeds `_record_metric` (see above) -- a no-op
    unless `enable_metrics_collection()` was called, so this doesn't change
    behavior or cost for any caller that hasn't opted in.
    """
    context: dict[str, Any] = extra.copy() if extra else {}
    start_time = time.perf_counter()
    logger.log(
        log_level,
        "[START] %s | %s",
        operation_name,
        " ".join(f"{k}={v}" for k, v in context.items()) if context else "no extra metadata",
    )
    try:
        yield context
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        meta_str = f" | {' '.join(f'{k}={v}' for k, v in context.items())}" if context else ""
        logger.log(log_level, "[DONE] %s in %.2f ms%s", operation_name, elapsed_ms, meta_str)
        _record_metric(operation_name, elapsed_ms, "done", context)
    except Exception as e:
        elapsed_ms = (time.perf_counter() - start_time) * 1000.0
        meta_str = f" | {' '.join(f'{k}={v}' for k, v in context.items())}" if context else ""
        logger.exception(
            "[FAIL] %s FAILED after %.2f ms%s | error=%s: %s",
            operation_name,
            elapsed_ms,
            meta_str,
            type(e).__name__,
            str(e),
        )
        _record_metric(operation_name, elapsed_ms, "failed", {**context, "error_type": type(e).__name__, "error": str(e)})
        raise
