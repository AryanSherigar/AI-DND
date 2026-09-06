"""PostgreSQL persistence adapter for immutable chunks and graph ID allocation.

Bare `§N` references below are sections of docs/fixes_and_evaluation_findings.md.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime

from context_memory.core.enums import IngestionJobState, is_legal_job_transition
from context_memory.core.errors import GraphPayloadConflictError, IllegalJobTransitionError, ImmutableRecordConflictError
from context_memory.core.graph import GraphNode, GraphRelationship, GraphWritePlan
from context_memory.core.models import (
    Chunk,
    ContextBatch,
    ContextRecord,
    Embedding,
    ExtractedMemoryCandidate,
    IngestionJob,
    SourceDescriptor,
)
from context_memory.ingestion.batch_models import BatchStatus


class PostgresChunkStore:
    def __init__(self, connection: object) -> None:
        self._connection = connection

    def put(self, chunk: Chunk) -> Chunk:
        with self._connection.transaction():
            with self._connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT context_id, source_type, source_external_id, source_record_id,
                           session_id, actor_id, actor_role, raw_text, content_hash,
                           occurred_at, metadata
                    FROM evidence_chunks WHERE chunk_id = %s AND context_id = %s FOR UPDATE
                    """,
                    (chunk.chunk_id, chunk.context_id),
                )
                existing = cursor.fetchone()
                if existing is not None:
                    expected = (
                        chunk.context_id,
                        chunk.source.source_type,
                        chunk.source.source_external_id,
                        chunk.source_record_id,
                        chunk.session_id,
                        chunk.actor_id,
                        chunk.actor_role,
                        chunk.raw_text,
                        chunk.content_hash,
                        chunk.occurred_at,
                        dict(chunk.metadata),
                    )
                    if existing != expected:
                        raise ImmutableRecordConflictError(
                            f"chunk_id {chunk.chunk_id} has different immutable content"
                        )
                    return chunk
                cursor.execute(
                    """
                    INSERT INTO evidence_chunks (
                        chunk_id, context_id, source_type, source_external_id,
                        source_record_id, session_id, actor_id, actor_role,
                        raw_text, content_hash, occurred_at, metadata
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                    """,
                    (
                        chunk.chunk_id,
                        chunk.context_id,
                        chunk.source.source_type,
                        chunk.source.source_external_id,
                        chunk.source_record_id,
                        chunk.session_id,
                        chunk.actor_id,
                        chunk.actor_role,
                        chunk.raw_text,
                        chunk.content_hash,
                        chunk.occurred_at,
                        json.dumps(dict(chunk.metadata), sort_keys=True),
                    ),
                )
                cursor.execute(
                    """
                    INSERT INTO ingestion_jobs (job_id, chunk_id, context_id, state)
                    VALUES (%s, %s, %s, 'pending_graph')
                    """,
                    (f"job:{chunk.chunk_id}", chunk.chunk_id, chunk.context_id),
                )
        return chunk

    def get(self, context_id: str, chunk_id: str) -> Chunk | None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT context_id, source_type, source_external_id, source_record_id,
                       session_id, actor_id, actor_role, raw_text, content_hash,
                       occurred_at, metadata
                FROM evidence_chunks WHERE chunk_id = %s AND context_id = %s
                """,
                (chunk_id, context_id),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        return Chunk(
            chunk_id=chunk_id,
            context_id=row[0],
            source=SourceDescriptor(source_type=row[1], source_external_id=row[2]),
            source_record_id=row[3],
            session_id=row[4],
            actor_id=row[5],
            actor_role=row[6],
            raw_text=row[7],
            content_hash=row[8],
            occurred_at=row[9],
            metadata=row[10],
        )

    def allocate_graph_id(self, node_kind: str, context_id: str, logical_key: str) -> int:
        with self._connection.transaction():
            with self._connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO graph_id_registry (node_kind, context_id, logical_key)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (node_kind, context_id, logical_key)
                    DO UPDATE SET logical_key = EXCLUDED.logical_key
                    RETURNING graph_id
                    """,
                    (node_kind, context_id, logical_key),
                )
                row = cursor.fetchone()
        if row is None:
            raise RuntimeError("graph ID allocation returned no row")
        return int(row[0])


class PostgresExtractionStore:
    """Append-only SQL audit trail for the deterministic M4 baseline."""

    def __init__(self, connection: object) -> None:
        self._connection = connection

    def record(
        self,
        *,
        attempt_id: str,
        chunk: Chunk,
        extractor_name: str,
        extractor_version: str,
        accepted: object,
        rejected: object,
    ) -> None:
        accepted_items = tuple(accepted)  # type: ignore[arg-type]
        rejected_items = tuple(rejected)  # type: ignore[arg-type]
        with self._connection.transaction():
            with self._connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO extraction_attempts (
                        attempt_id, chunk_id, context_id, extractor_name, extractor_version,
                        extractor_kind, quality_status, input_content_hash, accepted_count, rejected_count
                    ) VALUES (%s, %s, %s, %s, %s, 'deterministic_fixture', 'baseline_only', %s, %s, %s)
                    ON CONFLICT (attempt_id) DO NOTHING
                    """,
                    (attempt_id, chunk.chunk_id, chunk.context_id, extractor_name, extractor_version,
                     chunk.content_hash, len(accepted_items), len(rejected_items)),
                )
                for candidate in accepted_items:
                    assert isinstance(candidate, ExtractedMemoryCandidate)
                    cursor.execute(
                        """
                        INSERT INTO extracted_memory_candidates (
                            attempt_id, candidate_id, memory_text, memory_type, scope_type, scope_id,
                            source_record_id, source_start, source_end, confidence, observed_at,
                            valid_from, valid_to, entities
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
                        ON CONFLICT (attempt_id, candidate_id) DO NOTHING
                        """,
                        (
                            attempt_id, candidate.candidate_id, candidate.text, candidate.memory_type.value,
                            candidate.scope_type.value, candidate.scope_id, candidate.source_span.source_record_id,
                            candidate.source_span.source_start, candidate.source_span.source_end, candidate.confidence,
                            candidate.temporal.observed_at, candidate.temporal.valid_from, candidate.temporal.valid_to,
                            json.dumps([
                                {"surface": entity.surface, "entity_type": entity.entity_type}
                                for entity in candidate.entities
                            ], sort_keys=True),
                        ),
                    )

                for ordinal, item in enumerate(rejected_items):
                    draft = item.draft
                    cursor.execute(
                        """
                        INSERT INTO rejected_extraction_candidates (
                            attempt_id, ordinal, candidate_id, rejection_reason, draft
                        ) VALUES (%s, %s, %s, %s, %s::jsonb)
                        ON CONFLICT (attempt_id, ordinal) DO NOTHING
                        """,
                        (
                            attempt_id, ordinal, item.candidate_id, item.reason,
                            json.dumps({
                                "candidate_id": draft.candidate_id, "text": draft.text,
                                "source_start": draft.source_start, "source_end": draft.source_end,
                                "confidence": draft.confidence,
                                "memory_type": draft.memory_type.value if draft.memory_type else None,
                                "scope_type": draft.scope_type.value if draft.scope_type else None,
                                "scope_id": draft.scope_id,
                            }, sort_keys=True),
                        ),
                    )


class PostgresGraphManifestStore:
    """Reject changed payload before a non-atomic local HydraDB write begins.

    One narrow, deliberate exception: `NODE_MUTABLE_PROPERTIES`. Bitemporal
    supersession (ADR-030) needs to flip `is_current`/`superseded_at`/`valid_to`
    on a Fact node that was already fully written in an earlier turn's plan —
    `graph_plan_builder.py` only has the prior fact's `FactState` (not its full
    original property set) at that point, so it can only ever build a partial
    node for the update. Under strict whole-payload immutability that partial
    node's hash would always differ from the original, so every supersession
    would hit the exact same `GraphPayloadConflictError` the Session-node bug
    did (see `graph_plan_builder.py`'s `_session_node` docstring) — this is that
    same class of bug, caught before it could fire, not a hypothetical. Any
    field outside that fixed allow-list still triggers a hard conflict, which
    preserves the original guarantee: only a real logical_key collision can
    reach it now.

    `archived` (Phase 6, rollback): a fact created after a save point's cutoff
    becomes permanently invisible on this timeline. Deliberately its own flag,
    not an overload of `superseded_at` — that field's real bitemporal meaning
    ("when did this stop being true") would be corrupted by pressing it into
    service as an "undo" marker.
    """

    NODE_MUTABLE_PROPERTIES = frozenset({"is_current", "superseded_at", "valid_to", "archived"})

    def __init__(self, connection: object) -> None:
        self._connection = connection

    def register(self, plan: GraphWritePlan) -> None:
        with self._connection.transaction():
            with self._connection.cursor() as cursor:
                for record in plan.records():
                    kind = "node" if isinstance(record, GraphNode) else "relationship"
                    payload_hash = plan.payload_hash(record)
                    cursor.execute(
                        "SELECT graph_id, payload_hash, payload FROM graph_write_manifests WHERE record_kind = %s AND context_id = %s AND logical_key = %s FOR UPDATE",
                        (kind, plan.context_id, record.logical_key),
                    )
                    existing = cursor.fetchone()
                    if existing is not None:
                        existing_graph_id, existing_hash, existing_payload = existing
                        if (existing_graph_id, existing_hash) == (record.graph_id, payload_hash):
                            continue
                        merged_payload = None
                        if kind == "node" and existing_graph_id == record.graph_id:
                            merged_payload = self._merge_mutable_only(existing_payload, self._payload(record))
                        if merged_payload is None:
                            raise GraphPayloadConflictError(f"{kind} {record.logical_key} has a different immutable graph payload")
                        merged_hash = self._hash(merged_payload)
                        cursor.execute(
                            "UPDATE graph_write_manifests SET payload_hash = %s, payload = %s::jsonb "
                            "WHERE record_kind = %s AND context_id = %s AND logical_key = %s",
                            (merged_hash, json.dumps(merged_payload, sort_keys=True), kind, plan.context_id, record.logical_key),
                        )
                        continue
                    cursor.execute(
                        "INSERT INTO graph_write_manifests (record_kind, context_id, logical_key, graph_id, payload_hash, payload) VALUES (%s, %s, %s, %s, %s, %s::jsonb)",
                        (kind, plan.context_id, record.logical_key, record.graph_id, payload_hash, json.dumps(self._payload(record), sort_keys=True)),
                    )

    @classmethod
    def _merge_mutable_only(cls, existing_payload: dict[str, object], new_payload: dict[str, object]) -> dict[str, object] | None:
        """Returns a merged payload if `new_payload` only touches properties in
        `NODE_MUTABLE_PROPERTIES` relative to `existing_payload`, else None (a
        real conflict). The merge is additive over the *existing* full property
        set — it never drops a property the new (partial) payload omits."""
        if existing_payload.get("label") != new_payload.get("label"):
            return None
        merged_properties = dict(existing_payload.get("properties", {}))
        for key, value in new_payload.get("properties", {}).items():
            if key in merged_properties and merged_properties[key] != value and key not in cls.NODE_MUTABLE_PROPERTIES:
                return None
            merged_properties[key] = value
        return {"label": existing_payload["label"], "id": existing_payload["id"], "properties": merged_properties}

    @staticmethod
    def _hash(payload: dict[str, object]) -> str:
        import hashlib
        return hashlib.sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    @staticmethod
    def _payload(record: GraphNode | GraphRelationship) -> dict[str, object]:
        if isinstance(record, GraphNode):
            return {"label": record.label, "id": record.graph_id, "properties": dict(record.properties)}
        return {"type": record.relationship_type, "id": record.graph_id, "source": record.source_id, "destination": record.destination_id, "source_label": record.source_label, "destination_label": record.destination_label, "properties": dict(record.properties)}


class PostgresSearchIndexStore:
    """PostgreSQL `tsvector`/`ts_rank_cd` full-text index for keyword retrieval."""

    def __init__(self, connection: object) -> None:
        self._connection = connection

    def put(self, context_id: str, fact_id: str, raw_text: str) -> None:
        with self._connection.transaction():
            with self._connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO fact_search_index (fact_id, context_id, raw_text, is_active)
                    VALUES (%s, %s, %s, true)
                    ON CONFLICT (fact_id) DO UPDATE
                    SET raw_text = EXCLUDED.raw_text, is_active = true
                    """,
                    (fact_id, context_id, raw_text)
                )

    def contains(self, context_id: str, fact_id: str) -> bool:
        """§8 fix: independent post-write confirmation for completion
        verification (orchestrator._verify)."""
        with self._connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM fact_search_index WHERE context_id = %s AND fact_id = %s AND is_active LIMIT 1",
                (context_id, fact_id),
            )
            return cursor.fetchone() is not None

    def put_batch(self, items: Sequence[tuple[str, str, str]]) -> None:
        """One multi-row upsert for a whole chunk's accepted facts instead of
        `put()` in a loop -- N round trips collapse to 1. `items` is
        `(context_id, fact_id, raw_text)` tuples. Same upsert semantics as
        `put()` (no immutability check here -- this store has none), so this
        is a pure batching change, not a behavior change. See
        `docs/fixes_and_evaluation_findings.md` §3.2/§3.6: live-measured as
        the single biggest lever in the non-extraction ingestion path
        (278 sequential round trips for 139 facts in a 25-turn sample), and
        backed by published Postgres benchmarks showing 10-50x for exactly
        this batch-vs-N-single-row-inserts pattern.
        """
        if not items:
            return
        with self._connection.transaction():
            with self._connection.cursor() as cursor:
                values_sql = ", ".join(["(%s, %s, %s, true)"] * len(items))
                params: list[object] = []
                for context_id, fact_id, raw_text in items:
                    params.extend((fact_id, context_id, raw_text))
                cursor.execute(
                    f"""
                    INSERT INTO fact_search_index (fact_id, context_id, raw_text, is_active)
                    VALUES {values_sql}
                    ON CONFLICT (fact_id) DO UPDATE
                    SET raw_text = EXCLUDED.raw_text, is_active = true
                    """,
                    params,
                )


class PostgresEmbeddingStore:
    """Versioned fact/chunk embedding persistence against `memory_embeddings` (Milestone 7)."""

    def __init__(self, connection: object) -> None:
        self._connection = connection

    def put(self, embedding: Embedding) -> Embedding:
        """Insert once per (context, subject, model, version); replay with the same
        content hash is a no-op, a changed hash under the same version is rejected
        (re-embedding the same version must not silently rewrite a prior vector)."""
        with self._connection.transaction():
            with self._connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT embedded_content_hash FROM memory_embeddings
                    WHERE context_id = %s AND subject_kind = %s AND subject_id = %s
                      AND model_name = %s AND model_version = %s
                    FOR UPDATE
                    """,
                    (
                        embedding.context_id, embedding.subject_kind, embedding.subject_id,
                        embedding.model_name, embedding.model_version,
                    ),
                )
                existing = cursor.fetchone()
                if existing is not None:
                    if existing[0] != embedding.embedded_content_hash:
                        raise ImmutableRecordConflictError(
                            f"embedding for {embedding.subject_kind}:{embedding.subject_id} "
                            f"model {embedding.model_name}/{embedding.model_version} "
                            "has a different embedded_content_hash"
                        )
                    return embedding
                vector_literal = "[" + ",".join(repr(float(value)) for value in embedding.values) + "]"
                cursor.execute(
                    """
                    INSERT INTO memory_embeddings (
                        context_id, subject_kind, subject_id, source_chunk_id,
                        model_name, model_version, dimensions, embedding,
                        embedded_content_hash, is_active
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s::vector, %s, %s)
                    """,
                    (
                        embedding.context_id, embedding.subject_kind, embedding.subject_id,
                        embedding.source_chunk_id, embedding.model_name, embedding.model_version,
                        len(embedding.values), vector_literal, embedding.embedded_content_hash,
                        embedding.is_active,
                    ),
                )
        return embedding

    def put_batch(self, embeddings: Sequence[Embedding]) -> list[Embedding]:
        """Batched `put()`: one existence check covering every embedding in
        the batch plus one multi-row `INSERT` for the ones that are actually
        new, instead of `put()` in a loop (a `SELECT ... FOR UPDATE` +
        `INSERT` round trip per embedding). Same immutability contract as
        `put()`, applied per-row within the batch: an unchanged replay is a
        no-op for that row, a changed hash under the same
        (context, subject_kind, subject_id, model_name, model_version)
        still raises `ImmutableRecordConflictError` -- this only changes how
        many round trips it takes, not what's allowed. See
        `docs/fixes_and_evaluation_findings.md` §3.2/§3.6.
        """
        if not embeddings:
            return []
        with self._connection.transaction():
            with self._connection.cursor() as cursor:
                keys = [
                    (e.context_id, e.subject_kind, e.subject_id, e.model_name, e.model_version)
                    for e in embeddings
                ]
                key_values_sql = ", ".join(["(%s, %s, %s, %s, %s)"] * len(keys))
                key_params = [item for key in keys for item in key]
                cursor.execute(
                    f"""
                    SELECT context_id, subject_kind, subject_id, model_name, model_version, embedded_content_hash
                    FROM memory_embeddings
                    WHERE (context_id, subject_kind, subject_id, model_name, model_version) IN ({key_values_sql})
                    FOR UPDATE
                    """,
                    key_params,
                )
                existing_hash_by_key = {
                    (row[0], row[1], row[2], row[3], row[4]): row[5] for row in cursor.fetchall()
                }

                to_insert: list[Embedding] = []
                for embedding, key in zip(embeddings, keys):
                    existing_hash = existing_hash_by_key.get(key)
                    if existing_hash is not None:
                        if existing_hash != embedding.embedded_content_hash:
                            raise ImmutableRecordConflictError(
                                f"embedding for {embedding.subject_kind}:{embedding.subject_id} "
                                f"model {embedding.model_name}/{embedding.model_version} "
                                "has a different embedded_content_hash"
                            )
                        continue
                    to_insert.append(embedding)

                if to_insert:
                    row_values_sql = ", ".join(["(%s, %s, %s, %s, %s, %s, %s, %s::vector, %s, %s)"] * len(to_insert))
                    row_params: list[object] = []
                    for embedding in to_insert:
                        vector_literal = "[" + ",".join(repr(float(value)) for value in embedding.values) + "]"
                        row_params.extend((
                            embedding.context_id, embedding.subject_kind, embedding.subject_id,
                            embedding.source_chunk_id, embedding.model_name, embedding.model_version,
                            len(embedding.values), vector_literal, embedding.embedded_content_hash,
                            embedding.is_active,
                        ))
                    cursor.execute(
                        f"""
                        INSERT INTO memory_embeddings (
                            context_id, subject_kind, subject_id, source_chunk_id,
                            model_name, model_version, dimensions, embedding,
                            embedded_content_hash, is_active
                        ) VALUES {row_values_sql}
                        """,
                        row_params,
                    )
        return list(embeddings)

    def contains(self, context_id: str, subject_kind: str, subject_id: str) -> bool:
        """§8 fix: independent post-write confirmation for completion
        verification (orchestrator._verify) -- a real read, not a re-read of
        whatever `put`/`put_batch` already believed happened."""
        with self._connection.cursor() as cursor:
            cursor.execute(
                "SELECT 1 FROM memory_embeddings WHERE context_id = %s AND subject_kind = %s AND subject_id = %s LIMIT 1",
                (context_id, subject_kind, subject_id),
            )
            return cursor.fetchone() is not None

    def deactivate(self, context_id: str, subject_kind: str, subject_id: str) -> None:
        """Mark all model versions of one subject inactive (e.g. superseded fact)."""
        with self._connection.transaction():
            with self._connection.cursor() as cursor:
                cursor.execute(
                    """
                    UPDATE memory_embeddings SET is_active = false
                    WHERE context_id = %s AND subject_kind = %s AND subject_id = %s
                    """,
                    (context_id, subject_kind, subject_id),
                )


class PostgresJobStore:
    """Milestone 8 recovery state machine over `ingestion_jobs` (docs/decisions.md ADR-031)."""

    def __init__(self, connection: object) -> None:
        self._connection = connection

    def get(self, chunk_id: str) -> IngestionJob | None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT job_id, chunk_id, context_id, state, attempt_count, last_verified_state, last_error
                FROM ingestion_jobs WHERE chunk_id = %s
                """,
                (chunk_id,),
            )
            row = cursor.fetchone()
        if row is None:
            return None
        return IngestionJob(
            job_id=row[0], chunk_id=row[1], context_id=row[2], state=IngestionJobState(row[3]),
            attempt_count=row[4], last_verified_state=IngestionJobState(row[5]) if row[5] else None,
            last_error=row[6],
        )

    def seed(self, chunk_id: str, context_id: str) -> IngestionJob:
        """Idempotent: PostgresChunkStore.put already inserts this row (ADR-014); this
        is a defensive fallback, safe to call even when that row already exists."""
        with self._connection.transaction():
            with self._connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO ingestion_jobs (job_id, chunk_id, context_id, state)
                    VALUES (%s, %s, %s, 'pending_graph')
                    ON CONFLICT (chunk_id) DO NOTHING
                    """,
                    (f"job:{chunk_id}", chunk_id, context_id),
                )
        job = self.get(chunk_id)
        if job is None:
            raise RuntimeError(f"job seed for chunk_id {chunk_id} did not produce a row")
        return job

    def transition(self, chunk_id: str, new_state: IngestionJobState, *, error: str | None = None) -> IngestionJob:
        with self._connection.transaction():
            with self._connection.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT job_id, context_id, state, attempt_count, last_verified_state
                    FROM ingestion_jobs WHERE chunk_id = %s FOR UPDATE
                    """,
                    (chunk_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise IllegalJobTransitionError(f"no ingestion job for chunk_id {chunk_id}")
                job_id, context_id, current_raw, attempt_count, last_verified_raw = row
                current = IngestionJobState(current_raw)
                last_verified = IngestionJobState(last_verified_raw) if last_verified_raw else None
                if not is_legal_job_transition(current, new_state, last_verified):
                    raise IllegalJobTransitionError(
                        f"chunk {chunk_id}: {current.value} -> {new_state.value} is not a legal transition"
                    )
                next_attempt_count = attempt_count + 1 if new_state == IngestionJobState.RETRYABLE_FAILED else attempt_count
                next_last_verified = current.value if current.value not in (
                    IngestionJobState.RETRYABLE_FAILED.value, IngestionJobState.TERMINAL_FAILED.value,
                    IngestionJobState.MANUAL_REPAIR.value,
                ) else last_verified_raw
                cursor.execute(
                    """
                    UPDATE ingestion_jobs
                    SET state = %s, attempt_count = %s, last_verified_state = %s, last_error = %s, updated_at = now()
                    WHERE chunk_id = %s
                    """,
                    (new_state.value, next_attempt_count, next_last_verified, error, chunk_id),
                )
        return IngestionJob(
            job_id=job_id, chunk_id=chunk_id, context_id=context_id, state=new_state,
            attempt_count=next_attempt_count,
            last_verified_state=IngestionJobState(next_last_verified) if next_last_verified else None,
            last_error=error,
        )


class PostgresFactMetadataStore:
    """Milestones 4-5 of the AI-DND bridge: `when_active` (ADR-9) and
    `checkpoint` for pre-authored facts. Graph node properties are
    scalar-only (core/graph.py), so this lives beside `fact_search_index` in
    Postgres rather than on the Fact node itself -- same split this codebase
    already made once."""

    def __init__(self, connection: object) -> None:
        self._connection = connection

    def put(
        self, context_id: str, fact_id: int, checkpoint: str | None, when_active: dict | None,
        visible_to_participant_id: str | None = None, hidden: bool = False,
    ) -> None:
        if checkpoint is None and when_active is None and visible_to_participant_id is None and not hidden:
            return
        with self._connection.transaction():
            with self._connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO pre_authored_fact_metadata (fact_id, context_id, checkpoint, when_active, visible_to_participant_id, hidden)
                    VALUES (%s, %s, %s, %s::jsonb, %s, %s)
                    ON CONFLICT (fact_id) DO UPDATE
                    SET context_id = EXCLUDED.context_id, checkpoint = EXCLUDED.checkpoint, when_active = EXCLUDED.when_active,
                        visible_to_participant_id = EXCLUDED.visible_to_participant_id, hidden = EXCLUDED.hidden
                    """,
                    (
                        fact_id, context_id, checkpoint,
                        json.dumps(when_active) if when_active is not None else None,
                        visible_to_participant_id, hidden,
                    ),
                )

    def get_many(
        self, context_id: str, fact_ids: Sequence[int]
    ) -> dict[int, tuple[str | None, dict | None, str | None, bool]]:
        """Returns `{fact_id: (checkpoint, when_active, visible_to_participant_id, hidden)}`
        for whichever of `fact_ids` carry metadata -- most retrieved facts
        (runtime-extracted ones) won't, and are simply absent from the
        result rather than represented as an explicit all-`None` entry."""
        if not fact_ids:
            return {}
        with self._connection.cursor() as cursor:
            cursor.execute(
                "SELECT fact_id, checkpoint, when_active, visible_to_participant_id, hidden FROM pre_authored_fact_metadata "
                "WHERE context_id = %s AND fact_id = ANY(%s)",
                (context_id, list(fact_ids)),
            )
            return {row[0]: (row[1], row[2], row[3], row[4]) for row in cursor.fetchall()}


class PostgresExternalFactIdStore:
    """AI-DND memory-layer contract: resolves the caller's own opaque fact
    id to mem1's graph identity for it -- see
    `ingestion.direct_authoring.ExternalFactIdStore`'s docstring for why
    this is needed (`superseded_fact_id` on a direct-authored fact)."""

    def __init__(self, connection: object) -> None:
        self._connection = connection

    def get(self, context_id: str, external_fact_id: str) -> tuple[int, str] | None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                "SELECT graph_id, logical_key FROM external_fact_ids WHERE context_id = %s AND external_fact_id = %s",
                (context_id, external_fact_id),
            )
            row = cursor.fetchone()
        return (int(row[0]), row[1]) if row else None

    def put(self, context_id: str, external_fact_id: str, graph_id: int, logical_key: str) -> None:
        with self._connection.transaction():
            with self._connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO external_fact_ids (context_id, external_fact_id, graph_id, logical_key)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (context_id, external_fact_id) DO UPDATE
                    SET graph_id = EXCLUDED.graph_id, logical_key = EXCLUDED.logical_key
                    """,
                    (context_id, external_fact_id, graph_id, logical_key),
                )


class PostgresCheckpointStore:
    """Milestone 5: the ordered checkpoint list a scenario's pre-authored
    facts are authored against -- written once at template-ingest time,
    read at every query to resolve a bare `checkpoint` string to its
    ordinal position. Without this, `MemoryQueryRequest.checkpoint` is just
    an opaque label mem1 has no ordering for."""

    def __init__(self, connection: object) -> None:
        self._connection = connection

    def put(self, context_id: str, checkpoints: Sequence[str]) -> None:
        with self._connection.transaction():
            with self._connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO scenario_template_checkpoints (context_id, checkpoints)
                    VALUES (%s, %s::jsonb)
                    ON CONFLICT (context_id) DO UPDATE SET checkpoints = EXCLUDED.checkpoints
                    """,
                    (context_id, json.dumps(list(checkpoints))),
                )

    def get(self, context_id: str) -> list[str] | None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                "SELECT checkpoints FROM scenario_template_checkpoints WHERE context_id = %s", (context_id,)
            )
            row = cursor.fetchone()
        return row[0] if row else None


_BATCH_IN_FLIGHT_STATES = frozenset({
    IngestionJobState.PENDING_GRAPH.value, IngestionJobState.PENDING_EMBEDDINGS.value,
    IngestionJobState.VERIFYING.value,
})


def _serialize_context_batch(batch: ContextBatch) -> dict:
    return {
        "ingestion_id": batch.ingestion_id,
        "context_id": batch.context_id,
        "contract_version": batch.contract_version,
        "source_type": batch.source.source_type,
        "source_external_id": batch.source.source_external_id,
        "metadata": dict(batch.metadata),
        "records": [
            {
                "record_id": r.record_id,
                "occurred_at": r.occurred_at.isoformat(),
                "content_type": r.content_type,
                "content": r.content,
                "session_id": r.session_id,
                "actor_id": r.actor_id,
                "actor_role": r.actor_role,
                "metadata": dict(r.metadata),
            }
            for r in batch.records
        ],
    }


def _deserialize_context_batch(payload: dict) -> ContextBatch:
    records = tuple(
        ContextRecord(
            record_id=r["record_id"],
            occurred_at=datetime.fromisoformat(r["occurred_at"]),
            content=r["content"],
            content_type=r.get("content_type", "text/plain"),
            session_id=r.get("session_id"),
            actor_id=r.get("actor_id"),
            actor_role=r.get("actor_role"),
            metadata=r.get("metadata") or {},
        )
        for r in payload["records"]
    )
    return ContextBatch(
        ingestion_id=payload["ingestion_id"],
        context_id=payload["context_id"],
        source=SourceDescriptor(
            source_type=payload["source_type"], source_external_id=payload["source_external_id"]
        ),
        records=records,
        metadata=payload.get("metadata") or {},
    )


class PostgresBatchStore:
    """§3 fix: durable counterpart to what used to live only in
    `MemoryEngine._batches` (an in-process dict, gone on restart). Two
    tables: `ingestion_batches` (one row per submitted batch, carrying
    enough of the original payload to reconstruct the exact `ContextBatch`
    a retry needs) and `ingestion_batch_chunks` (which chunk_ids belong to
    which batch_id -- the join key into `ingestion_jobs`, the system's
    already-durable per-chunk state, so batch status is *derived* from that
    real state rather than duplicated into a second, driftable copy of it).
    """

    def __init__(self, connection: object) -> None:
        self._connection = connection

    def create(self, batch: ContextBatch, chunk_ids: Sequence[tuple[str, int | None]]) -> None:
        """Idempotent: a retry re-submitting the identical `batch_id` (never
        happens today -- `retry_batch` reuses the row instead -- but kept
        idempotent defensively) is a no-op, not a conflict."""
        payload = _serialize_context_batch(batch)
        with self._connection.transaction():
            with self._connection.cursor() as cursor:
                cursor.execute(
                    """
                    INSERT INTO ingestion_batches (batch_id, context_id, submitted_payload)
                    VALUES (%s, %s, %s::jsonb)
                    ON CONFLICT (batch_id) DO NOTHING
                    """,
                    (batch.ingestion_id, batch.context_id, json.dumps(payload)),
                )
                if chunk_ids:
                    values_sql = ", ".join(["(%s, %s, %s)"] * len(chunk_ids))
                    params: list[object] = []
                    for chunk_id, turn_number in chunk_ids:
                        params.extend((batch.ingestion_id, chunk_id, turn_number))
                    cursor.execute(
                        f"""
                        INSERT INTO ingestion_batch_chunks (batch_id, chunk_id, turn_number)
                        VALUES {values_sql}
                        ON CONFLICT (batch_id, chunk_id) DO NOTHING
                        """,
                        params,
                    )

    def get_context_batch(self, batch_id: str) -> ContextBatch | None:
        """Reconstructs the exact `ContextBatch` `submit_batch` built, for
        `retry_batch` to re-submit after a process restart (when the
        in-memory copy, if any, is long gone)."""
        with self._connection.cursor() as cursor:
            cursor.execute(
                "SELECT submitted_payload FROM ingestion_batches WHERE batch_id = %s", (batch_id,)
            )
            row = cursor.fetchone()
        return _deserialize_context_batch(row[0]) if row else None

    def mark_run_error(self, batch_id: str, error: str) -> None:
        """The whole background `run_batch` call raised before producing any
        per-chunk result (distinct from a per-chunk failure, which
        `ingestion_jobs` already records) -- e.g. HydraDB/Postgres were
        unreachable for the entire call."""
        with self._connection.transaction():
            with self._connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE ingestion_batches SET run_error = %s, completed_at = now() WHERE batch_id = %s",
                    (error, batch_id),
                )

    def clear_run_error(self, batch_id: str) -> None:
        """Called at retry time so a stale whole-run error doesn't keep
        reporting `failed` once the retry starts producing real per-chunk
        state again."""
        with self._connection.transaction():
            with self._connection.cursor() as cursor:
                cursor.execute(
                    "UPDATE ingestion_batches SET run_error = NULL, completed_at = NULL WHERE batch_id = %s",
                    (batch_id,),
                )

    def get_status(self, batch_id: str) -> BatchStatus | None:
        """Returns `None` for an unknown batch_id -- callers (MemoryEngine)
        turn that into `BatchNotFoundError` -> HTTP 404, replacing the old
        "unknown batch -> pending forever" behavior. Status is aggregated
        from `ingestion_jobs` the same way `engine._batch_status_from_result`
        already buckets a same-process `BatchRunResult`, just read back from
        Postgres instead of held in memory."""
        with self._connection.cursor() as cursor:
            cursor.execute("SELECT run_error FROM ingestion_batches WHERE batch_id = %s", (batch_id,))
            row = cursor.fetchone()
            if row is None:
                return None
            run_error = row[0]
            if run_error is not None:
                return BatchStatus(batch_id=batch_id, status="failed", facts_created=0, error=run_error, retryable=True)

            cursor.execute(
                "SELECT chunk_id FROM ingestion_batch_chunks WHERE batch_id = %s ORDER BY chunk_id", (batch_id,)
            )
            chunk_ids = [r[0] for r in cursor.fetchall()]
            if not chunk_ids:
                # Row exists (submit_batch already wrote it) but the
                # background run hasn't reached chunk_store.put for even one
                # chunk yet -- genuinely still pending, not unknown.
                return BatchStatus(batch_id=batch_id, status="pending", facts_created=0, retryable=False)

            cursor.execute(
                "SELECT chunk_id, state, last_error FROM ingestion_jobs WHERE chunk_id = ANY(%s)", (chunk_ids,)
            )
            job_by_chunk = {r[0]: (r[1], r[2]) for r in cursor.fetchall()}

            cursor.execute(
                """
                SELECT chunk_id, accepted_count FROM extraction_attempts
                WHERE chunk_id = ANY(%s) ORDER BY created_at DESC
                """,
                (chunk_ids,),
            )
            facts_by_chunk: dict[str, int] = {}
            for chunk_id, accepted_count in cursor.fetchall():
                # First row per chunk_id wins (ORDER BY created_at DESC) --
                # the latest attempt, in the rare case content/extractor
                # version produced more than one row for the same chunk.
                facts_by_chunk.setdefault(chunk_id, accepted_count)

        states: list[str | None] = []
        errors: list[str] = []
        for chunk_id in chunk_ids:
            job = job_by_chunk.get(chunk_id)
            if job is None:
                states.append(None)
                continue
            state_str, last_error = job
            states.append(state_str)
            if last_error:
                errors.append(last_error)

        facts_created = sum(facts_by_chunk.values())
        if any(state is None or state in _BATCH_IN_FLIGHT_STATES for state in states):
            return BatchStatus(batch_id=batch_id, status="pending", facts_created=facts_created, retryable=False)

        state_set = set(states)
        first_error = errors[0] if errors else None
        if state_set <= {IngestionJobState.COMPLETED.value}:
            return BatchStatus(batch_id=batch_id, status="succeeded", facts_created=facts_created, retryable=False)
        if IngestionJobState.COMPLETED.value in state_set:
            return BatchStatus(
                batch_id=batch_id, status="partial", facts_created=facts_created, error=first_error, retryable=True
            )
        if state_set <= {IngestionJobState.RETRYABLE_FAILED.value}:
            return BatchStatus(
                batch_id=batch_id, status="failed", facts_created=facts_created, error=first_error, retryable=True
            )
        return BatchStatus(
            batch_id=batch_id, status="failed", facts_created=facts_created, error=first_error, retryable=False
        )
