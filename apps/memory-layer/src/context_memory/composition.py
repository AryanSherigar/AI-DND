"""Shared object-graph wiring for `IngestionOrchestrator` + `HybridRetrievalEngine`.

`api/routes.py::get_engine` and `evaluation/benchmark_runner.py::create_pipeline`
built the same ~15 objects independently and had already drifted twice (missing
role-specific clients for entity resolution, then temporal resolver/query rewriter,
then rerank -- each found only by manual comparison). This is the one place that
wiring happens now; both callers delegate to it.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import psycopg
from psycopg_pool import ConnectionPool

from context_memory.client.hydradb_http import HydraHttpTransport
from context_memory.core.config import Config
from context_memory.core.journal import JournaledLLMClient, StepJournal
from context_memory.core.llm_client import LLMClient
from context_memory.core.tracing import configure_tracing
from context_memory.engine import MemoryEngine
from context_memory.ingestion.embedding import SentenceTransformerEmbedder
from context_memory.ingestion.entity_name_index import EntityNameIndex
from context_memory.ingestion.entity_registry import EntityRegistry
from context_memory.ingestion.extraction import ExtractionService
from context_memory.ingestion.fact_lookup import HydraFactLookup
from context_memory.ingestion.fact_projection import FactProjectionWriter
from context_memory.ingestion.graph_plan_builder import GraphPlanBuilder
from context_memory.ingestion.graph_writer import GraphWriter
from context_memory.ingestion.model_adapters import (
    LLMEntityResolutionModel,
    LLMExtractor,
    LLMTemporalUpdateModel,
)
from context_memory.ingestion.orchestrator import IngestionOrchestrator
from context_memory.ingestion.ports import Extractor
from context_memory.ingestion.rollback import RollbackService, SavePointStore
from context_memory.ingestion.temporal_update import TemporalUpdateClassifier
from context_memory.persistence.migrations import apply_migrations
from context_memory.persistence.postgres import (
    PostgresChunkStore,
    PostgresEmbeddingStore,
    PostgresExtractionStore,
    PostgresGraphManifestStore,
    PostgresJobStore,
    PostgresSearchIndexStore,
)
from context_memory.retrieval import HybridRetrievalEngine


def _journaled(
    client: LLMClient, journal: StepJournal | None, call_role: str
) -> LLMClient:
    """`JournaledLLMClient` is duck-typed to the same two-method shape as
    `LLMClient` -- wrapping is a no-op when `journal` is None, so every call
    site below reads the same whether journaling is on or off."""
    return (
        JournaledLLMClient(client, journal, call_role)
        if journal is not None
        else client
    )  # type: ignore[return-value]


def build_ingestion_and_retrieval(
    *,
    pool: Any,
    hydra_transport: Any,
    embedder: Any,
    config: Config,
    reader_llm_client: LLMClient,
    extractor: Extractor | None = None,
    extraction_store: Any | None = None,
    journal: StepJournal | None = None,
) -> tuple[IngestionOrchestrator, HybridRetrievalEngine, Extractor]:
    """`reader_llm_client` is explicit, not defaulted, because the two callers
    currently pass different clients there and unifying that choice is a
    separate, measured decision -- not something to fold silently into a
    dedup pass. Returns `(orchestrator, retrieval_engine, extractor)`; the
    extractor is returned so a caller wanting `PrefetchingExtractor` can wrap
    it before use. `journal`, when given, wraps every LLM client constructed
    or received here (Phase 5's step journal) -- the one composition root is
    exactly where this belongs, since it's the only place any of these
    clients is ever built."""
    chunk_store = PostgresChunkStore(pool)
    job_store = PostgresJobStore(pool)
    manifest_store = PostgresGraphManifestStore(pool)
    embedding_store = PostgresEmbeddingStore(pool)
    search_index_store = PostgresSearchIndexStore(pool)
    ext_store = extraction_store or PostgresExtractionStore(pool)

    if extractor is None:
        extractor = LLMExtractor(
            _journaled(config.get_extractor_client(), journal, "extractor"), config
        )
    extraction_service = ExtractionService(extractor, ext_store)

    # AI-DND memory-layer contract: a second, narrative-prompted extractor
    # pair, dispatched by source_type inside IngestionOrchestrator (see
    # `_extraction_service_for`). Only differs from the pair above in which
    # prompt fields `narrative_config` carries -- same client role, same
    # audit store, so a narrative-sourced attempt shows up in the same
    # extraction_attempts trail as any other. Building this unconditionally
    # (rather than only when a narrative source is expected) costs nothing:
    # `evaluation/benchmark_runner.py` also calls this function, and its
    # batches are always tagged "longmemeval", which the orchestrator's
    # dispatch never selects this extractor for.
    narrative_config = replace(
        config,
        fact_extraction_system_prompt=config.narrative_fact_extraction_system_prompt,
        batched_fact_extraction_system_prompt=config.batched_narrative_fact_extraction_system_prompt,
    )
    narrative_extractor = LLMExtractor(
        _journaled(config.get_extractor_client(), journal, "extractor"),
        narrative_config,
    )
    narrative_extraction_service = ExtractionService(narrative_extractor, ext_store)

    entity_resolution_model = LLMEntityResolutionModel(
        _journaled(config.get_entity_resolution_client(), journal, "entity_resolution"),
        config,
    )
    # `EntityNameIndex.find_candidates` and `EntityRegistry.resolve` both
    # filter on `context_id`, so sharing this index across every request in
    # this process's lifetime is safe -- different contexts never see each
    # other's candidates. See docs/fixes_and_evaluation_findings.md §4.
    entity_name_index = EntityNameIndex()
    entity_registry = EntityRegistry(
        allocator=chunk_store,
        name_index=entity_name_index,
        model=entity_resolution_model,
        batch_enabled=config.entity_resolution_batch_enabled,
    )
    plan_builder = GraphPlanBuilder(allocator=chunk_store)
    graph_writer = GraphWriter(manifest_store=manifest_store, transport=hydra_transport)

    temporal_model = LLMTemporalUpdateModel(
        _journaled(config.get_temporal_update_client(), journal, "temporal_update"),
        config,
    )
    update_classifier = TemporalUpdateClassifier(
        temporal_model,
        batch_enabled=config.temporal_update_batch_enabled,
        embedder=embedder,
        similarity_threshold=config.temporal_update_similarity_threshold,
    )
    fact_lookup = HydraFactLookup(hydra_transport)

    orchestrator = IngestionOrchestrator(
        chunk_store=chunk_store,
        job_store=job_store,
        extraction_service=extraction_service,
        graph_plan_builder=plan_builder,
        graph_writer=graph_writer,
        resolve_entity=entity_registry.resolve_entity,
        resolve_many=entity_registry.resolve_many,
        embedder=embedder,
        embedding_store=embedding_store,
        search_index_store=search_index_store,
        update_classifier=update_classifier,
        find_existing_facts=fact_lookup.find_existing,
        write_batch_size=config.ingestion_write_batch_size,
        narrative_extraction_service=narrative_extraction_service,
    )

    retrieval_engine = HybridRetrievalEngine(
        llm_client=_journaled(reader_llm_client, journal, "reader"),
        embedder=embedder,
        pool=pool,
        hydra_client=hydra_transport,
        config=config,
        temporal_resolver_client=_journaled(
            config.get_temporal_resolver_client(), journal, "temporal_resolver"
        ),
        query_rewriter_client=_journaled(
            config.get_query_rewriter_client(), journal, "query_rewriter"
        ),
        rerank_client=_journaled(config.get_rerank_client(), journal, "rerank"),
    )

    return orchestrator, retrieval_engine, extractor


def run_migrations(config: Config | None = None) -> tuple[str, ...]:
    """Standalone migration entry point for scripts/run_migrations.py, run by
    the memory-layer-migration-runner compose service before memory-layer
    starts -- kept out of build_memory_engine() so the engine factory never
    touches migrations."""
    config = config or Config()
    migrations_dir = Path(__file__).resolve().parents[2] / "db" / "migrations"
    if not migrations_dir.exists():
        return ()
    with psycopg.connect(config.database_url, autocommit=True) as conn:
        return apply_migrations(conn, migrations_dir)


def build_memory_engine(config: Config | None = None) -> MemoryEngine:
    """Connects to the real Postgres/HydraDB instances named by `config` and
    returns a fully-wired `MemoryEngine`. The one place a caller that just
    wants a working engine (an API server, a CLI tool, a benchmark script)
    should look, instead of reimplementing connection setup +
    `build_ingestion_and_retrieval`. Does not run migrations -- see
    `run_migrations`."""
    config = config or Config()
    # Phase 7: no-op unless OTEL_EXPORTER_OTLP_ENDPOINT (or _TRACES_ENDPOINT) is
    # set -- the standard OTel env vars, not a mem1-specific one, so this is
    # "point it at any OTLP backend," not "wire up our own config surface."
    configure_tracing()

    hydra_url = config.hydradb_url
    if not hydra_url.startswith("http://") and not hydra_url.startswith("https://"):
        hydra_url = f"http://{hydra_url}"

    pool = ConnectionPool(
        config.database_url,
        min_size=config.postgres_pool_min_size,
        max_size=config.postgres_pool_max_size,
        timeout=config.postgres_pool_timeout_seconds,
        kwargs={"autocommit": True},
        open=True,
    )
    pool.wait(timeout=config.postgres_pool_timeout_seconds)

    hydra_transport = HydraHttpTransport(
        base_url=hydra_url,
        bearer_token=config.hydradb_token or None,
        database=config.hydradb_database,
        timeout_seconds=config.hydradb_request_timeout_seconds,
    )
    embedder = SentenceTransformerEmbedder(model_name=config.embedding_model_name)
    # StepJournal keeps its own dedicated, non-pooled connection -- it
    # already serializes access with its own internal lock (a different
    # concurrency shape than the pool's per-call acquisition), so folding it
    # into the shared pool would add nothing and would complicate its
    # single-connection design for no benefit.
    journal_connection = (
        psycopg.connect(config.database_url, autocommit=True)
        if config.step_journal_enabled
        else None
    )
    journal = (
        StepJournal(journal_connection) if journal_connection is not None else None
    )

    orchestrator, retrieval_engine, _extractor = build_ingestion_and_retrieval(
        pool=pool,
        hydra_transport=hydra_transport,
        embedder=embedder,
        config=config,
        reader_llm_client=config.get_reader_client(),
        journal=journal,
    )

    # Phase 6: rollback gets its own `GraphWriter` -- `PostgresGraphManifestStore`
    # is a stateless wrapper over `pool` (no cache to duplicate), so a
    # second instance costs nothing and keeps rollback decoupled from
    # `build_ingestion_and_retrieval`'s internals rather than threading a new
    # return value through it.
    rollback_manifest_store = PostgresGraphManifestStore(pool)
    rollback_graph_writer = GraphWriter(rollback_manifest_store, hydra_transport)
    save_point_store = SavePointStore(pool)
    rollback_service = RollbackService(pool, rollback_graph_writer, journal)

    # Milestone 3 of the AI-DND bridge (direct authoring + template clone):
    # same "second instance costs nothing" reasoning as rollback's writer
    # above -- `PostgresChunkStore` doubles as the `GraphIdAllocator`
    # (graph_id_registry is its own table, independent of the chunk rows it
    # also stores), so building one here rather than threading it out of
    # `build_ingestion_and_retrieval` keeps that shared composition function
    # (also used by evaluation/benchmark_runner.py) untouched.
    authoring_allocator = PostgresChunkStore(pool)
    authoring_manifest_store = PostgresGraphManifestStore(pool)
    authoring_graph_writer = GraphWriter(authoring_manifest_store, hydra_transport)

    # mem1 gap #46 fix: same "second instance costs nothing" reasoning as
    # the writers above -- both Postgres stores are stateless wrappers over
    # `pool`. Reuses the SAME `embedder` object already built above (not a
    # second one): a second SentenceTransformer load is expensive (see
    # docs/fixes_and_evaluation_findings.md §3.1), and `authoring_allocator`
    # already doubles as the GraphIdAllocator, so it doubles again here as
    # the FactProjectionWriter's ChunkStore.
    fact_projection_writer = FactProjectionWriter(
        embedder,
        PostgresEmbeddingStore(pool),
        PostgresSearchIndexStore(pool),
        authoring_allocator,
    )

    return MemoryEngine(
        orchestrator=orchestrator,
        retrieval_engine=retrieval_engine,
        llm_client=config.get_reader_client(),
        pool=pool,
        config=config,
        journal=journal,
        save_point_store=save_point_store,
        rollback_service=rollback_service,
        graph_id_allocator=authoring_allocator,
        authoring_graph_writer=authoring_graph_writer,
        hydra_transport=hydra_transport,
        fact_projection_writer=fact_projection_writer,
    )
