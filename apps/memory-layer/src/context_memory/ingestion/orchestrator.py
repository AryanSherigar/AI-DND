"""Milestone 8: chains extraction -> resolution -> graph write -> embeddings per chunk,
driving the job state machine from `docs/decisions.md` ADR-031.

Scope, stated plainly rather than overclaimed: this gives *safe replay of the
whole chunk pipeline*, not fine-grained per-stage resumption. Calling
`run_chunk` again after a `retryable_failed` result re-runs extraction,
resolution, graph-plan construction, the graph write, and embedding
persistence from the top — every one of those stages was already built to be
an idempotent no-op on unchanged replay (`ExtractionService`'s stable
`attempt_id`, `PostgresGraphManifestStore`, `PostgresEmbeddingStore`,
`GraphWriter`'s `MERGE` identities), so redoing the whole chunk is correct,
just not free. There is no port to re-derive "what candidates did we already
accept" from storage alone (`ExtractionStore`/`EmbeddingStore` are write/audit
paths, not read-back paths) — building that is future work if per-stage
resumption is ever needed. This matches ADR-007's framing ("replay instead of
claimed atomicity"), not a stronger guarantee than that.

Verification before `completed` always re-reads the immutable chunk. Production
adapters additionally implement the optional `Verifiable*` ports, so the
orchestrator independently confirms the planned HydraDB nodes plus the presence
of an embedding and search row for every fact. Graph relationships are not read
back. Custom/fake stores without those capabilities degrade to chunk-only
verification; the guarantee is explicit at the adapter boundary.

Bare `§N` references below are sections of docs/fixes_and_evaluation_findings.md.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from hashlib import sha256

from context_memory.core.enums import IngestionJobState
from context_memory.core.errors import (
    ContractValidationError,
    GraphPayloadConflictError,
    ImmutableRecordConflictError,
)
from context_memory.core.graph import GraphNode, GraphWritePlan
from context_memory.core.logging import get_logger, timed_operation
from context_memory.core.models import Chunk, ContextBatch, ContextRecord, Embedding
from context_memory.core.validation import chunk_from_record
from context_memory.ingestion.extraction import ExtractionResult, ExtractionService
from context_memory.ingestion.graph_plan_builder import (
    FindExistingFacts,
    GraphPlanBuilder,
    ResolveEntity,
    ResolveManyEntities,
)
from context_memory.ingestion.graph_writer import GraphWriter
from context_memory.ingestion.ports import (
    BatchEmbedder,
    BatchEmbeddingStore,
    BatchSearchIndexStore,
    ChunkStore,
    DeactivatableEmbeddingStore,
    DeactivatableSearchIndexStore,
    Embedder,
    EmbeddingStore,
    JobStore,
    SearchIndexStore,
    TemporalUpdateClassifierPort,
    VerifiableEmbeddingStore,
    VerifiableGraphWriter,
    VerifiableSearchIndexStore,
)

logger = get_logger(__name__)

_OPEN_SENTINEL = (
    9999999999  # matches graph_plan_builder.py's and rollback.py's sentinel
)

# Errors that mean the payload/policy itself is invalid; retrying unchanged input cannot help.
_TERMINAL_ERROR_TYPES = (
    ContractValidationError,
    ImmutableRecordConflictError,
    GraphPayloadConflictError,
)

# AI-DND memory-layer contract: sources whose content is narrative game
# prose rather than chat dialogue, routed to `narrative_extraction_service`
# (a separately-prompted ExtractionService, see composition.py) instead of
# the default chat/LongMemEval-tuned one. `scenario_template` (newbie-mode
# creator lore) is included on the same reasoning as `turn_batch` -- both are
# narrative-shaped prose -- though only `turn_batch` has been independently
# verified against real event-phrased content; narrow this set if that
# extrapolation should be descoped later.
_NARRATIVE_SOURCE_TYPES = frozenset({"turn_batch", "scenario_template"})


@dataclass(frozen=True)
class ChunkRunResult:
    chunk_id: str
    state: IngestionJobState
    accepted_fact_count: int = 0
    error: str | None = None


@dataclass(frozen=True)
class BatchRunResult:
    context_id: str
    results: tuple[ChunkRunResult, ...]

    @property
    def completed_count(self) -> int:
        return sum(1 for r in self.results if r.state == IngestionJobState.COMPLETED)


class IngestionOrchestrator:
    def __init__(
        self,
        *,
        chunk_store: ChunkStore,
        job_store: JobStore,
        extraction_service: ExtractionService,
        graph_plan_builder: GraphPlanBuilder,
        graph_writer: GraphWriter,
        resolve_entity: ResolveEntity,
        embedder: Embedder,
        embedding_store: EmbeddingStore,
        search_index_store: SearchIndexStore,
        update_classifier: TemporalUpdateClassifierPort | None = None,
        find_existing_facts: FindExistingFacts | None = None,
        write_batch_size: int = 1,
        resolve_many: ResolveManyEntities | None = None,
        narrative_extraction_service: ExtractionService | None = None,
    ) -> None:
        self._chunk_store = chunk_store
        self._job_store = job_store
        self._extraction_service = extraction_service
        # AI-DND memory-layer contract: optional narrative-prompted sibling,
        # dispatched by `batch.source.source_type` in `_extraction_service_for`
        # below. None (every existing caller/test) preserves the exact prior
        # behavior of always using `extraction_service`.
        self._narrative_extraction_service = narrative_extraction_service
        self._graph_plan_builder = graph_plan_builder
        self._graph_writer = graph_writer
        self._resolve_entity = resolve_entity
        # Optional -- parallelizes entity-resolution LLM calls within a
        # chunk when supplied (EntityRegistry.resolve_many); every existing
        # caller that doesn't pass this keeps the exact per-mention
        # behavior graph_plan_builder.build() always had. See
        # docs/fixes_and_evaluation_findings.md §4.7.
        self._resolve_many = resolve_many
        self._embedder = embedder
        self._embedding_store = embedding_store
        self._search_index_store = search_index_store
        self._update_classifier = update_classifier
        self._find_existing_facts = find_existing_facts
        # See Config.ingestion_write_batch_size's field comment. 1 (the
        # default here) reproduces the original per-chunk behavior exactly;
        # real callers that want the batched path pass a larger value
        # explicitly (both `benchmark_runner.create_pipeline` and
        # `api/routes.get_engine` do).
        self._write_batch_size = max(1, write_batch_size)

    def run_batch(self, batch: ContextBatch) -> BatchRunResult:
        with timed_operation(
            logger,
            "orchestrator.run_batch",
            {
                "batch_id": batch.ingestion_id,
                "context_id": batch.context_id,
                "records": len(batch.records),
                "write_batch_size": self._write_batch_size,
            },
        ) as ctx:
            records = list(batch.records)
            results: list[ChunkRunResult] = []
            for start in range(0, len(records), self._write_batch_size):
                results.extend(
                    self._run_group(
                        batch, records[start : start + self._write_batch_size]
                    )
                )
            completed = sum(
                1 for r in results if r.state == IngestionJobState.COMPLETED
            )
            ctx["completed_count"] = completed
            return BatchRunResult(context_id=batch.context_id, results=tuple(results))

    def _run_group(
        self, batch: ContextBatch, records: list[ContextRecord]
    ) -> list[ChunkRunResult]:
        """Processes a group of records with the graph write and the
        embedding/search-index write batched across the whole group, instead
        of one write call per chunk (see `Config.ingestion_write_batch_size`
        and `GraphWriter.write_many`). A group of 1 -- the default, and what
        every single-turn caller like `MemoryEngine.add_turn_async` always
        gets -- degrades to exactly `run_record`'s original per-chunk path,
        unchanged.

        Extraction, graph-plan building (entity resolution + `SUPERSEDES`
        lookup), verification, and job-state transitions all stay per-chunk:
        none of those were the measured bottleneck (see
        docs/fixes_and_evaluation_findings.md §3.1), and keeping them
        per-chunk means one chunk's extraction or verification failure never
        blocks its group-mates. Only the graph write and the embedding/
        search-index write -- the two stages actually measured as
        round-trip-count-bound -- are merged across the group.
        """
        if len(records) <= 1:
            return [self.run_record(batch, record) for record in records]

        with timed_operation(
            logger,
            "orchestrator.run_group",
            {
                "batch_id": batch.ingestion_id,
                "context_id": batch.context_id,
                "group_size": len(records),
            },
        ) as group_ctx:
            results: dict[str, ChunkRunResult] = {}
            order: list[str] = []
            pending: list[tuple[Chunk, ExtractionResult, GraphWritePlan]] = []

            for record in records:
                chunk = chunk_from_record(batch, record)
                self._chunk_store.put(chunk)
                order.append(chunk.chunk_id)
                job = self._job_store.get(chunk.chunk_id)
                if job is None:
                    job = self._job_store.seed(chunk.chunk_id, chunk.context_id)
                current_state = job.state

                skipped = self._skip_result(chunk.chunk_id, current_state)
                if skipped is not None:
                    results[chunk.chunk_id] = skipped
                    continue

                try:
                    extraction, plan = self._extract_and_plan(batch, record, chunk)
                except Exception as error:
                    results[chunk.chunk_id] = self._record_failure(
                        chunk.chunk_id, error
                    )
                    continue

                pending.append((chunk, extraction, plan))

            if pending:
                try:
                    with timed_operation(
                        logger,
                        "orchestrator.stage.graph_write_batched",
                        {"chunk_count": len(pending)},
                    ):
                        self._graph_writer.write_many([p[2] for p in pending])
                        for chunk, *_ in pending:
                            self._job_store.transition(
                                chunk.chunk_id, IngestionJobState.PENDING_EMBEDDINGS
                            )
                except Exception as error:
                    self._fail_pending(pending, error, results)
                    pending = []

            if pending:
                try:
                    with timed_operation(
                        logger,
                        "orchestrator.stage.embeddings_and_search_index",
                        {
                            "chunk_count": len(pending),
                            "facts_to_embed": sum(len(p[1].accepted) for p in pending),
                        },
                    ):
                        units = [
                            (chunk, extraction) for chunk, extraction, _ in pending
                        ]

                        with timed_operation(
                            logger,
                            "orchestrator.stage.embedding_model",
                            {"chunk_count": len(pending)},
                        ):
                            all_embeddings = self._build_embeddings(units)

                        with timed_operation(
                            logger,
                            "orchestrator.stage.embedding_persistence",
                            {"chunk_count": len(pending)},
                        ):
                            self._persist_embeddings_and_index(all_embeddings, units)

                        for chunk, *_ in pending:
                            self._job_store.transition(
                                chunk.chunk_id, IngestionJobState.VERIFYING
                            )
                except Exception as error:
                    self._compensate_pending(pending)
                    self._fail_pending(pending, error, results)
                    pending = []

            # Per-chunk from here: verification and completion stay isolated
            # so one chunk's failure never blocks its group-mates, and this
            # part was never the measured bottleneck (§3.1) so there's
            # nothing to gain by batching it too.
            for chunk, extraction, plan in pending:
                try:
                    with timed_operation(
                        logger,
                        "orchestrator.stage.verification",
                        {"chunk_id": chunk.chunk_id},
                    ):
                        self._verify(chunk, plan, extraction)
                    self._job_store.transition(
                        chunk.chunk_id, IngestionJobState.COMPLETED
                    )
                    results[chunk.chunk_id] = ChunkRunResult(
                        chunk.chunk_id,
                        IngestionJobState.COMPLETED,
                        accepted_fact_count=len(extraction.accepted),
                    )
                except Exception as error:
                    self._compensate_chunk(chunk, extraction, plan)
                    results[chunk.chunk_id] = self._record_failure(
                        chunk.chunk_id, error
                    )

            group_ctx["completed_count"] = sum(
                1 for cid in order if results[cid].state == IngestionJobState.COMPLETED
            )
            return [results[cid] for cid in order]

    def _extraction_service_for(self, source_type: str) -> ExtractionService:
        """AI-DND memory-layer contract: narrative sources get the
        narrative-tuned extractor when one was supplied; every other source
        (chat, longmemeval, an omitted narrative service) keeps the default."""
        if (
            self._narrative_extraction_service is not None
            and source_type in _NARRATIVE_SOURCE_TYPES
        ):
            return self._narrative_extraction_service
        return self._extraction_service

    def _extract_and_plan(
        self, batch: ContextBatch, record: ContextRecord, chunk: Chunk
    ) -> tuple[ExtractionResult, GraphWritePlan]:
        with timed_operation(
            logger, "orchestrator.stage.extraction", {"chunk_id": chunk.chunk_id}
        ) as stage_ctx:
            extraction_service = self._extraction_service_for(batch.source.source_type)
            extraction = extraction_service.extract(batch, record, chunk)
            stage_ctx["accepted_facts"] = len(extraction.accepted)
            stage_ctx["rejected_facts"] = len(extraction.rejected)

        with timed_operation(
            logger, "orchestrator.stage.graph_plan", {"chunk_id": chunk.chunk_id}
        ) as stage_ctx:
            plan = self._graph_plan_builder.build(
                chunk,
                extraction,
                self._resolve_entity,
                update_classifier=self._update_classifier,
                find_existing_facts=self._find_existing_facts,
                resolve_many=self._resolve_many,
            )
            stage_ctx["nodes_count"] = len(plan.nodes)
            stage_ctx["edges_count"] = len(plan.relationships)
        return extraction, plan

    def _build_embeddings(
        self, units: list[tuple[Chunk, ExtractionResult]]
    ) -> list[Embedding]:
        """Embeds every accepted candidate across `units` in one model call when the
        embedder supports batching (~4.6x measured on SentenceTransformerEmbedder;
        fixed per-call overhead dominates a model this small)."""
        candidates = [
            (chunk, cand) for chunk, extraction in units for cand in extraction.accepted
        ]
        if not candidates:
            return []
        texts = [cand.text for _, cand in candidates]
        if isinstance(self._embedder, BatchEmbedder):
            vectors = self._embedder.embed_batch(texts)
        else:
            vectors = [self._embedder.embed(t) for t in texts]
        return [
            Embedding(
                context_id=chunk.context_id,
                subject_kind="fact",
                subject_id=cand.candidate_id,
                source_chunk_id=chunk.chunk_id,
                model_name=getattr(self._embedder, "model_name", "unknown"),
                model_version=getattr(self._embedder, "model_version", "1"),
                values=vector,
                embedded_content_hash=f"sha256:{sha256(cand.text.encode('utf-8')).hexdigest()}",
            )
            for (chunk, cand), vector in zip(candidates, vectors)
        ]

    def _persist_embeddings_and_index(
        self, embeddings: list[Embedding], units: list[tuple[Chunk, ExtractionResult]]
    ) -> None:
        """Batched when the stores support it -- collapses N sequential
        SELECT-FOR-UPDATE+INSERT round trips into one existence check plus one
        multi-row INSERT. Both stores are Protocols, so this falls back to the
        per-item loop for implementations without `put_batch` (fakes, etc.)."""
        if isinstance(self._embedding_store, BatchEmbeddingStore):
            if embeddings:
                self._embedding_store.put_batch(embeddings)
        else:
            for embedding in embeddings:
                self._embedding_store.put(embedding)

        rows = [
            (chunk.context_id, cand.candidate_id, cand.text)
            for chunk, extraction in units
            for cand in extraction.accepted
        ]
        if isinstance(self._search_index_store, BatchSearchIndexStore):
            if rows:
                self._search_index_store.put_batch(rows)
        else:
            for context_id, fact_id, raw_text in rows:
                self._search_index_store.put(
                    context_id=context_id, fact_id=fact_id, raw_text=raw_text
                )

    def _verify(
        self, chunk: Chunk, plan: GraphWritePlan, extraction: ExtractionResult
    ) -> None:
        """§8 fix: the chunk re-read below is same-process evidence only, as
        it always was -- but when the configured graph_writer/embedding_store/
        search_index_store support it (the `Verifiable*` ports, isinstance-
        gated the same way `Batch*` capabilities already are in this
        module), this now ALSO independently confirms the graph write is
        actually readable back from HydraDB, and every accepted fact has a
        real embedding row and search-index row -- not just that no write
        call happened to raise. A store that doesn't implement the
        `Verifiable*` capability is simply not checked (graceful
        degradation, not a hidden requirement), same as `Batch*` support
        already degrades to a per-item loop when absent."""
        verified_chunk = self._chunk_store.get(chunk.context_id, chunk.chunk_id)
        if verified_chunk is None or verified_chunk.content_hash != chunk.content_hash:
            raise RuntimeError(
                f"post-write verification failed for chunk {chunk.chunk_id}"
            )

        if isinstance(
            self._graph_writer, VerifiableGraphWriter
        ) and not self._graph_writer.verify(plan):
            raise RuntimeError(
                f"graph verification failed for chunk {chunk.chunk_id}: plan {plan.plan_key} not fully readable"
            )

        if isinstance(self._embedding_store, VerifiableEmbeddingStore):
            for candidate in extraction.accepted:
                if not self._embedding_store.contains(
                    chunk.context_id, "fact", candidate.candidate_id
                ):
                    raise RuntimeError(
                        f"embedding verification failed for chunk {chunk.chunk_id}: "
                        f"fact {candidate.candidate_id} missing"
                    )

        if isinstance(self._search_index_store, VerifiableSearchIndexStore):
            for candidate in extraction.accepted:
                if not self._search_index_store.contains(
                    chunk.context_id, candidate.candidate_id
                ):
                    raise RuntimeError(
                        f"search index verification failed for chunk {chunk.chunk_id}: "
                        f"fact {candidate.candidate_id} missing"
                    )

    def _record_failure(self, chunk_id: str, error: Exception) -> ChunkRunResult:
        if isinstance(error, _TERMINAL_ERROR_TYPES):
            logger.error(
                "Terminal error processing chunk %s: %s", chunk_id, error, exc_info=True
            )
            state = IngestionJobState.TERMINAL_FAILED
        else:
            # transient/unclassified: safe to retry (idempotent stages, see module docstring)
            logger.warning(
                "Retryable error processing chunk %s: %s",
                chunk_id,
                error,
                exc_info=True,
            )
            state = IngestionJobState.RETRYABLE_FAILED
        self._safe_transition(chunk_id, state, str(error))
        return ChunkRunResult(chunk_id, state, error=str(error))

    def _skip_result(
        self, chunk_id: str, current_state: IngestionJobState
    ) -> ChunkRunResult | None:
        if current_state == IngestionJobState.COMPLETED:
            logger.debug("Chunk %s already in COMPLETED state; skipping.", chunk_id)
            return ChunkRunResult(chunk_id, IngestionJobState.COMPLETED)
        if current_state in (
            IngestionJobState.TERMINAL_FAILED,
            IngestionJobState.MANUAL_REPAIR,
        ):
            logger.warning(
                "Chunk %s is in %s state; skipping auto-retry.",
                chunk_id,
                current_state.value,
            )
            return ChunkRunResult(
                chunk_id,
                current_state,
                error="blocked: requires manual repair, not auto-retried",
            )
        return None

    def _fail_pending(
        self,
        pending: list[tuple[Chunk, ExtractionResult, GraphWritePlan]],
        error: Exception,
        results: dict[str, ChunkRunResult],
    ) -> list[str]:
        """A batched call (graph write or embedding write) covering the
        whole group failed -- since it's one physical call per bucket now,
        not one per chunk, there's no way to tell which chunk's rows were
        responsible. Marks every chunk still `pending` with the same
        classification `run_chunk` would give a solo failure at this stage,
        consistent with this module's documented scope: replay redoes the
        whole chunk pipeline, extended here to "redo the whole group" when a
        group failed together, not a stronger per-row guarantee."""
        terminal = isinstance(error, _TERMINAL_ERROR_TYPES)
        state = (
            IngestionJobState.TERMINAL_FAILED
            if terminal
            else IngestionJobState.RETRYABLE_FAILED
        )
        log = logger.error if terminal else logger.warning
        chunk_ids = [chunk.chunk_id for chunk, *_ in pending]
        log(
            "%s error in batched write for group (%d chunks): %s",
            "Terminal" if terminal else "Retryable",
            len(chunk_ids),
            error,
            exc_info=True,
        )
        for chunk_id in chunk_ids:
            self._safe_transition(chunk_id, state, str(error))
            results[chunk_id] = ChunkRunResult(chunk_id, state, error=str(error))
        return chunk_ids

    def run_record(self, batch: ContextBatch, record: ContextRecord) -> ChunkRunResult:
        chunk = chunk_from_record(batch, record)
        self._chunk_store.put(chunk)
        job = self._job_store.get(chunk.chunk_id)
        if job is None:
            job = self._job_store.seed(chunk.chunk_id, chunk.context_id)
        return self.run_chunk(batch, record, chunk, job.state)

    def run_chunk(
        self,
        batch: ContextBatch,
        record: ContextRecord,
        chunk: Chunk,
        current_state: IngestionJobState,
    ) -> ChunkRunResult:
        skipped = self._skip_result(chunk.chunk_id, current_state)
        if skipped is not None:
            return skipped

        with timed_operation(
            logger,
            "orchestrator.run_chunk",
            {"chunk_id": chunk.chunk_id, "context_id": chunk.context_id},
        ) as chunk_ctx:
            extraction: ExtractionResult | None = None
            plan: GraphWritePlan | None = None
            is_graph_written = False
            try:
                extraction, plan = self._extract_and_plan(batch, record, chunk)
                with timed_operation(
                    logger,
                    "orchestrator.stage.graph_write",
                    {"chunk_id": chunk.chunk_id},
                ):
                    self._graph_writer.write(plan)
                    is_graph_written = True
                    self._job_store.transition(
                        chunk.chunk_id, IngestionJobState.PENDING_EMBEDDINGS
                    )

                self._persist_and_verify(chunk, extraction, plan)
                self._job_store.transition(chunk.chunk_id, IngestionJobState.COMPLETED)
                chunk_ctx["final_state"] = IngestionJobState.COMPLETED.value
                chunk_ctx["accepted_facts"] = len(extraction.accepted)
                return ChunkRunResult(
                    chunk.chunk_id,
                    IngestionJobState.COMPLETED,
                    accepted_fact_count=len(extraction.accepted),
                )
            except Exception as error:
                if is_graph_written and extraction is not None and plan is not None:
                    self._compensate_chunk(chunk, extraction, plan)
                result = self._record_failure(chunk.chunk_id, error)
                chunk_ctx["final_state"] = result.state.value
                return result

    def _persist_and_verify(
        self, chunk: Chunk, extraction: ExtractionResult, plan: GraphWritePlan
    ) -> None:
        units = [(chunk, extraction)]
        with timed_operation(
            logger,
            "orchestrator.stage.embeddings_and_search_index",
            {"chunk_id": chunk.chunk_id, "facts_to_embed": len(extraction.accepted)},
        ):
            with timed_operation(
                logger,
                "orchestrator.stage.embedding_model",
                {"chunk_id": chunk.chunk_id},
            ):
                embeddings = self._build_embeddings(units)
            with timed_operation(
                logger,
                "orchestrator.stage.embedding_persistence",
                {"chunk_id": chunk.chunk_id},
            ):
                self._persist_embeddings_and_index(embeddings, units)
            self._job_store.transition(chunk.chunk_id, IngestionJobState.VERIFYING)

        with timed_operation(
            logger, "orchestrator.stage.verification", {"chunk_id": chunk.chunk_id}
        ):
            self._verify(chunk, plan, extraction)

    def _build_compensating_nodes(
        self, plan: GraphWritePlan, extraction: ExtractionResult
    ) -> list[GraphNode]:
        accepted_cand_keys = {
            f"fact:{cand.candidate_id}" for cand in extraction.accepted
        }
        compensating: list[GraphNode] = []
        for node in plan.nodes:
            if node.label != "Fact":
                continue
            is_new_fact = node.logical_key in accepted_cand_keys
            properties = self._compensating_fact_properties(
                plan.context_id, node.logical_key, is_new_fact
            )
            compensating.append(
                GraphNode(node.graph_id, "Fact", node.logical_key, properties)
            )
        return compensating

    @staticmethod
    def _compensating_fact_properties(
        context_id: str, logical_key: str, is_new_fact: bool
    ) -> dict[str, object]:
        if is_new_fact:
            return {
                "context_id": context_id,
                "logical_key": logical_key,
                "is_current": False,
                "archived": True,
            }
        return {
            "context_id": context_id,
            "logical_key": logical_key,
            "is_current": True,
            "superseded_at": _OPEN_SENTINEL,
            "valid_to": _OPEN_SENTINEL,
        }

    def _compensate_plan(
        self, plan: GraphWritePlan, extraction: ExtractionResult
    ) -> None:
        nodes = self._build_compensating_nodes(plan, extraction)
        if not nodes:
            return
        plan_key = f"compensate:{plan.plan_key}:{uuid.uuid4().hex[:8]}"
        compensating_plan = GraphWritePlan(plan.context_id, plan_key, tuple(nodes), ())
        self._graph_writer.write(compensating_plan)

    def _deactivate_downstream(
        self, chunk: Chunk, extraction: ExtractionResult
    ) -> None:
        candidate_ids = [cand.candidate_id for cand in extraction.accepted]
        self._deactivate_embeddings(chunk.context_id, candidate_ids)
        self._deactivate_search_index(chunk.context_id, candidate_ids)

    def _deactivate_embeddings(self, context_id: str, candidate_ids: list[str]) -> None:
        has_deactivate = isinstance(
            self._embedding_store, DeactivatableEmbeddingStore
        ) or hasattr(self._embedding_store, "deactivate")
        if not has_deactivate:
            return
        for candidate_id in candidate_ids:
            try:
                self._embedding_store.deactivate(context_id, "fact", candidate_id)
            except Exception as error:
                logger.warning(
                    "Failed to deactivate embedding for %s: %s", candidate_id, error
                )

    def _deactivate_search_index(
        self, context_id: str, candidate_ids: list[str]
    ) -> None:
        has_deactivate = isinstance(
            self._search_index_store, DeactivatableSearchIndexStore
        ) or hasattr(self._search_index_store, "deactivate")
        if not has_deactivate:
            return
        for candidate_id in candidate_ids:
            try:
                self._search_index_store.deactivate(context_id, candidate_id)
            except Exception as error:
                logger.warning(
                    "Failed to deactivate search index for %s: %s", candidate_id, error
                )

    def _compensate_chunk(
        self, chunk: Chunk, extraction: ExtractionResult, plan: GraphWritePlan
    ) -> None:
        try:
            self._compensate_plan(plan, extraction)
            self._deactivate_downstream(chunk, extraction)
        except Exception as comp_error:
            logger.exception(
                "RECONCILIATION REQUIRED: failed to compensate graph write for chunk %s: %s",
                chunk.chunk_id,
                comp_error,
            )

    def _compensate_pending(
        self, pending: list[tuple[Chunk, ExtractionResult, GraphWritePlan]]
    ) -> None:
        for chunk, extraction, plan in pending:
            self._compensate_chunk(chunk, extraction, plan)

    def _safe_transition(
        self, chunk_id: str, state: IngestionJobState, error: str
    ) -> None:
        try:
            self._job_store.transition(chunk_id, state, error=error)
        except Exception as transition_error:
            # §8 fix: was a bare `except Exception: pass` -- a job that
            # couldn't even record its own failure state used to vanish
            # without a trace anywhere. Still swallowed (not re-raised: the
            # ORIGINAL `error` being recorded via this call is what the
            # caller needs to see, and this method's whole contract is
            # "never let a bookkeeping failure mask the real one"), but now
            # logged loudly as an explicit reconciliation signal instead of
            # silently -- an operator can grep for this instead of a job
            # being invisibly stuck.
            logger.error(
                "RECONCILIATION REQUIRED: failed to transition chunk %s to %s (original error: %s): %s",
                chunk_id,
                state.value,
                error,
                transition_error,
                exc_info=True,
            )
