"""Ingestion-side graph batch construction and local HydraDB write orchestration.

Bare `§N` references below are sections of docs/fixes_and_evaluation_findings.md.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Sequence
from hashlib import sha256

from context_memory.core.graph import GraphNode, GraphRelationship, GraphWritePlan
from context_memory.core.logging import get_logger, timed_operation
from context_memory.ingestion.ports import GraphManifestStore, GraphTransport

logger = get_logger(__name__)


class GraphWriter:
    # HydraDB's admission control rejects any single `UNWIND $rows` write
    # once `rows` exceeds 1024 items -- confirmed live: grouping 100 chunks
    # via `write_many` pushed the Fact-node bucket to 1236 rows and the
    # whole physical call was rejected with HTTP 429
    # ("client_query_batch_items rejected by admission control: actual 1236
    # exceeds limit 1024"), which failed *every* chunk in that group at
    # once (one physical call, no way to tell which chunk's rows were the
    # problem -- see `_fail_pending` in orchestrator.py). 900 leaves real
    # margin below the server's actual limit, not a number picked to sit
    # just under it. This caps rows per physical call regardless of how
    # many chunks `write_batch_size` groups together, so tuning that number
    # for I/O-round-trip efficiency (docs/fixes_and_evaluation_findings.md
    # §3.9) can never reintroduce this failure mode even if a batch of
    # turns turns out far more fact-dense than the ones this was tuned on.
    DEFAULT_MAX_ROWS_PER_WRITE = 900

    def __init__(self, manifest_store: GraphManifestStore, transport: GraphTransport, max_rows_per_write: int = DEFAULT_MAX_ROWS_PER_WRITE) -> None:
        self._manifest_store = manifest_store
        self._transport = transport
        self._max_rows_per_write = max_rows_per_write

    def write(self, plan: GraphWritePlan) -> tuple[str, ...]:
        with timed_operation(logger, "graph_writer.write", {"plan_key": plan.plan_key, "nodes": len(plan.nodes), "relationships": len(plan.relationships)}) as ctx:
            self._manifest_store.register(plan)
            bookmarks: list[str] = []
            nodes: dict[tuple[str, tuple[str, ...]], list[GraphNode]] = defaultdict(list)
            relationships: dict[tuple[str, str, str, tuple[str, ...]], list[GraphRelationship]] = defaultdict(list)
            for node in plan.nodes:
                nodes[(node.label, tuple(sorted(node.properties)))].append(node)
            for relationship in plan.relationships:
                relationships[(relationship.relationship_type, relationship.source_label, relationship.destination_label, tuple(sorted(relationship.properties)))].append(relationship)
            for (label, property_names), group in nodes.items():
                rows = self._node_rows(group)
                bookmarks.extend(self._flush(self._node_query(label, property_names), rows, lambda r: self._key(plan, f"node-{label}-{'-'.join(property_names)}", r)))
            for (relationship_type, source_label, destination_label, property_names), group in relationships.items():
                rows = self._relationship_rows(group)
                bookmarks.extend(self._flush(self._relationship_query(relationship_type, source_label, destination_label, property_names), rows, lambda r: self._key(plan, f"relationship-{relationship_type}-{source_label}-{destination_label}-{'-'.join(property_names)}", r)))
            ctx["bookmarks_received"] = len(bookmarks)
            return tuple(bookmarks)

    def verify(self, plan: GraphWritePlan) -> bool:
        """§8 fix: independent post-write confirmation that `plan`'s nodes
        are actually readable back from HydraDB -- not just that `write()`'s
        call didn't raise. `manifest_store.register()` alone can't answer
        this: it's called *before* the physical `transport.write()` in both
        `write()`/`write_many()`, so a manifest row only proves a write was
        attempted with this exact payload, not that HydraDB durably has it.

        Bulk, one read per distinct node label in `plan` (not one per node)
        -- the same `MATCH (n:{label} {context_id: $context_id}) RETURN
        n.id AS id` shape `cloning.template_clone._read_labeled` already
        uses, live-verified against this HydraDB build's real read grammar
        (see that module's docstring for the rejected alternatives).
        Relationships are not independently re-read (this build's parameter/
        pattern support makes a bulk edge-existence check materially more
        expensive for comparatively little extra signal beyond the node
        check) -- documented scope, not a silent gap: a relationship whose
        endpoint nodes both verified but the edge itself silently failed to
        write is not caught here.
        """
        if not plan.nodes:
            return True
        ids_by_label: dict[str, set[int]] = defaultdict(set)
        for node in plan.nodes:
            ids_by_label[node.label].add(node.graph_id)
        for label, expected_ids in ids_by_label.items():
            cypher = f"MATCH (n:{label} {{context_id: $context_id}}) RETURN n.id AS id"
            try:
                rows = self._transport.read(cypher, {"context_id": plan.context_id}, None)
            except Exception as error:
                logger.warning("graph_writer.verify: read failed for label %s, plan %s: %s", label, plan.plan_key, error)
                return False
            found_ids = {int(row["id"]) for row in rows if row.get("id") is not None}
            missing = expected_ids - found_ids
            if missing:
                logger.warning(
                    "graph_writer.verify: %d %s node(s) missing after write for plan %s: %s",
                    len(missing), label, plan.plan_key, missing,
                )
                return False
        return True

    def write_many(self, plans: Sequence[GraphWritePlan]) -> tuple[str, ...]:
        """Same write as `write()`, batched across multiple chunks' plans
        instead of one `write()` call per chunk.

        Live-verified this session (docs/fixes_and_evaluation_findings.md
        §3.3) that threading `write()`'s per-bucket calls does *not* help --
        HydraDB serializes every write to a `cell_id` through one server-side
        mutex lane regardless of client concurrency, confirmed against the
        engine's own Rust source. Fewer, bigger calls is the lever that
        actually works there, the same lesson §3.2 already proved for
        Postgres: merge the SAME (label, property_names) /
        (type, source_label, destination_label, property_names) buckets
        *across* every plan in `plans` before writing, so N chunks' worth of
        node/relationship writes become one bucket set's worth of `UNWIND`
        calls (bounded by the number of distinct node/edge shapes, typically
        ~7-8, not by how many chunks are in the group) instead of N times
        that many.

        Idempotency is unaffected: every plan is still registered with
        `manifest_store` individually, under its own `plan_key`, exactly as
        `write()` would register it alone -- a solo retry of one chunk from
        this group later still checks against the same per-chunk manifest
        entry it always would. Only the *physical* write calls are merged;
        `MERGE (n {id: row.id})` is idempotent per node id regardless of
        which call or what order the row arrived in, so combining rows from
        different chunks into the same `UNWIND` batch changes nothing about
        what ends up written -- confirmed against the write-ordering
        constraint too: this still writes every node bucket (across the
        whole group) before any relationship bucket (across the whole
        group), so a relationship added in this group can always `MATCH`
        the node it references, the same guarantee `write()` gives within
        one chunk.
        """
        if not plans:
            return ()
        if len(plans) == 1:
            return self.write(plans[0])

        with timed_operation(logger, "graph_writer.write_many", {"plan_count": len(plans), "nodes": sum(len(p.nodes) for p in plans), "relationships": sum(len(p.relationships) for p in plans)}) as ctx:
            for plan in plans:
                self._manifest_store.register(plan)

            bookmarks: list[str] = []
            nodes: dict[tuple[str, tuple[str, ...]], list[GraphNode]] = defaultdict(list)
            relationships: dict[tuple[str, str, str, tuple[str, ...]], list[GraphRelationship]] = defaultdict(list)
            for plan in plans:
                for node in plan.nodes:
                    nodes[(node.label, tuple(sorted(node.properties)))].append(node)
                for relationship in plan.relationships:
                    relationships[(relationship.relationship_type, relationship.source_label, relationship.destination_label, tuple(sorted(relationship.properties)))].append(relationship)

            write_calls = 0
            for (label, property_names), group in nodes.items():
                rows = self._node_rows(group)
                flushed = self._flush(self._node_query(label, property_names), rows, lambda r: self._key_many(plans, f"node-{label}-{'-'.join(property_names)}", r))
                bookmarks.extend(flushed)
                write_calls += max(1, -(-len(rows) // self._max_rows_per_write)) if rows else 0
            for (relationship_type, source_label, destination_label, property_names), group in relationships.items():
                rows = self._relationship_rows(group)
                flushed = self._flush(self._relationship_query(relationship_type, source_label, destination_label, property_names), rows, lambda r: self._key_many(plans, f"relationship-{relationship_type}-{source_label}-{destination_label}-{'-'.join(property_names)}", r))
                bookmarks.extend(flushed)
                write_calls += max(1, -(-len(rows) // self._max_rows_per_write)) if rows else 0
            ctx["bookmarks_received"] = len(bookmarks)
            ctx["write_calls"] = write_calls
            return tuple(bookmarks)

    def _flush(self, query: str, rows: list[dict[str, object]], key_fn) -> list[str]:
        """Writes `rows` via `query`, splitting into sub-batches of at most
        `self._max_rows_per_write` each -- see `DEFAULT_MAX_ROWS_PER_WRITE`'s
        comment for why this cap exists. `key_fn(rows_subset)` computes a
        real, content-addressed idempotency key for whatever subset is
        actually being sent, so a split write never reuses one key for two
        different payloads -- when nothing needs splitting (the overwhelming
        majority of calls) this is exactly one call with exactly the same
        key `write()` always computed, unchanged behavior.
        """
        if not rows:
            return []
        bookmarks: list[str] = []
        for start in range(0, len(rows), self._max_rows_per_write):
            sub_rows = rows[start : start + self._max_rows_per_write]
            bookmark = self._transport.write(query, sub_rows, key_fn(sub_rows))
            if bookmark:
                bookmarks.append(bookmark)
        return bookmarks

    @staticmethod
    def _node_query(label: str, property_names: tuple[str, ...]) -> str:
        assignments = ", ".join(f"n.{name} = row.{name}" for name in property_names)
        return f"UNWIND $rows AS row MERGE (n {{id: row.id}}) SET n:{label}, {assignments}"

    @staticmethod
    def _relationship_query(relationship_type: str, source_label: str, destination_label: str, property_names: tuple[str, ...]) -> str:
        assignments = ", ".join(f"r.{name} = row.{name}" for name in property_names)
        return f"UNWIND $rows AS row MATCH (s:{source_label} {{id: row.source_id}}), (d:{destination_label} {{id: row.destination_id}}) MERGE (s)-[r:{relationship_type} {{id: row.id}}]->(d) SET {assignments}"

    # Two different new facts, in the same write-batch, can both supersede the
    # SAME prior fact -- each carries its own superseded_at/valid_to for that
    # one vertex, and sending both rows in one UNWIND hit HydraDB HTTP 400
    # ("conflicting metadata values for vertex N property superseded_at"),
    # losing the whole bucket (docs/fixes_and_evaluation_findings.md §10.4/§13).
    # The prior became invalid at the FIRST superseding fact, so MIN is the
    # semantically correct merge for these two fields.
    _MIN_MERGE_PROPERTIES = frozenset({"superseded_at", "valid_to"})

    @staticmethod
    def _dedupe_nodes(nodes: list[GraphNode]) -> list[GraphNode]:
        if len(nodes) <= 1:
            return nodes
        by_id: dict[int, GraphNode] = {}
        for node in nodes:
            existing = by_id.get(node.graph_id)
            if existing is None:
                by_id[node.graph_id] = node
                continue
            merged: dict[str, object] = dict(existing.properties)
            for key, value in node.properties.items():
                if key not in merged or merged[key] == value:
                    merged[key] = value
                    continue
                if key in GraphWriter._MIN_MERGE_PROPERTIES:
                    try:
                        merged[key] = min(merged[key], value)
                        continue
                    except TypeError:
                        pass
                # Unexpected -- every node here shares a deterministic
                # graph_id, so a real conflict outside the two temporal
                # fields means something else differs. Keep the later value
                # rather than raising, so this degrades to a stale property
                # instead of losing the whole batch again.
                logger.warning(
                    "graph_writer: conflicting %s for vertex %s (%s vs %s) in one write batch -- keeping the later value",
                    key, node.graph_id, merged[key], value,
                )
                merged[key] = value
            by_id[node.graph_id] = GraphNode(node.graph_id, node.label, node.logical_key, merged)
        return list(by_id.values())

    @staticmethod
    def _node_rows(nodes: list[GraphNode]) -> list[dict[str, object]]:
        return [{"id": node.graph_id, **dict(node.properties)} for node in GraphWriter._dedupe_nodes(nodes)]

    @staticmethod
    def _relationship_rows(relationships: list[GraphRelationship]) -> list[dict[str, object]]:
        return [{"id": item.graph_id, "source_id": item.source_id, "destination_id": item.destination_id, **dict(item.properties)} for item in relationships]

    @staticmethod
    def _key(plan: GraphWritePlan, phase: str, rows: list[dict[str, object]] | None = None) -> str:
        import json
        payload_bytes = json.dumps(rows, sort_keys=True, default=str).encode() if rows is not None else b""
        return f"context-memory-{sha256(f'{plan.context_id}\x00{plan.plan_key}\x00{phase}\x00'.encode() + payload_bytes).hexdigest()}"

    @staticmethod
    def _key_many(plans: Sequence[GraphWritePlan], phase: str, rows: list[dict[str, object]] | None = None) -> str:
        """Same idempotency-key shape as `_key`, but for a bucket merged
        across several plans -- hashes in every constituent `plan_key`
        (sorted, so call order never changes the key) instead of one. This
        is only the HTTP-level idempotency key HydraDB uses for the write
        call itself; the actual replay-safety guarantee (`manifest_store`)
        is unaffected and still keyed per plan, see `write_many`'s docstring.
        """
        import json
        payload_bytes = json.dumps(rows, sort_keys=True, default=str).encode() if rows is not None else b""
        plan_keys = ",".join(sorted(plan.plan_key for plan in plans))
        context_id = plans[0].context_id if plans else ""
        return f"context-memory-{sha256(f'{context_id}\x00{plan_keys}\x00{phase}\x00'.encode() + payload_bytes).hexdigest()}"
