"""Bulk HydraDB read for `EntityRegistry`'s lazy per-context hydration (see
`EntityRegistry._hydrate`). Entity nodes carry no `aliases` property --
aliases live on separate `Alias` nodes reached via `HAS_ALIAS` edges (see
`graph_plan_builder.py`'s `_entity_node`/`_alias_records`) -- so this reads
both and joins them by graph id.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from context_memory.core.logging import get_logger, timed_operation
from context_memory.core.ports import GraphTransport

logger = get_logger(__name__)

_READ_ENTITIES_CYPHER = (
    "MATCH (n:Entity {context_id: $context_id}) "
    "RETURN n.id AS id, n.canonical_name AS canonical_name, n.entity_type AS entity_type"
)
_READ_ALIASES_CYPHER = (
    "MATCH (e:Entity {context_id: $context_id})-[r:HAS_ALIAS]->(a:Alias) "
    "RETURN e.id AS entity_id, a.canonical_alias AS canonical_alias"
)


@dataclass(frozen=True)
class HydratedEntity:
    graph_id: int
    canonical_name: str
    entity_type: str
    aliases: tuple[str, ...]


class HydraEntityHydrator:
    """`EntityRegistry`'s `EntityHydrator` port, backed by a live HydraDB
    query. Mirrors `fact_lookup.HydraFactLookup`'s posture: a failed read
    degrades to "nothing known," it never blocks resolution.
    """

    def __init__(self, transport: GraphTransport) -> None:
        self._transport = transport

    def fetch(self, context_id: str) -> list[HydratedEntity]:
        with timed_operation(
            logger, "entity_hydration.fetch", {"context_id": context_id}
        ) as ctx:
            try:
                entity_rows = self._transport.read(
                    _READ_ENTITIES_CYPHER, {"context_id": context_id}, None
                )
                alias_rows = self._transport.read(
                    _READ_ALIASES_CYPHER, {"context_id": context_id}, None
                )
            except Exception as error:
                logger.warning(
                    "entity_hydration.fetch failed for context %s: %s",
                    context_id,
                    error,
                )
                return []

            aliases_by_entity_id = self._group_aliases(alias_rows)
            entities = self._build_entities(entity_rows, aliases_by_entity_id)
            ctx["entities"] = len(entities)
            return entities

    def _group_aliases(
        self, alias_rows: Sequence[dict[str, object]]
    ) -> dict[str, list[str]]:
        grouped: dict[str, list[str]] = {}
        for row in alias_rows:
            entity_id = row.get("entity_id")
            canonical_alias = row.get("canonical_alias")
            if not entity_id or not canonical_alias:
                continue
            grouped.setdefault(str(entity_id), []).append(str(canonical_alias))
        return grouped

    def _build_entities(
        self,
        entity_rows: Sequence[dict[str, object]],
        aliases_by_entity_id: dict[str, list[str]],
    ) -> list[HydratedEntity]:
        entities: list[HydratedEntity] = []
        for row in entity_rows:
            entity = self._build_one_entity(row, aliases_by_entity_id)
            if entity is not None:
                entities.append(entity)
        return entities

    def _build_one_entity(
        self, row: dict[str, object], aliases_by_entity_id: dict[str, list[str]]
    ) -> HydratedEntity | None:
        entity_id = row.get("id")
        canonical_name = row.get("canonical_name")
        entity_type = row.get("entity_type")
        if not entity_id or not canonical_name or not entity_type:
            logger.warning("entity_hydration: skipping malformed entity row %r", row)
            return None
        try:
            graph_id = int(entity_id)
        except (TypeError, ValueError):
            logger.warning(
                "entity_hydration: skipping entity row with non-integer id %r",
                entity_id,
            )
            return None
        aliases = tuple(aliases_by_entity_id.get(str(entity_id), ()))
        return HydratedEntity(graph_id, str(canonical_name), str(entity_type), aliases)
