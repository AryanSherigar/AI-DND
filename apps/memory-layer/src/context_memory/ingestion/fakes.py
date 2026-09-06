"""Deterministic fakes for unit tests; no provider, database, or graph calls."""

import re
from collections.abc import Mapping, Sequence
from hashlib import sha256

from context_memory.core.enums import IngestionJobState, is_legal_job_transition
from context_memory.core.errors import GraphPayloadConflictError, IllegalJobTransitionError, ImmutableRecordConflictError
from context_memory.core.graph import GraphNode, GraphWritePlan
from context_memory.core.models import Chunk, ContextRecord, Embedding, ExtractionDraft, IngestionJob
from context_memory.core.resolution import EntityProfile, FactState, TemporalRelation


class DeterministicExtractor:
    extractor_name = "deterministic-fixture"
    extractor_version = "v1"

    def __init__(self, candidates_by_record: Mapping[str, Sequence[ExtractionDraft]] | None = None) -> None:
        self._candidates_by_record = dict(candidates_by_record or {})

    def extract(self, record: ContextRecord) -> tuple[ExtractionDraft, ...]:
        return tuple(self._candidates_by_record.get(record.record_id, ()))


class DeterministicEmbedder:
    def __init__(self, dimensions: int = 8) -> None:
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")
        self.dimensions = dimensions

    def embed(self, text: str) -> tuple[float, ...]:
        digest = sha256(text.encode("utf-8")).digest()
        return tuple(byte / 255.0 for byte in digest[: self.dimensions])


class InMemoryChunkStore:
    def __init__(self) -> None:
        self._chunks: dict[str, Chunk] = {}

    def put(self, chunk: Chunk) -> Chunk:
        existing = self._chunks.get(chunk.chunk_id)
        if existing is not None and existing != chunk:
            raise ImmutableRecordConflictError(f"chunk_id {chunk.chunk_id} has different immutable content")
        self._chunks[chunk.chunk_id] = chunk
        return chunk

    def get(self, context_id: str, chunk_id: str) -> Chunk | None:
        chunk = self._chunks.get(chunk_id)
        return chunk if chunk is not None and chunk.context_id == context_id else None


class InMemoryJobStore:
    """Deterministic stand-in for `PostgresJobStore`, same transition rules."""

    def __init__(self) -> None:
        self._jobs: dict[str, IngestionJob] = {}

    def seed(self, chunk_id: str, context_id: str, state: IngestionJobState = IngestionJobState.PENDING_GRAPH) -> IngestionJob:
        """Create the initial job row (mirrors PostgresChunkStore.put's same-transaction insert)."""
        job = IngestionJob(job_id=f"job:{chunk_id}", chunk_id=chunk_id, context_id=context_id, state=state)
        self._jobs[chunk_id] = job
        return job

    def get(self, chunk_id: str) -> IngestionJob | None:
        return self._jobs.get(chunk_id)

    def transition(self, chunk_id: str, new_state: IngestionJobState, *, error: str | None = None) -> IngestionJob:
        job = self._jobs.get(chunk_id)
        if job is None:
            raise IllegalJobTransitionError(f"no ingestion job for chunk_id {chunk_id}")
        if not is_legal_job_transition(job.state, new_state, job.last_verified_state):
            raise IllegalJobTransitionError(f"chunk {chunk_id}: {job.state.value} -> {new_state.value} is not a legal transition")
        next_attempt_count = job.attempt_count + 1 if new_state == IngestionJobState.RETRYABLE_FAILED else job.attempt_count
        terminal_ish = (IngestionJobState.RETRYABLE_FAILED, IngestionJobState.TERMINAL_FAILED, IngestionJobState.MANUAL_REPAIR)
        next_last_verified = job.state if job.state not in terminal_ish else job.last_verified_state
        updated = IngestionJob(
            job_id=job.job_id, chunk_id=chunk_id, context_id=job.context_id, state=new_state,
            attempt_count=next_attempt_count, last_verified_state=next_last_verified, last_error=error,
        )
        self._jobs[chunk_id] = updated
        return updated


class InMemoryEmbeddingStore:
    def __init__(self) -> None:
        self._rows: dict[tuple[str, str, str, str, str], Embedding] = {}

    def put(self, embedding: Embedding) -> Embedding:
        key = (embedding.context_id, embedding.subject_kind, embedding.subject_id, embedding.model_name, embedding.model_version)
        existing = self._rows.get(key)
        if existing is not None and existing.embedded_content_hash != embedding.embedded_content_hash:
            raise ImmutableRecordConflictError(f"embedding {key} has a different embedded_content_hash")
        self._rows[key] = embedding
        return embedding

    def put_batch(self, embeddings: Sequence[Embedding]) -> list[Embedding]:
        """Same semantics as `put()` in a loop -- this fake has no round
        trips to save, it exists so orchestrator-level tests can exercise
        the batched call path (`getattr(store, "put_batch", None)`) instead
        of always falling back to the per-item loop."""
        return [self.put(embedding) for embedding in embeddings]

    def contains(self, context_id: str, subject_kind: str, subject_id: str) -> bool:
        return any(
            k[0] == context_id and k[1] == subject_kind and k[2] == subject_id for k in self._rows
        )

    def deactivate(self, context_id: str, subject_kind: str, subject_id: str) -> None:
        for key, embedding in list(self._rows.items()):
            if key[0] == context_id and key[1] == subject_kind and key[2] == subject_id:
                self._rows[key] = Embedding(
                    context_id=embedding.context_id, subject_kind=embedding.subject_kind,
                    subject_id=embedding.subject_id, source_chunk_id=embedding.source_chunk_id,
                    model_name=embedding.model_name, model_version=embedding.model_version,
                    values=embedding.values, embedded_content_hash=embedding.embedded_content_hash,
                    is_active=False,
                )


class InMemorySearchIndexStore:
    def __init__(self) -> None:
        self._rows: dict[str, str] = {}  # fact_id -> raw_text
        # Kept separate from `_rows` so existing tests indexing `_rows`
        # directly by fact_id (its established shape) are unaffected.
        self._context_by_fact: dict[str, str] = {}

    def put(self, context_id: str, fact_id: str, raw_text: str) -> None:
        self._rows[fact_id] = raw_text
        self._context_by_fact[fact_id] = context_id

    def put_batch(self, items: Sequence[tuple[str, str, str]]) -> None:
        """See `InMemoryEmbeddingStore.put_batch`."""
        for context_id, fact_id, raw_text in items:
            self.put(context_id=context_id, fact_id=fact_id, raw_text=raw_text)

    def contains(self, context_id: str, fact_id: str) -> bool:
        return fact_id in self._rows and self._context_by_fact.get(fact_id) == context_id


class InMemoryGraphIdAllocator:
    def __init__(self) -> None:
        self._ids: dict[tuple[str, str, str], int] = {}

    def allocate_graph_id(self, node_kind: str, context_id: str, logical_key: str) -> int:
        key = (node_kind, context_id, logical_key)
        if key not in self._ids:
            self._ids[key] = len(self._ids)
        return self._ids[key]


class DeterministicEntityResolutionModel:
    """Fixture-only bounded selection. Never calls a provider."""

    def __init__(self, selections: Mapping[str, int | None] | None = None) -> None:
        self._selections = dict(selections or {})
        self.calls: list[tuple[str, str, tuple[int, ...]]] = []

    def resolve_entity(self, *, context_id: str, surface: str, candidates: Sequence[EntityProfile]) -> int | None:
        self.calls.append((context_id, surface, tuple(profile.graph_id for profile in candidates)))
        return self._selections.get(surface)


class DeterministicTemporalUpdateModel:
    """Fixture-only update judgment keyed by new/prior fact IDs."""

    def __init__(self, relations: Mapping[tuple[str, str], TemporalRelation] | None = None) -> None:
        self._relations = dict(relations or {})
        self.calls: list[tuple[str, str]] = []

    def classify_update(self, *, new_fact: FactState, prior_fact: FactState) -> TemporalRelation:
        key = (new_fact.fact_id, prior_fact.fact_id)
        self.calls.append(key)
        return self._relations.get(key, TemporalRelation.UNRESOLVED)


class InMemoryGraphManifestStore:
    """Mirrors `PostgresGraphManifestStore`'s NODE_MUTABLE_PROPERTIES allowance
    (see that class's docstring, ADR-030) -- a later plan re-registering the
    same node's superseded_at/valid_to/is_current is a legitimate bitemporal
    update, not a payload conflict. Anything else differing is still a hard
    conflict."""

    NODE_MUTABLE_PROPERTIES = frozenset({"is_current", "superseded_at", "valid_to"})

    def __init__(self) -> None:
        self._records: dict[tuple[str, str, str], tuple[int, dict[str, object]]] = {}

    def register(self, plan: GraphWritePlan) -> None:
        for record in plan.records():
            kind = "node" if isinstance(record, GraphNode) else "relationship"
            key = (kind, plan.context_id, record.logical_key)
            properties = dict(record.properties)
            existing = self._records.get(key)
            if existing is None:
                self._records[key] = (record.graph_id, properties)
                continue
            existing_graph_id, existing_properties = existing
            if existing_graph_id == record.graph_id and existing_properties == properties:
                continue
            if kind == "node" and existing_graph_id == record.graph_id:
                merged = dict(existing_properties)
                conflict = False
                for prop_key, value in properties.items():
                    if prop_key in merged and merged[prop_key] != value and prop_key not in self.NODE_MUTABLE_PROPERTIES:
                        conflict = True
                        break
                    merged[prop_key] = value
                if not conflict:
                    self._records[key] = (record.graph_id, merged)
                    continue
            raise GraphPayloadConflictError(f"{kind} {record.logical_key} has a different immutable graph payload")


class InMemoryBatchStore:
    """Deterministic stand-in for `persistence.postgres.PostgresBatchStore`
    (§3 fix) -- no real per-chunk job-state derivation (that's
    `PostgresBatchStore.get_status`'s join against `ingestion_jobs`/
    `extraction_attempts`, exercised against a real database in
    `test_postgres_persistence.py`). This fake only needs to prove
    `MemoryEngine`'s own fallback wiring: an unknown batch_id reports
    "unknown" (`get_status`/`get_context_batch` both return `None`), and a
    known one's submitted payload/run_error round-trip correctly -- what
    `MemoryEngine.get_batch_status`/`retry_batch` actually branch on when
    the batch isn't in this process's own `_batches` cache."""

    def __init__(self) -> None:
        self._entries: dict[str, dict[str, object]] = {}

    def create(self, batch, chunk_ids) -> None:
        self._entries.setdefault(batch.ingestion_id, {"batch": batch, "chunk_ids": list(chunk_ids), "run_error": None})

    def get_context_batch(self, batch_id: str):
        entry = self._entries.get(batch_id)
        return entry["batch"] if entry else None

    def mark_run_error(self, batch_id: str, error: str) -> None:
        entry = self._entries.get(batch_id)
        if entry is not None:
            entry["run_error"] = error

    def clear_run_error(self, batch_id: str) -> None:
        entry = self._entries.get(batch_id)
        if entry is not None:
            entry["run_error"] = None

    def get_status(self, batch_id: str):
        from context_memory.ingestion.batch_models import BatchStatus

        entry = self._entries.get(batch_id)
        if entry is None:
            return None
        if entry["run_error"] is not None:
            return BatchStatus(batch_id=batch_id, status="failed", facts_created=0, error=entry["run_error"], retryable=True)
        return BatchStatus(batch_id=batch_id, status="pending", facts_created=0, retryable=False)


class RecordingGraphTransport:
    """`read_rows`, when explicitly set, always wins (a test hand-scripting
    a specific response). Otherwise, §8 fix: a `GraphWriter.verify()`-shaped
    bulk label read (`MATCH (n:{label} {context_id: $context_id}) RETURN
    n.id AS id`) is answered from what `write()` actually recorded, instead
    of always coming back empty -- every orchestrator test using this fake
    now exercises real write-then-verify round-tripping, not a query that
    was structurally guaranteed to report everything missing."""

    _WRITE_LABEL_PATTERN = re.compile(r"SET n:(\w+)")
    _VERIFY_READ_PATTERN = re.compile(r"MATCH \(n:(\w+) \{context_id: \$context_id\}\)")

    def __init__(self) -> None:
        self.writes: list[tuple[str, list[dict[str, object]], str]] = []
        self.reads: list[tuple[str, dict[str, object], str | None]] = []
        self.read_rows: list[dict[str, object]] = []

    def write(self, cypher: str, rows: Sequence[dict[str, object]], idempotency_key: str) -> str:
        self.writes.append((cypher, list(rows), idempotency_key))
        return f"bookmark-{len(self.writes)}"

    def read(self, cypher: str, parameters: dict[str, object], bookmark: str | None) -> Sequence[dict[str, object]]:
        self.reads.append((cypher, parameters, bookmark))
        if self.read_rows:
            return self.read_rows
        match = self._VERIFY_READ_PATTERN.search(cypher)
        if match is None:
            return []
        label = match.group(1)
        context_id = (parameters or {}).get("context_id")
        ids: set[object] = set()
        for write_cypher, write_rows, _ in self.writes:
            label_match = self._WRITE_LABEL_PATTERN.search(write_cypher)
            if label_match is None or label_match.group(1) != label:
                continue
            for row in write_rows:
                if row.get("context_id") == context_id and "id" in row:
                    ids.add(row["id"])
        return [{"id": node_id} for node_id in ids]
