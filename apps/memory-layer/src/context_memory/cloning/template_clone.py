"""Scenario-template -> playthrough memory-space clone (Milestone 3b of the
AI-DND bridge, ADR-7 "ingest once, clone many").

Query shapes below are the ones live-verified against this exact HydraDB
build (not the earlier, wrong assumption that a bulk/wildcard node read
would work): `RETURN` only accepts `<binding>.<property>` or `count(*)` --
no `RETURN n`, no `labels(n)`, no `id(n)`. But a *labeled, property-listed*
`MATCH (n:Fact {context_id: $ctx}) RETURN n.id AS id, n.text AS text, ...`
IS a genuine bulk, multi-row read across every matching node -- confirmed
live returning 2 rows for 2 facts, 0 rows (not an error) for zero matches.
Relationship patterns need exactly one named type per query
(`-[r:ABOUT]->`, not `-[r]->`), so this issues one bulk read per known
Fact->Entity relationship type instead of one generic edge sweep. Total
read cost is `O(node labels + edge types)` calls, not `O(facts)` -- flat
regardless of template size, not the N+1 per-fact fallback the original
Milestone-3 plan expected before this was checked against a live instance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, Sequence

from context_memory.core.graph import GraphNode, GraphRelationship, GraphWritePlan
from context_memory.core.logging import get_logger, timed_operation
from context_memory.core.ports import GraphTransport
from context_memory.ingestion.graph_writer import GraphWriter
from context_memory.ingestion.ports import GraphIdAllocator

logger = get_logger(__name__)


class FactMetadataStore(Protocol):
    """Duck-typed to `persistence.postgres.PostgresFactMetadataStore` --
    named here rather than imported from `persistence` to keep `cloning`
    dependent only on the port shape it needs, not that module's Postgres
    specifics (same reasoning `ingestion.ports` already applies to
    `GraphIdAllocator`/`JobStore`/etc.)."""

    def get_many(
        self, context_id: str, fact_ids: Sequence[int]
    ) -> dict[int, tuple[str | None, dict | None, str | None, bool]]: ...
    def put(
        self, context_id: str, fact_id: int, checkpoint: str | None, when_active: dict | None,
        visible_to_participant_id: str | None = None, hidden: bool = False,
    ) -> None: ...

# Every property graph_plan_builder.py / direct_authoring.py ever write onto
# an Entity or Fact node. Read explicitly, not wildcarded (HydraDB doesn't
# support that) -- a property this build doesn't recognize is simply
# unqueried, not silently dropped, so a future property addition to either
# writer needs a matching addition here or it won't survive a clone. Not
# hidden: the risk is the same class as any hand-maintained projection list.
_ENTITY_PROPERTIES = ("logical_key", "canonical_name", "entity_type", "description", "aliases")
_FACT_PROPERTIES = (
    "logical_key", "text", "speaker", "session_id", "memory_type", "scope_type", "scope_id",
    "predicate_key", "source_chunk_id", "source_start", "source_end", "content_hash",
    "confidence", "observed_at", "superseded_at", "valid_from", "valid_to", "created_at",
    "is_current", "archived", "object_literal",
)
# Fact -> Entity relationship types this codebase actually writes
# (graph_plan_builder.py's STATED_BY/ABOUT, direct_authoring.py's ABOUT/RELATES_TO).
# SUPERSEDES (Fact -> Fact) and HAS_TURN/HAS_ALIAS/EXTRACTED_FROM/MERGED_INTO
# involve Session/Turn/Alias nodes this template-clone scope doesn't carry
# forward -- a template has no Turns of its own, only pre-authored/extracted
# Facts and Entities (see ADR-7: authoring-time ingestion, not gameplay).
_FACT_TO_ENTITY_RELATIONSHIP_TYPES = ("ABOUT", "STATED_BY", "RELATES_TO")


@dataclass(frozen=True)
class CloneResult:
    entities_cloned: int
    facts_cloned: int
    relationships_cloned: int


def clone(
    source_context_id: str,
    target_context_id: str,
    allocator: GraphIdAllocator,
    graph_writer: GraphWriter,
    hydra_transport: GraphTransport,
    fact_metadata_store: FactMetadataStore | None = None,
) -> CloneResult:
    """Copies every Entity/Fact node and Fact->Entity edge under
    `source_context_id` into a fresh `target_context_id`. Idempotent per
    node/edge (same allocator + same GraphWriter MERGE semantics every other
    writer in this codebase relies on) -- re-running a clone into the same
    target is a no-op replay, not a duplicate.

    `fact_metadata_store`, when given, also clones each fact's
    `pre_authored_fact_metadata` row (Milestones 4-5's `when_active`/
    `checkpoint`) onto its newly-allocated fact_id -- that table is keyed by
    (context_id, fact_id), so without this step a cloned playthrough's facts
    would carry ids the template's metadata rows never heard of.
    """
    with timed_operation(
        logger, "template_clone.clone", {"source_context_id": source_context_id, "target_context_id": target_context_id}
    ) as ctx:
        entity_rows = _read_labeled(hydra_transport, "Entity", source_context_id, _ENTITY_PROPERTIES)
        fact_rows = _read_labeled(hydra_transport, "Fact", source_context_id, _FACT_PROPERTIES)

        entity_nodes, old_to_new_entity_id = _clone_nodes(
            entity_rows, "Entity", "entity", target_context_id, allocator
        )
        fact_nodes, old_to_new_fact_id = _clone_nodes(
            fact_rows, "Fact", "fact", target_context_id, allocator
        )

        relationships = []
        for relationship_type in _FACT_TO_ENTITY_RELATIONSHIP_TYPES:
            edge_rows = _read_fact_to_entity_edges(hydra_transport, relationship_type, source_context_id)
            relationships.extend(_clone_edges(
                edge_rows, relationship_type, old_to_new_fact_id, old_to_new_entity_id,
                target_context_id, allocator,
            ))

        nodes = tuple(entity_nodes) + tuple(fact_nodes)
        if nodes or relationships:
            plan = GraphWritePlan(
                context_id=target_context_id,
                plan_key=f"plan:clone:{source_context_id}->{target_context_id}",
                nodes=nodes, relationships=tuple(relationships),
            )
            graph_writer.write(plan)

        if fact_metadata_store is not None and old_to_new_fact_id:
            _clone_fact_metadata(fact_metadata_store, source_context_id, target_context_id, old_to_new_fact_id)

        result = CloneResult(
            entities_cloned=len(entity_nodes), facts_cloned=len(fact_nodes), relationships_cloned=len(relationships)
        )
        ctx["entities_cloned"] = result.entities_cloned
        ctx["facts_cloned"] = result.facts_cloned
        ctx["relationships_cloned"] = result.relationships_cloned
        return result


def _clone_fact_metadata(
    fact_metadata_store: FactMetadataStore, source_context_id: str, target_context_id: str,
    old_to_new_fact_id: dict[int, int],
) -> None:
    metadata = fact_metadata_store.get_many(source_context_id, list(old_to_new_fact_id.keys()))
    for old_fact_id, (checkpoint, when_active, visible_to_participant_id, hidden) in metadata.items():
        new_fact_id = old_to_new_fact_id.get(old_fact_id)
        if new_fact_id is None:
            continue
        # §5 fix: a template fact authored as participant-restricted stays
        # restricted in the clone -- not carrying this forward would have
        # silently widened every cloned playthrough's visibility to
        # everyone, the opposite of what the template author specified.
        # Same reasoning for `hidden`: a secret stays a secret in the clone.
        fact_metadata_store.put(
            target_context_id, new_fact_id, checkpoint, when_active, visible_to_participant_id, hidden,
        )


def _read_labeled(
    hydra_transport: GraphTransport, label: str, context_id: str, properties: tuple[str, ...]
) -> list[dict[str, object]]:
    projection = ", ".join(f"n.{prop} AS {prop}" for prop in properties)
    cypher = f"MATCH (n:{label} {{context_id: $context_id}}) RETURN n.id AS id, {projection}"
    return list(hydra_transport.read(cypher, {"context_id": context_id}, None))


def _read_fact_to_entity_edges(
    hydra_transport: GraphTransport, relationship_type: str, context_id: str
) -> list[dict[str, object]]:
    cypher = (
        f"MATCH (f:Fact {{context_id: $context_id}})-[r:{relationship_type}]->(e:Entity) "
        "RETURN f.id AS src, e.id AS dst"
    )
    return list(hydra_transport.read(cypher, {"context_id": context_id}, None))


def _clone_nodes(
    rows: list[dict[str, object]], label: str, node_kind: str, target_context_id: str, allocator: GraphIdAllocator
) -> tuple[list[GraphNode], dict[int, int]]:
    nodes: list[GraphNode] = []
    old_to_new_id: dict[int, int] = {}
    for row in rows:
        old_id = int(row["id"])
        logical_key = row["logical_key"]
        if not logical_key:
            # Defensive, not expected: every writer in this codebase always
            # sets logical_key. A row missing it can't be re-allocated a
            # stable id, so it's skipped rather than crashing the whole clone.
            logger.warning("template_clone: %s node id=%s has no logical_key, skipping", label, old_id)
            continue
        new_id = allocator.allocate_graph_id(node_kind, target_context_id, logical_key)
        old_to_new_id[old_id] = new_id
        properties = _drop_nulls(row, exclude=("id",))
        properties["context_id"] = target_context_id
        nodes.append(GraphNode(new_id, label, logical_key, properties))
    return nodes, old_to_new_id


def _clone_edges(
    rows: list[dict[str, object]], relationship_type: str, old_to_new_fact_id: dict[int, int],
    old_to_new_entity_id: dict[int, int], target_context_id: str, allocator: GraphIdAllocator,
) -> list[GraphRelationship]:
    relationships = []
    for row in rows:
        old_src, old_dst = int(row["src"]), int(row["dst"])
        new_src = old_to_new_fact_id.get(old_src)
        new_dst = old_to_new_entity_id.get(old_dst)
        if new_src is None or new_dst is None:
            # The Fact/Entity node this edge points to failed its own clone
            # (e.g. missing logical_key, see _clone_nodes) -- drop the
            # now-dangling edge rather than write a relationship to a node
            # that was never cloned.
            continue
        logical_key = f"{relationship_type.lower()}:{new_src}:{new_dst}"
        graph_id = allocator.allocate_graph_id(relationship_type.lower(), target_context_id, logical_key)
        relationships.append(GraphRelationship(
            graph_id, relationship_type, logical_key, new_src, new_dst, "Fact", "Entity",
            {"context_id": target_context_id},
        ))
    return relationships


def _drop_nulls(row: dict[str, object], exclude: tuple[str, ...]) -> dict[str, object]:
    """`GraphNode.properties` values must be scalar (core/graph.py) -- `None`
    isn't one, so a property a source node never set (read back as `null`)
    must be dropped, not passed through, the same way `_scalar_properties`
    (graph_plan_builder.py) already filters at write time."""
    return {key: value for key, value in row.items() if key not in exclude and value is not None}
