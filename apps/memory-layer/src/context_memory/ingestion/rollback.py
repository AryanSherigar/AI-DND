"""Phase 6: single-timeline rollback. Loading a save point rewinds a context's
active timeline -- anything written after it becomes archived, not kept alive
in parallel (this is classic save/load, not concurrent branching; see the
harness plan's Phase 6 decision for why that scope was chosen).

Reuses the existing bitemporal-supersession write path (`GraphWriter` +
`PostgresGraphManifestStore`'s `NODE_MUTABLE_PROPERTIES` merge) rather than a
parallel mechanism: a rollback is, mechanically, just another batch of
partial Fact-node property updates -- the same shape `GraphPlanBuilder`
already writes every time a new fact supersedes a prior one.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone

from context_memory.core.graph import GraphNode, GraphWritePlan
from context_memory.core.journal import JournalContext, StepJournal
from context_memory.core.logging import get_logger, timed_operation
from context_memory.ingestion.graph_writer import GraphWriter

logger = get_logger(__name__)

_OPEN_SENTINEL = 9999999999  # "no upper bound" -- matches graph_plan_builder.py's own sentinel


def walk_restore_targets(archived_ids: list[str], superseded_by: dict[str, str]) -> set[str]:
    """For each archived fact, walks `superseded_by` (new_fact -> the fact it
    superseded) back past any link that is itself archived. A chain that
    happened entirely after the cutoff must restore its pre-cutoff ancestor,
    not an intermediate archived fact -- e.g. F1 -> F2 -> F3 all created after
    the save point restores F1's own prior (or nothing, if F1 had none), not
    F1 or F2. Pure and DB-free so this is the one part of rollback worth unit
    testing directly, independent of Postgres/HydraDB."""
    archived_set = set(archived_ids)
    restore_set: set[str] = set()
    for candidate_id in archived_ids:
        target = superseded_by.get(candidate_id)
        while target is not None and target in archived_set:
            target = superseded_by.get(target)
        if target is not None:
            restore_set.add(target)
    return restore_set


@dataclass(frozen=True)
class SavePoint:
    save_id: str
    context_id: str
    session_id: str | None
    label: str | None
    cutoff_observed_at: datetime
    created_at: datetime


class SavePointStore:
    """Postgres-backed. A save point is just a marker on the existing
    `observed_at` (knowledge-time) and `created_at` (wall-clock) timelines --
    creating one writes no graph state at all."""

    def __init__(self, connection: object) -> None:
        self._connection = connection

    def create(self, context_id: str, session_id: str | None = None, label: str | None = None) -> SavePoint:
        save_id = f"save-{uuid.uuid4().hex[:16]}"
        now = datetime.now(timezone.utc)
        with self._connection.transaction():
            with self._connection.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO save_points (save_id, context_id, session_id, label, cutoff_observed_at, created_at) "
                    "VALUES (%s, %s, %s, %s, %s, %s)",
                    (save_id, context_id, session_id, label, now, now),
                )
        return SavePoint(save_id, context_id, session_id, label, now, now)

    def get(self, save_id: str) -> SavePoint | None:
        with self._connection.cursor() as cursor:
            cursor.execute(
                "SELECT save_id, context_id, session_id, label, cutoff_observed_at, created_at "
                "FROM save_points WHERE save_id = %s",
                (save_id,),
            )
            row = cursor.fetchone()
        return SavePoint(*row) if row else None

    def list_for_context(self, context_id: str) -> list[SavePoint]:
        with self._connection.cursor() as cursor:
            cursor.execute(
                "SELECT save_id, context_id, session_id, label, cutoff_observed_at, created_at "
                "FROM save_points WHERE context_id = %s ORDER BY created_at DESC",
                (context_id,),
            )
            rows = cursor.fetchall()
        return [SavePoint(*row) for row in rows]


@dataclass(frozen=True)
class RollbackResult:
    save_id: str
    archived_fact_ids: tuple[str, ...]
    restored_fact_ids: tuple[str, ...]


class RollbackService:
    def __init__(self, connection: object, graph_writer: GraphWriter, journal: StepJournal | None = None) -> None:
        self._connection = connection
        self._graph_writer = graph_writer
        self._journal = journal

    def rollback_to(self, save_point: SavePoint) -> RollbackResult:
        start = time.monotonic()
        with timed_operation(
            logger, "rollback.apply", {"context_id": save_point.context_id, "save_id": save_point.save_id}
        ) as ctx:
            archived_ids = self._find_archived_candidates(save_point)
            restored_ids, restored_valid_to = self._find_restored_candidates(save_point.context_id, archived_ids)
            id_to_graph_id = self._resolve_graph_ids(
                save_point.context_id, [*archived_ids, *restored_ids]
            )

            self._apply_graph_updates(save_point.context_id, archived_ids, restored_ids, restored_valid_to, id_to_graph_id)
            self._apply_postgres_cleanup(save_point, archived_ids, restored_ids, id_to_graph_id)

            ctx["archived_count"] = len(archived_ids)
            ctx["restored_count"] = len(restored_ids)
            if self._journal is not None:
                self._journal.record(
                    step_type="rollback.apply", call_role="rollback", idempotency_key=f"rollback:{save_point.save_id}",
                    request_payload={"save_id": save_point.save_id, "cutoff_observed_at": save_point.cutoff_observed_at.isoformat()},
                    response_payload={"archived_fact_ids": list(archived_ids), "restored_fact_ids": list(restored_ids)},
                    outcome="ok", elapsed_ms=(time.monotonic() - start) * 1000,
                    context=JournalContext(context_id=save_point.context_id, session_id=save_point.session_id),
                )
            return RollbackResult(save_point.save_id, tuple(archived_ids), tuple(restored_ids))

    def _find_archived_candidates(self, save_point: SavePoint) -> list[str]:
        """Every fact whose knowledge-time (`observed_at`) falls after the save
        point's cutoff never existed on this rolled-back timeline."""
        with self._connection.cursor() as cursor:
            cursor.execute(
                "SELECT c.candidate_id FROM extracted_memory_candidates c "
                "JOIN extraction_attempts a ON c.attempt_id = a.attempt_id "
                "WHERE a.context_id = %s AND c.observed_at > %s",
                (save_point.context_id, save_point.cutoff_observed_at),
            )
            return [row[0] for row in cursor.fetchall()]

    def _find_restored_candidates(self, context_id: str, archived_ids: list[str]) -> tuple[list[str], dict[str, datetime | None]]:
        """A fact superseded only by something now being archived must become
        current again. Walks the SUPERSEDES chain (recovered from
        `graph_write_manifests`'s relationship logical_keys, `supersedes:
        {new_candidate_id}:{prior_fact_id}`) past any link that is itself
        archived -- a chain that happened entirely after the cutoff must
        restore its pre-cutoff ancestor, not an intermediate archived fact."""
        if not archived_ids:
            return [], {}
        archived_set = set(archived_ids)
        with self._connection.cursor() as cursor:
            cursor.execute(
                "SELECT logical_key FROM graph_write_manifests "
                "WHERE context_id = %s AND record_kind = 'relationship' AND logical_key LIKE 'supersedes:%%'",
                (context_id,),
            )
            rows = cursor.fetchall()
        superseded_by: dict[str, str] = {}
        for (logical_key,) in rows:
            _, new_candidate_id, prior_fact_id = logical_key.split(":", 2)
            superseded_by[new_candidate_id] = prior_fact_id

        restore_set = walk_restore_targets(archived_ids, superseded_by)

        if not restore_set:
            return [], {}
        with self._connection.cursor() as cursor:
            cursor.execute(
                "SELECT candidate_id, valid_to FROM extracted_memory_candidates "
                "WHERE candidate_id = ANY(%s)",
                (list(restore_set),),
            )
            valid_to_by_id = {row[0]: row[1] for row in cursor.fetchall()}
        return list(restore_set), valid_to_by_id

    def _resolve_graph_ids(self, context_id: str, candidate_ids: list[str]) -> dict[str, int]:
        if not candidate_ids:
            return {}
        logical_keys = [f"fact:{cid}" for cid in candidate_ids]
        with self._connection.cursor() as cursor:
            cursor.execute(
                "SELECT logical_key, graph_id FROM graph_id_registry "
                "WHERE node_kind = 'fact' AND context_id = %s AND logical_key = ANY(%s)",
                (context_id, logical_keys),
            )
            rows = cursor.fetchall()
        return {logical_key.removeprefix("fact:"): int(graph_id) for logical_key, graph_id in rows}

    def _apply_graph_updates(
        self, context_id: str, archived_ids: list[str], restored_ids: list[str],
        restored_valid_to: dict[str, datetime | None], id_to_graph_id: dict[str, int],
    ) -> None:
        nodes: list[GraphNode] = []
        for candidate_id in archived_ids:
            graph_id = id_to_graph_id.get(candidate_id)
            if graph_id is None:
                continue
            logical_key = f"fact:{candidate_id}"
            nodes.append(GraphNode(graph_id, "Fact", logical_key, {
                "context_id": context_id, "logical_key": logical_key, "archived": True,
            }))
        for candidate_id in restored_ids:
            graph_id = id_to_graph_id.get(candidate_id)
            if graph_id is None:
                continue
            logical_key = f"fact:{candidate_id}"
            original_valid_to = restored_valid_to.get(candidate_id)
            nodes.append(GraphNode(graph_id, "Fact", logical_key, {
                "context_id": context_id, "logical_key": logical_key,
                "is_current": True, "superseded_at": _OPEN_SENTINEL,
                "valid_to": int(original_valid_to.timestamp()) if original_valid_to else _OPEN_SENTINEL,
            }))
        if not nodes:
            return
        save_id_hint = f"{context_id}:{len(archived_ids)}:{len(restored_ids)}"
        plan = GraphWritePlan(context_id, f"rollback:{save_id_hint}:{uuid.uuid4().hex[:8]}", tuple(nodes), ())
        self._graph_writer.write(plan)

    def _apply_postgres_cleanup(
        self, save_point: SavePoint, archived_ids: list[str], restored_ids: list[str], id_to_graph_id: dict[str, int],
    ) -> None:
        with self._connection.transaction():
            with self._connection.cursor() as cursor:
                cursor.execute(
                    "DELETE FROM conversation_buffer WHERE context_id = %s AND created_at > %s",
                    (save_point.context_id, save_point.created_at),
                )
                if archived_ids:
                    cursor.execute(
                        "UPDATE memory_embeddings SET is_active = false "
                        "WHERE context_id = %s AND subject_kind = 'fact' AND subject_id = ANY(%s)",
                        (save_point.context_id, archived_ids),
                    )
                    cursor.execute(
                        "UPDATE fact_search_index SET is_active = false WHERE context_id = %s AND fact_id = ANY(%s)",
                        (save_point.context_id, archived_ids),
                    )
                if restored_ids:
                    cursor.execute(
                        "UPDATE memory_embeddings SET is_active = true "
                        "WHERE context_id = %s AND subject_kind = 'fact' AND subject_id = ANY(%s)",
                        (save_point.context_id, restored_ids),
                    )
                    cursor.execute(
                        "UPDATE fact_search_index SET is_active = true WHERE context_id = %s AND fact_id = ANY(%s)",
                        (save_point.context_id, restored_ids),
                    )
