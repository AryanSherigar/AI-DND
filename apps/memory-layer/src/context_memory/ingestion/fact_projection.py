"""Closes mem1 gap #46 (docs/BEGINNER_BUILD_FLOW.md §46): a fact written to
HydraDB outside the runtime-extraction pipeline -- master-mode direct
authoring (`ingestion.direct_authoring.write_fact`), or a template-to-
playthrough clone of ANY fact, extracted or authored
(`cloning.template_clone.clone`) -- was never projected into the two Postgres
tables `retrieval.seeder.CandidateSeeder.seed()` actually starts from
(`memory_embeddings`, `fact_search_index`). The fact existed in the graph;
nothing could ever find it. `FactProjectionWriter` is the one place that
companion write happens, mirroring what `ingestion.orchestrator` already does
for runtime-extracted facts -- same ports (`Embedder`, `EmbeddingStore`,
`SearchIndexStore`), same concrete Postgres stores behind them in production.

Identity convention -- read this before changing subject_id/fact_id anywhere
in this module: a projected row's subject_id/fact_id is the fact's own
`graph_id` (already a single global `IDENTITY` column in `graph_id_registry`,
so naturally unique across every context with zero schema change), NOT a
content-derived string. `retrieval.graph_expander.GraphExpander` has a
matching dispatch -- a bare-digit subject_id already IS the graph_id, no
`graph_id_registry` lookup needed -- see its own inline comment at the call
site. This matters because a content hash of (subject, predicate, object) is
NOT context-scoped: cloning one template into many playthroughs (ADR-7's
whole premise), or two unrelated scenarios that happen to author identical
content, reliably produces byte-identical hashes across different contexts,
and `fact_search_index.fact_id` is a bare, non-context-scoped `PRIMARY KEY`
(db/migrations/0001, 0005) -- reusing that hash as the row identity would
silently let one context's write overwrite another's.
"""

from __future__ import annotations

from datetime import UTC, datetime
from hashlib import sha256

from context_memory.core.models import Chunk, Embedding, SourceDescriptor
from context_memory.core.validation import chunk_id_for, content_hash
from context_memory.ingestion.ports import (
    ChunkStore,
    CopyableEmbeddingStore,
    Embedder,
    EmbeddingStore,
    SearchIndexStore,
)

# Fixed, not wall-clock: PostgresChunkStore.put() treats a chunk's whole
# content -- occurred_at included -- as immutable, and this placeholder is
# looked up (and re-inserted, as a no-op) every time a fact is authored or
# cloned under the same context_id. A wall-clock value here would make the
# SECOND call ever made for a context raise ImmutableRecordConflictError.
_PLACEHOLDER_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)
_PLACEHOLDER_RAW_TEXT = (
    "placeholder evidence chunk for a fact projected outside extraction"
)
_SUBJECT_KIND_FACT = "fact"


class FactProjectionWriter:
    """Writes the `memory_embeddings` + `fact_search_index` rows a
    direct-authored or cloned fact needs to be reachable through
    `CandidateSeeder`."""

    def __init__(
        self,
        embedder: Embedder,
        embedding_store: EmbeddingStore,
        search_index_store: SearchIndexStore,
        chunk_store: ChunkStore,
    ) -> None:
        self._embedder = embedder
        self._embedding_store = embedding_store
        self._search_index_store = search_index_store
        self._chunk_store = chunk_store

    def project(self, context_id: str, fact_graph_id: int, text: str) -> None:
        """Direct-authoring entry point (`direct_authoring.write_fact`):
        embeds `text` fresh and writes both rows under `str(fact_graph_id)`."""
        source_chunk_id = self._ensure_authoring_chunk(
            context_id, "direct_authoring", fact_graph_id
        )
        vector = self._embedder.embed(text)
        self._write(context_id, fact_graph_id, text, vector, source_chunk_id)

    def project_copy(
        self,
        source_context_id: str,
        source_subject_id: str,
        target_context_id: str,
        new_fact_graph_id: int,
        text: str,
    ) -> None:
        """Clone entry point (`cloning.template_clone.clone`): reuses the
        source fact's already-computed embedding vector when one exists under
        the CURRENT embedder's exact model/version (same text -> same vector;
        avoids a live model call for every fact in every playthrough ever
        cloned from a template), falling back to a fresh `embed()` only when
        no matching source row exists -- a template authored/cloned before
        this writer existed, or under a since-upgraded embedding model."""
        source_chunk_id = self._ensure_authoring_chunk(
            target_context_id, "template_clone", new_fact_graph_id
        )
        model_name = getattr(self._embedder, "model_name", "unknown")
        model_version = getattr(self._embedder, "model_version", "1")
        vector = None
        if isinstance(self._embedding_store, CopyableEmbeddingStore):
            vector = self._embedding_store.get_active(
                source_context_id,
                _SUBJECT_KIND_FACT,
                source_subject_id,
                model_name,
                model_version,
            )
        if vector is None:
            vector = self._embedder.embed(text)
        self._write(target_context_id, new_fact_graph_id, text, vector, source_chunk_id)

    def _write(
        self,
        context_id: str,
        fact_graph_id: int,
        text: str,
        vector: tuple[float, ...],
        source_chunk_id: str,
    ) -> None:
        subject_id = str(fact_graph_id)
        embedding = Embedding(
            context_id=context_id,
            subject_kind=_SUBJECT_KIND_FACT,
            subject_id=subject_id,
            source_chunk_id=source_chunk_id,
            model_name=getattr(self._embedder, "model_name", "unknown"),
            model_version=getattr(self._embedder, "model_version", "1"),
            values=vector,
            embedded_content_hash=f"sha256:{sha256(text.encode('utf-8')).hexdigest()}",
        )
        self._embedding_store.put(embedding)
        self._search_index_store.put(
            context_id=context_id, fact_id=subject_id, raw_text=text
        )

    def _ensure_authoring_chunk(
        self, context_id: str, source_type: str, fact_graph_id: int
    ) -> str:
        """One idempotent placeholder `evidence_chunks` row PER FACT --
        satisfies `memory_embeddings.source_chunk_id`'s `NOT NULL` FK for
        facts that never went through extraction and so have no real chunk.

        NEW-HIGH-02 fix: keyed on `fact_graph_id`, not just `context_id` --
        every authored/cloned fact previously shared one placeholder chunk
        per context, which made `SiblingExpander`'s same-chunk join treat
        every authored fact in a scenario as a sibling of every other one
        (a cross-product blowup). One fact per chunk correctly means an
        authored fact has no siblings via this join, matching reality: it
        wasn't extracted from a shared passage."""
        record_id = f"{context_id}:fact-projection-placeholder:{fact_graph_id}"
        chunk = Chunk(
            chunk_id=chunk_id_for(context_id, record_id),
            context_id=context_id,
            source=SourceDescriptor(
                source_type=source_type, source_external_id=context_id
            ),
            source_record_id=record_id,
            raw_text=_PLACEHOLDER_RAW_TEXT,
            content_hash=content_hash(_PLACEHOLDER_RAW_TEXT),
            occurred_at=_PLACEHOLDER_EPOCH,
        )
        self._chunk_store.put(chunk)
        return chunk.chunk_id
