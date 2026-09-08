"""Shared Alias-node/HAS_ALIAS-edge construction for both ingestion paths --
runtime extraction (`graph_plan_builder.GraphPlanBuilder._alias_records`) and
master-mode direct authoring (`direct_authoring.write_entity`).

NEW-HIGH-03 fix: direct authoring used to store aliases as a flat
comma-joined string property on the Entity node instead of these Alias
nodes/HAS_ALIAS edges, which `entity_hydration.HydraEntityHydrator` never
read (it only follows HAS_ALIAS) -- author-defined aliases were silently
dropped on every rehydration. Extracting the id-generation scheme here once
means both writers produce identical, drift-proof Alias/HAS_ALIAS shapes.
"""

from __future__ import annotations

from collections.abc import Sequence

from context_memory.core.graph import GraphNode, GraphRelationship
from context_memory.ingestion.ports import GraphIdAllocator


def alias_records(
    context_id: str,
    entity_graph_id: int,
    aliases: Sequence[str],
    allocator: GraphIdAllocator,
) -> list[tuple[GraphNode, GraphRelationship]]:
    records: list[tuple[GraphNode, GraphRelationship]] = []
    for alias in aliases:
        alias_logical_key = f"alias:{alias}:{entity_graph_id}"
        alias_graph_id = allocator.allocate_graph_id(
            "alias", context_id, alias_logical_key
        )
        alias_node = GraphNode(
            alias_graph_id,
            "Alias",
            alias_logical_key,
            {
                "context_id": context_id,
                "logical_key": alias_logical_key,
                "canonical_alias": alias,
                "entity_graph_id": entity_graph_id,
            },
        )
        edge_logical_key = f"has_alias:{entity_graph_id}:{alias}"
        edge_graph_id = allocator.allocate_graph_id(
            "has_alias", context_id, edge_logical_key
        )
        has_alias = GraphRelationship(
            edge_graph_id,
            "HAS_ALIAS",
            edge_logical_key,
            entity_graph_id,
            alias_graph_id,
            "Entity",
            "Alias",
            {"context_id": context_id},
        )
        records.append((alias_node, has_alias))
    return records
