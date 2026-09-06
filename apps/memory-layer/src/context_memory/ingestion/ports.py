"""Provider and persistence boundaries. Implementations stay outside domain.

Bare `§N` references below are sections of docs/fixes_and_evaluation_findings.md.
"""

from collections.abc import Sequence
from typing import Protocol, runtime_checkable

from context_memory.core.enums import IngestionJobState
from context_memory.core.models import Chunk, ContextBatch, ContextRecord, Embedding, ExtractionDraft, IngestionJob
from context_memory.core.resolution import EntityProfile, FactState, TemporalRelation, TemporalUpdateDecision
from context_memory.core.graph import GraphWritePlan
from context_memory.core.ports import Embedder, GraphTransport
from context_memory.ingestion.batch_models import BatchStatus

__all__ = [
    "Extractor", "Embedder", "BatchEmbedder", "ChunkStore", "JobStore",
    "EmbeddingStore", "BatchEmbeddingStore", "ExtractionStore",
    "SearchIndexStore", "BatchSearchIndexStore", "GraphIdAllocator",
    "EntityResolutionModel", "BatchEntityResolutionModel",
    "TemporalUpdateModel", "BatchTemporalUpdateModel", "GraphManifestStore",
    "GraphTransport", "EntityNameIndex", "TemporalUpdateClassifierPort",
    "BatchTemporalUpdateClassifierPort", "BatchStore",
    "VerifiableEmbeddingStore", "VerifiableSearchIndexStore", "VerifiableGraphWriter",
    "CopyableEmbeddingStore",
]

# `Protocol` can't express "this method is optional" on a single class --
# these pair a base capability with an extended one, checked via
# `isinstance(obj, Batch*)` (requires @runtime_checkable) rather than a
# string-typed `hasattr` probe. Same runtime behavior, real typing.


@runtime_checkable
class BatchEmbedder(Embedder, Protocol):
    def embed_batch(self, texts: Sequence[str]) -> Sequence[tuple[float, ...]]: ...


class Extractor(Protocol):
    """Returns candidates without writing graph or SQL state."""

    def extract(self, record: ContextRecord) -> Sequence[ExtractionDraft]: ...


class ChunkStore(Protocol):
    """Future SQL-backed immutable chunk store."""

    def put(self, chunk: Chunk) -> Chunk: ...

    def get(self, context_id: str, chunk_id: str) -> Chunk | None: ...


class JobStore(Protocol):
    """Milestone 8 recovery state machine (docs/decisions.md ADR-031)."""

    def get(self, chunk_id: str) -> IngestionJob | None: ...

    def seed(self, chunk_id: str, context_id: str) -> IngestionJob:
        """Idempotent: `PostgresChunkStore.put` already inserts this row in the same
        transaction as the chunk (ADR-014); this is a defensive fallback for callers
        (or fakes) whose chunk store doesn't create the job row itself."""
        ...

    def transition(
        self, chunk_id: str, new_state: IngestionJobState, *, error: str | None = None
    ) -> IngestionJob: ...


class BatchStore(Protocol):
    """§3 fix: durable batch tracking for Milestone 2's async ingest
    (`PostgresBatchStore` in production, `InMemoryBatchStore` in tests --
    both in their respective modules). `MemoryEngine` falls back to this
    only when a batch_id isn't in its own same-process `_batches` cache
    (a different replica, or this process restarted) -- see
    `MemoryEngine.get_batch_status`/`retry_batch`."""

    def create(self, batch: ContextBatch, chunk_ids: Sequence[tuple[str, int | None]]) -> None: ...

    def get_context_batch(self, batch_id: str) -> ContextBatch | None: ...

    def mark_run_error(self, batch_id: str, error: str) -> None: ...

    def clear_run_error(self, batch_id: str) -> None: ...

    def get_status(self, batch_id: str) -> BatchStatus | None: ...


class EmbeddingStore(Protocol):
    """PostgreSQL/pgvector-backed versioned embedding persistence (Milestone 7)."""

    def put(self, embedding: Embedding) -> Embedding: ...

    def deactivate(self, context_id: str, subject_kind: str, subject_id: str) -> None: ...


@runtime_checkable
class BatchEmbeddingStore(EmbeddingStore, Protocol):
    def put_batch(self, embeddings: Sequence[Embedding]) -> list[Embedding]: ...


@runtime_checkable
class VerifiableEmbeddingStore(EmbeddingStore, Protocol):
    """§8 fix: opt-in independent existence check for completion
    verification (orchestrator._verify) -- gated the same isinstance way
    `BatchEmbeddingStore` already is, so an implementation that doesn't
    support it (most test fakes) simply isn't checked, same as
    `put_batch`'s absence today falls back to the per-item loop."""

    def contains(self, context_id: str, subject_kind: str, subject_id: str) -> bool: ...


@runtime_checkable
class CopyableEmbeddingStore(EmbeddingStore, Protocol):
    """mem1 gap #46 fix: opt-in read-back of an already-computed vector for
    an exact (model_name, model_version) match -- used by
    `ingestion.fact_projection.FactProjectionWriter.project_copy` to reuse a
    vector when cloning a fact into a new context instead of re-embedding
    identical text on every clone. Same isinstance-gated pattern as
    `VerifiableEmbeddingStore`/`BatchEmbeddingStore`: a store that doesn't
    support it (most test fakes) is simply never asked, and `project_copy`
    falls back to embedding fresh, same as it already does for a fact with no
    prior projection at all."""

    def get_active(
        self, context_id: str, subject_kind: str, subject_id: str, model_name: str, model_version: str
    ) -> tuple[float, ...] | None: ...


class ExtractionStore(Protocol):
    """Append-only audit trail for deterministic extraction baseline output."""

    def record(
        self,
        *,
        attempt_id: str,
        chunk: Chunk,
        extractor_name: str,
        extractor_version: str,
        accepted: Sequence[object],
        rejected: Sequence[object],
    ) -> None: ...


class SearchIndexStore(Protocol):
    """PostgreSQL-backed full-text search index for BM25 keyword retrieval."""

    def put(self, context_id: str, fact_id: str, raw_text: str) -> None: ...


@runtime_checkable
class BatchSearchIndexStore(SearchIndexStore, Protocol):
    def put_batch(self, items: Sequence[tuple[str, str, str]]) -> None: ...


@runtime_checkable
class VerifiableSearchIndexStore(SearchIndexStore, Protocol):
    """§8 fix: see `VerifiableEmbeddingStore` -- same opt-in pattern."""

    def contains(self, context_id: str, fact_id: str) -> bool: ...


@runtime_checkable
class VerifiableGraphWriter(Protocol):
    """§8 fix: opt-in independent post-write confirmation for a
    `GraphWritePlan` -- `ingestion.graph_writer.GraphWriter` implements
    this; gated the same isinstance way as the other `Verifiable*` ports so
    a test double that doesn't need real verification never has to."""

    def verify(self, plan: GraphWritePlan) -> bool: ...


class GraphIdAllocator(Protocol):
    """Stable graph IDs are allocated in PostgreSQL before HydraDB writes."""

    def allocate_graph_id(self, node_kind: str, context_id: str, logical_key: str) -> int: ...


class EntityResolutionModel(Protocol):
    """Bounded LLM judgment over application-supplied candidate entities."""

    def resolve_entity(
        self, *, context_id: str, surface: str, candidates: Sequence[EntityProfile]
    ) -> int | None: ...


@runtime_checkable
class BatchEntityResolutionModel(EntityResolutionModel, Protocol):
    """One call for several mentions (§14) instead of the per-mention path."""

    def resolve_entities(
        self, *, context_id: str, mentions: Sequence[tuple[str, Sequence[EntityProfile]]]
    ) -> dict[int, int | None]: ...


class TemporalUpdateModel(Protocol):
    """LLM classification after deterministic subject/predicate gating."""

    def classify_update(self, *, new_fact: FactState, prior_fact: FactState) -> TemporalRelation: ...


@runtime_checkable
class BatchTemporalUpdateModel(TemporalUpdateModel, Protocol):
    """One call for all priors (§8) instead of the pairwise path."""

    def classify_updates(
        self, *, new_fact: FactState, prior_facts: Sequence[FactState]
    ) -> dict[int, TemporalRelation]: ...


class GraphManifestStore(Protocol):
    """Durable immutable-payload guard before non-atomic graph writes."""

    def register(self, plan: GraphWritePlan) -> None: ...


class TemporalUpdateClassifierPort(Protocol):
    """Post-gating decision over one new/prior fact pair -- distinct from
    `TemporalUpdateModel`, which is just the LLM call this wraps."""

    def classify(self, *, new_fact: FactState, prior_fact: FactState) -> TemporalUpdateDecision: ...


@runtime_checkable
class BatchTemporalUpdateClassifierPort(TemporalUpdateClassifierPort, Protocol):
    def classify_many(
        self, *, new_fact: FactState, prior_facts: Sequence[FactState]
    ) -> list[TemporalUpdateDecision]: ...


class EntityNameIndex(Protocol):
    """Semantic candidate-name blocking for entity resolution (Tier 3)."""

    def add(self, entity_id: str, name: str, entity_type: str, haystack_id: str) -> None: ...

    def find_candidates(
        self, query_name: str, entity_type: str, haystack_id: str, top_k: int = 5, threshold: float = 0.75,
    ) -> Sequence[dict[str, object]]: ...
