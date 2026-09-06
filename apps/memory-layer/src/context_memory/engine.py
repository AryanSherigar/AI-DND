from __future__ import annotations

import contextvars
from datetime import datetime, timezone
import uuid
import json

from context_memory.core.config import Config
from context_memory.core.enums import IngestionJobState
from context_memory.core.errors import BatchNotFoundError
from context_memory.core.journal import JournalContext, StepJournal, correlation_scope
from context_memory.core.logging import get_logger, timed_operation
from context_memory.core.graph import GraphNode, GraphWritePlan
from context_memory.core.models import ContextBatch, ContextRecord, SourceDescriptor
from context_memory.core.ports import GraphTransport
from context_memory.core.validation import chunk_id_for, content_hash
from context_memory.cloning.template_clone import CloneResult, clone
from context_memory.ingestion.batch_models import BatchStatus, TurnBatchEntry
from context_memory.ingestion.direct_authoring import DirectEntityInput, DirectFactInput, write_entity, write_fact
from context_memory.ingestion.fact_projection import FactProjectionWriter
from context_memory.ingestion.graph_writer import GraphWriter
from context_memory.ingestion.orchestrator import BatchRunResult, IngestionOrchestrator
from context_memory.ingestion.ports import BatchStore, GraphIdAllocator
from context_memory.persistence.postgres import (
    PostgresBatchStore,
    PostgresCheckpointStore,
    PostgresExternalFactIdStore,
    PostgresFactMetadataStore,
)
from context_memory.ingestion.rollback import RollbackResult, RollbackService, SavePoint, SavePointStore
from context_memory.ingestion.sources.chat import adapt_chat_turn
from context_memory.retrieval import HybridRetrievalEngine
from context_memory.core.llm_client import LLMClient
from concurrent.futures import ThreadPoolExecutor

logger = get_logger(__name__)


# §1/§4 fix: fixed reference epoch a synthetic per-turn `occurred_at` is
# derived from when the caller gives no real event time. Never wall-clock --
# a catch-up batch re-submitting an already-ingested turn must land on
# EXACTLY the same `occurred_at` as the first submission (same context_id +
# turn_number -> same chunk_id already; PostgresChunkStore.put treats the
# chunk's whole content, occurred_at included, as immutable) or it raises
# ImmutableRecordConflictError instead of being the idempotent no-op a
# replay should be. A pure function of turn_number is also what gives turns
# 10/11/12 in one batch distinct, correctly-ordered timestamps instead of
# the single `datetime.now()` every record in the batch used to share.
_SYNTHETIC_TURN_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _synthetic_turn_occurred_at(turn_number: int) -> datetime:
    from datetime import timedelta
    return _SYNTHETIC_TURN_EPOCH + timedelta(seconds=turn_number)


def _batch_status_from_result(batch_id: str, result: BatchRunResult) -> BatchStatus:
    """Aggregates per-chunk `ChunkRunResult`s (already computed by
    `run_batch`) into one `BatchStatus`. `IngestionJobState.MANUAL_REPAIR`
    is not currently reachable from `run_batch`'s own transitions (see
    `orchestrator.py`), so it's excluded from `_TERMINAL_STATES` below on
    purpose, not by oversight -- if a chunk ever reports that state, it falls
    into the same "not fully succeeded" bucket everything else does."""
    facts_created = sum(r.accepted_fact_count for r in result.results)
    states = {r.state for r in result.results}
    errors = [r.error for r in result.results if r.error]
    first_error = errors[0] if errors else None

    # By the time `run_batch` returns, every chunk has resolved to one of
    # COMPLETED / RETRYABLE_FAILED / TERMINAL_FAILED (`_run_group`/`run_record`
    # only ever hand back a `ChunkRunResult` after that chunk's synchronous
    # run finishes) -- PENDING_GRAPH/PENDING_EMBEDDINGS/VERIFYING are
    # mid-flight `ingestion_jobs` states, never a final `ChunkRunResult.state`.
    if states <= {IngestionJobState.COMPLETED}:
        return BatchStatus(batch_id=batch_id, status="succeeded", facts_created=facts_created, retryable=False)
    if IngestionJobState.COMPLETED in states:
        return BatchStatus(
            batch_id=batch_id, status="partial", facts_created=facts_created, error=first_error, retryable=True
        )
    if states <= {IngestionJobState.RETRYABLE_FAILED}:
        return BatchStatus(
            batch_id=batch_id, status="failed", facts_created=facts_created, error=first_error, retryable=True
        )
    return BatchStatus(
        batch_id=batch_id, status="failed", facts_created=facts_created, error=first_error, retryable=False
    )


class MemoryEngine:
    def __init__(
        self,
        orchestrator: IngestionOrchestrator,
        retrieval_engine: HybridRetrievalEngine,
        llm_client: LLMClient,
        pool: object,
        config: Config | None = None,
        journal: StepJournal | None = None,
        save_point_store: SavePointStore | None = None,
        rollback_service: RollbackService | None = None,
        graph_id_allocator: GraphIdAllocator | None = None,
        authoring_graph_writer: GraphWriter | None = None,
        hydra_transport: GraphTransport | None = None,
        fact_metadata_store: PostgresFactMetadataStore | None = None,
        checkpoint_store: PostgresCheckpointStore | None = None,
        batch_store: BatchStore | None = None,
        external_fact_id_store: PostgresExternalFactIdStore | None = None,
        fact_projection_writer: FactProjectionWriter | None = None,
    ):
        self._orchestrator = orchestrator
        self._retrieval_engine = retrieval_engine
        self._llm = llm_client
        self._pool = pool
        self._config = config or Config()
        self._journal = journal
        self._save_point_store = save_point_store or SavePointStore(pool)
        self._rollback_service = rollback_service
        # Milestone 3 of the AI-DND bridge (direct authoring + template
        # clone): optional, like `rollback_service` above -- callers that
        # never author master-mode scenarios or clone templates (most
        # existing tests) don't need to wire these.
        self._graph_id_allocator = graph_id_allocator
        self._authoring_graph_writer = authoring_graph_writer
        self._hydra_transport = hydra_transport
        # Milestones 4-5: default built off `pool`, same
        # override-or-default pattern `save_point_store` already uses above.
        self._fact_metadata_store = fact_metadata_store or PostgresFactMetadataStore(pool)
        self._checkpoint_store = checkpoint_store or PostgresCheckpointStore(pool)
        # AI-DND memory-layer contract: `superseded_fact_id` on a
        # direct-authored fact, same override-or-default pattern as above.
        self._external_fact_id_store = external_fact_id_store or PostgresExternalFactIdStore(pool)
        self._batch_store = batch_store or PostgresBatchStore(pool)
        # mem1 gap #46 fix: unlike the stores above, deliberately NOT
        # default-constructed here -- it needs the same `Embedder` instance
        # the orchestrator uses (a second SentenceTransformer load is
        # expensive, see docs/fixes_and_evaluation_findings.md §3.1), which
        # this class has no access to build on its own. None (every caller
        # that never authors master-mode scenarios or clones templates, most
        # existing tests) means write_template_fact/clone_playthrough_space
        # simply skip the projection step, same as the other optional
        # authoring deps above when unset.
        self._fact_projection_writer = fact_projection_writer
        self._executor = ThreadPoolExecutor(max_workers=self._config.ingestion_executor_max_workers)
        # Milestone 2 of the AI-DND bridge: batch_id -> {"batch", "chunk_ids",
        # "result", "error"}. Same-process fast-path cache only -- doesn't
        # survive a restart or reach a different replica, same as before.
        # §3 fix: `self._batch_store` (PostgresBatchStore by default) is now
        # the durable source of truth underneath this -- `get_batch_status`/
        # `retry_batch` fall back to it whenever a batch_id isn't in this
        # dict, instead of the old "unknown -> pending forever" behavior.
        # This cache still exists because it's strictly cheaper for the
        # overwhelmingly common case (poll a batch this same process just
        # submitted) -- no reason to pay a Postgres round trip for that.
        self._batches: dict[str, dict[str, object]] = {}

    def create_save_point(self, context_id: str, session_id: str | None = None, label: str | None = None) -> SavePoint:
        return self._save_point_store.create(context_id, session_id, label)

    def rollback_to(self, save_id: str) -> RollbackResult:
        if self._rollback_service is None:
            raise RuntimeError("rollback_to called without a RollbackService configured")
        save_point = self._save_point_store.get(save_id)
        if save_point is None:
            raise ValueError(f"unknown save_id: {save_id}")
        with correlation_scope(JournalContext(context_id=save_point.context_id, session_id=save_point.session_id)):
            return self._rollback_service.rollback_to(save_point)

    def add_turn_async(
        self, context_id: str, session_id: str, role: str, content: str, timestamp: datetime,
        scenario_id: str | None = None,
    ) -> None:
        with correlation_scope(JournalContext(context_id=context_id, session_id=session_id, scenario_id=scenario_id)), timed_operation(
            logger, "memory_engine.add_turn_async", {"context_id": context_id, "session_id": session_id, "role": role}
        ) as ctx:
            # 1. Record to conversation buffer
            with self._pool.connection() as conn:
                with conn.cursor() as cursor:
                    cursor.execute(
                        "SELECT COALESCE(MAX(turn_index), -1) + 1 FROM conversation_buffer WHERE context_id = %s AND session_id = %s",
                        (context_id, session_id)
                    )
                    turn_index = cursor.fetchone()[0]

                    cursor.execute(
                        """
                        INSERT INTO conversation_buffer (context_id, session_id, turn_index, role, content, created_at)
                        VALUES (%s, %s, %s, %s, %s, %s)
                        """,
                        (context_id, session_id, turn_index, role, content, timestamp)
                    )
                    try:
                        conn.commit()
                    except AttributeError:
                        pass
                    ctx["turn_index"] = turn_index

            # 2. Ingest via orchestrator
            payload = {
                "context_id": context_id,
                "session_id": session_id,
                "role": role,
                "content": content,
                "timestamp": timestamp,
            }
            batch = adapt_chat_turn(payload, f"ingest-{uuid.uuid4()}")
            # Async execution off the critical path. `ThreadPoolExecutor` does
            # not propagate `ContextVar`s to the worker thread (that's an
            # asyncio-only behavior) -- copy the current context explicitly so
            # background ingestion's LLM calls (extraction, entity resolution,
            # temporal update -- the largest source of LLM calls in the
            # system) still land under this turn's correlation id.
            ctx_snapshot = contextvars.copy_context()
            self._executor.submit(ctx_snapshot.run, self._run_orchestrator_safe, batch)

    def _run_orchestrator_safe(self, batch: ContextBatch) -> None:
        try:
            with timed_operation(logger, "memory_engine.bg_ingest", {"batch_id": batch.ingestion_id, "context_id": batch.context_id}):
                self._orchestrator.run_batch(batch)
        except Exception as e:
            logger.error("Background ingestion failed for batch %s: %s", batch.ingestion_id, e, exc_info=True)

    def submit_batch(self, context_id: str, turns_batch: list[TurnBatchEntry]) -> str:
        """Milestone 2 of the AI-DND bridge: async batched ingest for
        `POST /v1/memory/ingest`. Each turn becomes one `ContextRecord` with a
        deterministic `record_id` (`context_id:turn:{turn_number}`) -- so a
        `retry_batch` call re-derives the exact same `chunk_id`
        (`chunk_id_for`) the first attempt did, and the orchestrator's own
        idempotent replay (`_skip_result` treats an already-`COMPLETED` chunk
        as a no-op) does the rest. Runs off the critical path via the same
        `ThreadPoolExecutor` `add_turn_async` already uses -- ingest never
        blocks a turn. `batch_id` is a bare UUID string, not `f"ingest-{...}"`
        -- AI-DND's real (non-mock) `MemoryIngestResponse`/`BatchStatus`
        models type it as `UUID`, which a prefixed string fails to parse
        as. Nothing internal keys off the old prefix; it was only ever a
        human-readable label on an otherwise-opaque dict/DB key."""
        batch_id = str(uuid.uuid4())
        records = tuple(
            ContextRecord(
                record_id=f"{context_id}:turn:{entry.turn_number}",
                occurred_at=entry.occurred_at or _synthetic_turn_occurred_at(entry.turn_number),
                content=entry.text,
                actor_id=str(entry.participant_id),
                # `turn_index` is what graph_plan_builder._turn_node reads;
                # `turn_number` is kept alongside as the AI-DND-facing name
                # and what graph_plan_builder._fact_node also writes onto the
                # Fact node itself (§4/§5: as_of_turn filtering needs
                # turn_number on the fact, not just the Turn node).
                metadata={"turn_number": entry.turn_number, "turn_index": entry.turn_number},
            )
            for entry in turns_batch
        )
        chunk_turn_pairs = [
            (chunk_id_for(context_id, record.record_id), entry.turn_number)
            for entry, record in zip(turns_batch, records)
        ]
        chunk_ids = tuple(chunk_id for chunk_id, _ in chunk_turn_pairs)
        # §1 fix: source identity is the stable playthrough (context_id), not
        # this submission attempt's random batch_id. The chunk's identity
        # already only depends on context_id + turn_number
        # (validation.chunk_id_for); PostgresChunkStore.put additionally
        # locks in the whole Chunk (source descriptor included) as immutable
        # the first time a chunk_id is seen -- a stable source here is what
        # lets a later catch-up batch (a fresh `ingestion_id`, same turns)
        # replay onto the SAME chunk instead of tripping
        # ImmutableRecordConflictError on a source_external_id that only
        # ever matched itself once. `ingestion_id` (already random per call)
        # is the actual "this submission attempt" identity -- unchanged.
        batch = ContextBatch(
            ingestion_id=batch_id,
            context_id=context_id,
            source=SourceDescriptor(source_type="turn_batch", source_external_id=context_id),
            records=records,
        )
        self._batches[batch_id] = {"batch": batch, "chunk_ids": chunk_ids, "result": None, "error": None}
        # §3 fix: durable row too, so status/retry survive this process
        # ending -- see PostgresBatchStore's docstring.
        self._batch_store.create(batch, chunk_turn_pairs)

        ctx_snapshot = contextvars.copy_context()
        self._executor.submit(ctx_snapshot.run, self._run_batch_safe, batch_id, batch)
        return batch_id

    def _run_batch_safe(self, batch_id: str, batch: ContextBatch) -> None:
        try:
            with timed_operation(
                logger, "memory_engine.bg_batch_ingest", {"batch_id": batch_id, "context_id": batch.context_id}
            ):
                result = self._orchestrator.run_batch(batch)
                self._batches[batch_id]["result"] = result
        except Exception as e:
            logger.error("Background batch ingestion failed for batch %s: %s", batch_id, e, exc_info=True)
            self._batches[batch_id]["error"] = str(e)
            # §3 fix: durably recorded too -- the in-memory entry above is
            # only ever visible to this same process/replica.
            try:
                self._batch_store.mark_run_error(batch_id, str(e))
            except Exception:
                logger.warning("failed to durably record run error for batch %s", batch_id, exc_info=True)

    def get_batch_status(self, batch_id: str) -> BatchStatus:
        entry = self._batches.get(batch_id)
        if entry is not None:
            if entry["error"] is not None:
                return BatchStatus(
                    batch_id=batch_id, status="failed", facts_created=0, error=entry["error"], retryable=True
                )
            result: BatchRunResult | None = entry["result"]
            if result is None:
                return BatchStatus(batch_id=batch_id, status="pending", facts_created=0, retryable=False)
            return _batch_status_from_result(batch_id, result)
        # §3 fix: not in this process's memory -- a different replica, or
        # this process restarted since the batch was submitted. Fall back to
        # the durable status (derived from `ingestion_jobs`, not a second
        # copy of it) instead of the old "unknown batch -> pending forever."
        status = self._batch_store.get_status(batch_id)
        if status is None:
            raise BatchNotFoundError(f"unknown batch_id: {batch_id}")
        return status

    def retry_batch(self, batch_id: str) -> str:
        """Re-submits the same `ContextBatch` recorded at `submit_batch` time.
        No separate retry code path -- the orchestrator's own idempotent
        replay is what actually skips already-completed chunks and redoes
        only the failed ones."""
        entry = self._batches.get(batch_id)
        if entry is not None:
            batch: ContextBatch = entry["batch"]
        else:
            # §3 fix: reconstruct from the durable row instead of failing
            # outright -- what makes retry work after a process restart.
            batch = self._batch_store.get_context_batch(batch_id)
            if batch is None:
                raise BatchNotFoundError(f"unknown batch_id: {batch_id}")
            chunk_ids = tuple(chunk_id_for(batch.context_id, r.record_id) for r in batch.records)
            self._batches[batch_id] = {"batch": batch, "chunk_ids": chunk_ids, "result": None, "error": None}
            entry = self._batches[batch_id]
        entry["result"] = None
        entry["error"] = None
        self._batch_store.clear_run_error(batch_id)
        ctx_snapshot = contextvars.copy_context()
        self._executor.submit(ctx_snapshot.run, self._run_batch_safe, batch_id, batch)
        return batch_id

    def write_template_entity(self, context_id: str, entity: DirectEntityInput) -> int:
        """Master-mode authoring-time direct write (Milestone 3a). No LLM
        call -- see direct_authoring.py's module docstring for why."""
        allocator, writer = self._require_authoring_deps()
        return write_entity(context_id, entity, allocator, writer)

    def write_template_fact(self, context_id: str, fact: DirectFactInput) -> int:
        allocator, writer = self._require_authoring_deps()
        return write_fact(
            context_id, fact, allocator, writer, self._fact_metadata_store, self._external_fact_id_store,
            self._fact_projection_writer,
        )

    def write_scenario_checkpoints(self, template_context_id: str, checkpoints: list[str]) -> None:
        """Milestone 5: the scenario's ordered checkpoint list, stored once
        against the template context_id (not per-playthrough -- every clone
        shares the same authored ordering)."""
        self._checkpoint_store.put(template_context_id, checkpoints)

    def ingest_template_lore(self, context_id: str, lore_text: str) -> None:
        """Newbie-mode authoring-time ingestion: the same LLM extractor
        runtime ingestion uses, pointed at the scenario's template context_id
        instead of a playthrough's. Synchronous, not `submit_batch` -- Core
        API's publish flow is already async at its own layer (`202 Accepted`
        per the RFC), so this call blocking until extraction finishes is the
        simpler design, not a missing feature: nesting a second poll loop
        inside an already-async publish would only add latency to surface
        the same eventual result.

        AI-DND memory-layer contract gap (found while scoping, not asked
        for): `record_id` used to be the fixed `{context_id}:template-lore`
        regardless of content -- chunks are immutable, so republishing the
        SAME scenario with EDITED lore text hit the exact conflict check
        that protects runtime ingestion (`ImmutableRecordConflictError`),
        instead of the upsert-by-scenario_id behavior master mode already
        gets for free from content-addressed MERGE. `record_id` is now
        content-addressed too, so a genuinely new lore text always gets a
        fresh, non-conflicting chunk; `begin_template_republish` (called
        first, unconditionally) retires whatever facts the PRIOR lore
        version produced, so a republish behaves as a real replace rather
        than an accumulation of every version ever published."""
        self.begin_template_republish(context_id)
        occurred_at = datetime.now(timezone.utc)
        record = ContextRecord(
            record_id=f"{context_id}:template-lore:{content_hash(lore_text)[7:23]}",
            occurred_at=occurred_at, content=lore_text,
        )
        batch = ContextBatch(
            ingestion_id=f"template-{uuid.uuid4()}", context_id=context_id,
            source=SourceDescriptor(source_type="scenario_template", source_external_id=context_id),
            records=(record,),
        )
        self._orchestrator.run_batch(batch)

    def begin_template_republish(self, context_id: str) -> int:
        """AI-DND memory-layer contract: a scenario template republish must
        replace its prior content, not accumulate alongside it (upsert by
        scenario_id). Master mode already gets this for free -- its writes
        are content-addressed MERGE, so an unchanged fact/entity collapses
        onto the same node. What neither mode got before this: MERGE only
        adds/updates matching content, it never *removes* a fact a creator
        deleted from a new version -- a gap found while scoping this
        requirement, not asked for in the contract itself.

        Call once per template-ingest request, before writing any new
        entities/facts. Archives every currently-active Fact this template
        context has -- the same `archived`/`is_current` flags rollback
        already uses (both are in `PostgresGraphManifestStore.
        NODE_MUTABLE_PROPERTIES`, so this is a normal, manifest-compatible
        partial update to an already-registered node, not a new kind of
        write). Scoped to Facts only, not Entities: an entity can still be
        referenced by facts outside this republish batch (e.g. a playthrough
        already cloned from an earlier version), so removing entities
        wholesale on republish is a sharper, riskier operation left for a
        deliberate follow-up rather than folded into this fix silently.
        Returns the number of facts archived."""
        if self._hydra_transport is None:
            raise RuntimeError("begin_template_republish called without a hydra_transport configured")
        _, writer = self._require_authoring_deps()
        rows = self._hydra_transport.read(
            "MATCH (f:Fact {context_id: $context_id, is_current: true}) "
            "RETURN f.id AS id, f.logical_key AS logical_key",
            {"context_id": context_id}, None,
        )
        now_epoch = int(datetime.now(timezone.utc).timestamp())
        nodes = tuple(
            GraphNode(
                int(row["id"]), "Fact", row["logical_key"],
                {
                    "context_id": context_id, "logical_key": row["logical_key"], "is_current": False,
                    "archived": True, "superseded_at": now_epoch, "valid_to": now_epoch,
                },
            )
            for row in rows if row.get("id") is not None and row.get("logical_key")
        )
        if not nodes:
            return 0
        plan = GraphWritePlan(
            context_id=context_id, plan_key=f"plan:template-republish:{context_id}:{now_epoch}",
            nodes=nodes, relationships=(),
        )
        writer.write(plan)
        return len(nodes)

    def clone_playthrough_space(self, template_context_id: str, playthrough_context_id: str) -> CloneResult:
        """ADR-7: ingest once (into the scenario's template context_id, via
        `write_template_entity`/`write_template_fact`/`ingest_template_lore`),
        clone many (once per playthrough, here)."""
        allocator, writer = self._require_authoring_deps()
        if self._hydra_transport is None:
            raise RuntimeError("clone_playthrough_space called without a hydra_transport configured")
        return clone(
            template_context_id, playthrough_context_id, allocator, writer, self._hydra_transport,
            self._fact_metadata_store, self._fact_projection_writer,
        )

    def get_entity(self, context_id: str, canonical_name: str) -> dict[str, object] | None:
        """AI-DND memory-layer contract: `GET /v1/memory/entity/{entity_id}`
        (§4.5, "required for launch" -- present in the RFC as a debugging
        and future-tool-calling hook, not called by any product code today).

        Identifier scheme: `canonical_name`, the same identity
        `direct_authoring.py` already uses (its own documented convention
        is that a caller resolves its own opaque `entity_id` to
        `canonical_name` before calling in). Scoped by `context_id` --
        entities aren't globally unique, only unique per playthrough/
        template context. Returns `None` if no such entity exists, rather
        than raising -- an unknown entity is this method's normal "not
        found" outcome, not an error."""
        if self._hydra_transport is None:
            raise RuntimeError("get_entity called without a hydra_transport configured")
        logical_key = f"entity:{canonical_name}"
        rows = self._hydra_transport.read(
            "MATCH (n:Entity {context_id: $context_id, logical_key: $logical_key}) "
            "RETURN n.id AS id, n.canonical_name AS canonical_name, n.entity_type AS entity_type, "
            "n.description AS description, n.aliases AS aliases",
            {"context_id": context_id, "logical_key": logical_key}, None,
        )
        if not rows:
            return None
        row = rows[0]
        raw_aliases = row.get("aliases")
        return {
            "entity_id": canonical_name,
            "canonical_name": row.get("canonical_name") or canonical_name,
            "entity_type": row.get("entity_type"),
            "description": row.get("description"),
            # write_entity flattens aliases to one comma-joined string
            # (graph properties are scalar-only) -- split back out here.
            "aliases": [a.strip() for a in raw_aliases.split(",")] if raw_aliases else [],
        }

    def _require_authoring_deps(self) -> tuple[GraphIdAllocator, GraphWriter]:
        if self._graph_id_allocator is None or self._authoring_graph_writer is None:
            raise RuntimeError(
                "direct authoring/cloning called without graph_id_allocator/authoring_graph_writer configured"
            )
        return self._graph_id_allocator, self._authoring_graph_writer

    def search_memories(
        self, context_id: str, query: str, question_date: datetime, scenario_id: str | None = None
    ) -> str:
        with correlation_scope(JournalContext(context_id=context_id, scenario_id=scenario_id)), timed_operation(
            logger, "memory_engine.search_memories", {"context_id": context_id, "query_len": len(query)}
        ):
            return self._retrieval_engine.retrieve_and_answer(context_id, query, question_date)

    def retrieve_facts(
        self,
        context_id: str,
        query_text: str,
        question_date: datetime,
        game_state: dict | None = None,
        checkpoint: str | None = None,
        as_of_turn: int | None = None,
        template_context_id: str | None = None,
        participant_id: str | None = None,
        scenario_id: str | None = None,
    ):
        """Structured retrieval for AI-DND's `POST /v1/memory/query`
        (Milestone 1 of the AI-DND bridge). Thin passthrough to
        `HybridRetrievalEngine.retrieve_facts`, same shape as
        `search_memories`'s passthrough to `retrieve_and_answer`.

        §5 fix: `participant_id` now actually reaches retrieval's
        participant-scoped visibility check (was accepted on the wire and
        dropped here). `scenario_id` is forwarded to the journal/
        correlation context only (not a new filter -- `context_id` /
        playthrough_id is already this system's hard isolation boundary;
        every fact/embedding/graph write and read is scoped to it)."""
        with correlation_scope(JournalContext(context_id=context_id, scenario_id=scenario_id)), timed_operation(
            logger, "memory_engine.retrieve_facts", {"context_id": context_id, "query_len": len(query_text)}
        ):
            return self._retrieval_engine.retrieve_facts(
                context_id,
                query_text,
                question_date,
                game_state=game_state,
                checkpoint=checkpoint,
                as_of_turn=as_of_turn,
                template_context_id=template_context_id,
                participant_id=participant_id,
            )

    def generate_reply(
        self, context_id: str, session_id: str, user_message: str, scenario_id: str | None = None
    ) -> str:
        # One correlation id for the whole turn -- add_turn_async/search_memories
        # each open their own scope, but `correlation_scope` reuses the ambient
        # one instead of forking, so ingest -> retrieve -> ingest-reply all land
        # under one `journal_steps.correlation_id` (and one `scenario_id`,
        # Phase 9's tenancy identity -- set once here, propagated to every
        # nested call without each one needing to pass it again).
        with correlation_scope(
            JournalContext(context_id=context_id, session_id=session_id, scenario_id=scenario_id)
        ), timed_operation(
            logger, "memory_engine.generate_reply", {"context_id": context_id, "session_id": session_id}
        ) as ctx:
            now = datetime.now(timezone.utc)

            # Ingest user turn
            self.add_turn_async(context_id, session_id, "user", user_message, now)

            # Retrieve context and answer
            reply = self.search_memories(context_id, user_message, now)

            # Ingest assistant turn
            self.add_turn_async(context_id, session_id, "assistant", reply, now)
            ctx["reply_len"] = len(reply)
            return reply

    def agent_turn(self, context_id: str, user_prompt: str, system_prompt: str | None = None) -> str:
        """§11 fix: the first real production caller of the Phase 9 tool
        harness (`ToolRegistry`/`GuardedToolExecutor`/`run_tool_loop`) --
        until this method, those had registry/hook/loop tests but no
        runtime code path ever constructed or called them. Lets an LLM
        decide, from a natural-language prompt, whether to search this
        playthrough's memory, create a save point, or roll back to one --
        see `core/agent_tools.py` for the tool definitions and the one
        authorization hook `rollback_to_save_point` needs (every other tool
        is closed over `context_id`, never LLM-controllable)."""
        from context_memory.core.agent_tools import (
            DEFAULT_MEMORY_AGENT_SYSTEM_PROMPT,
            build_memory_agent_tools,
            build_rollback_authorization_hook,
        )
        from context_memory.core.tool_executor import GuardedToolExecutor
        from context_memory.core.tool_loop import run_tool_loop

        registry = build_memory_agent_tools(self, context_id)
        executor = GuardedToolExecutor(
            registry, journal=self._journal,
            pre_hooks=(build_rollback_authorization_hook(self, context_id),),
        )
        with correlation_scope(JournalContext(context_id=context_id)), timed_operation(
            logger, "memory_engine.agent_turn", {"context_id": context_id}
        ):
            return run_tool_loop(
                self._llm, registry, executor,
                system_prompt or DEFAULT_MEMORY_AGENT_SYSTEM_PROMPT, user_prompt,
            )
