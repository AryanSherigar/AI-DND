"""Rewrites a question into decomposed queries + synonyms, cached on disk.

Bare `§N` references below are sections of docs/fixes_and_evaluation_findings.md.
"""

from __future__ import annotations

import fcntl
import json
import os
import uuid
from collections.abc import MutableMapping
from pathlib import Path

from context_memory.core.config import Config
from context_memory.core.llm_client import LLMClient
from context_memory.core.logging import get_logger, timed_operation
from context_memory.retrieval.models import QueryRewriterOutput

logger = get_logger(__name__)


class JsonFileRewriteCache(MutableMapping):
    """Rewrite cache persisted to JSON, so determinism survives across processes.

    An in-process dict only stabilises repeat asks within one run; two benchmark
    processes still diverge. Writes are atomic (temp file + rename) because a run
    can be killed mid-flush.
    """

    def __init__(self, path: str) -> None:
        self._path = Path(path)
        self._lock_path = self._path.with_suffix(self._path.suffix + ".lock")
        self._data: dict[str, QueryRewriterOutput] = {}
        if self._path.exists():
            try:
                raw = json.loads(self._path.read_text())
                self._data = {k: QueryRewriterOutput(**v) for k, v in raw.items()}
            except Exception as error:
                logger.warning("rewrite cache unreadable, starting empty: %s", error)

    def _read_disk_data(self) -> dict[str, QueryRewriterOutput]:
        if not self._path.exists():
            return {}
        try:
            raw = json.loads(self._path.read_text())
            return {k: QueryRewriterOutput(**v) for k, v in raw.items()}
        except Exception as error:
            logger.warning("rewrite cache unreadable during flush: %s", error)
            return {}

    def _write_merged(self, merged: dict[str, QueryRewriterOutput]) -> None:
        # HIGH-06 fix: a unique-per-writer tmp name -- shared static ".tmp"
        # let concurrent workers clobber each other's in-flight write.
        unique_suffix = f"{self._path.suffix}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
        tmp = self._path.with_suffix(unique_suffix)
        tmp.write_text(json.dumps({k: v.model_dump() for k, v in merged.items()}))
        tmp.replace(self._path)

    def _flush(self) -> None:
        # HIGH-06 fix: flock serializes concurrent workers so a whole-file
        # overwrite here can't silently lose another worker's already-
        # persisted keys (re-read-and-merge under the lock, not blind
        # overwrite from this process's possibly-stale in-memory `_data`).
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._lock_path, "a") as lock_file:
                fcntl.flock(lock_file, fcntl.LOCK_EX)
                merged = {**self._read_disk_data(), **self._data}
                self._write_merged(merged)
                self._data = merged
        except Exception as error:
            logger.warning("rewrite cache write failed: %s", error)

    def __getitem__(self, key: str) -> QueryRewriterOutput:
        return self._data[key]

    def __setitem__(self, key: str, value: QueryRewriterOutput) -> None:
        self._data[key] = value
        self._flush()

    def __delitem__(self, key: str) -> None:
        del self._data[key]
        self._flush()

    def __iter__(self):
        return iter(self._data)

    def __len__(self) -> int:
        return len(self._data)


class QueryRewriter:
    """Rewrites a question into decomposed queries + synonyms.

    Cached because this call is not reproducible: measured 3 distinct outputs in 5
    calls at temperature 0 (§9). The rewriter runs on a reasoning model whose hidden
    chain is sampled, and this endpoint ignores `seed` (system_fingerprint is null),
    so determinism has to come from caching rather than from the provider. Different
    synonym sets change BM25 hits, which changes the retrieved facts and the answer.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        config: Config | None = None,
        cache: MutableMapping[str, QueryRewriterOutput] | None = None,
    ) -> None:
        self._llm = llm_client
        self._config = config or Config()
        self._cache = cache

    def rewrite(self, question: str) -> QueryRewriterOutput:
        if self._cache is not None:
            cached = self._cache.get(question)
            if cached is not None:
                return cached
        result = self._rewrite_uncached(question)
        if self._cache is not None:
            self._cache[question] = result
        return result

    def _rewrite_uncached(self, question: str) -> QueryRewriterOutput:
        with timed_operation(
            logger, "retrieval.phase0.query_rewriter", {"question_len": len(question)}
        ) as ctx:
            try:
                response = self._llm.structured_completion(
                    self._config.query_rewriter_system_prompt,
                    question,
                    QueryRewriterOutput,
                    temperature=self._config.llm_temperature,
                    max_tokens=self._config.query_rewriter_max_tokens,
                    timeout=self._config.query_rewriter_timeout_seconds,
                    max_retries=self._config.llm_structured_retry_attempts,
                )
                if isinstance(response, QueryRewriterOutput):
                    ctx["decomposed_count"] = len(response.decomposed_queries)
                    ctx["synonyms_count"] = len(response.synonyms)
                    return response
            except Exception as e:
                logger.warning("Query rewriter error: %s", e)
            return QueryRewriterOutput(decomposed_queries=[question], synonyms=[])
