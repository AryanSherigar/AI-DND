"""`HydraEntityHydrator` -- bulk-reads a context's existing Entity/Alias
nodes from HydraDB for `EntityRegistry`'s lazy per-context hydration. Same
content-sniffing fake transport approach `test_template_clone.py` uses.
"""

from __future__ import annotations

import unittest

from context_memory.ingestion.entity_hydration import (
    HydraEntityHydrator,
    HydratedEntity,
)


class FakeHydraTransport:
    def __init__(self, entity_rows=(), alias_rows=()):
        self.entity_rows = list(entity_rows)
        self.alias_rows = list(alias_rows)
        self.read_calls: list[str] = []

    def read(self, cypher, parameters, bookmark):
        self.read_calls.append(cypher)
        if "HAS_ALIAS" in cypher:
            return self.alias_rows
        if "MATCH (n:Entity" in cypher:
            return self.entity_rows
        raise AssertionError(f"unexpected cypher in FakeHydraTransport: {cypher}")


class _RaisingTransport:
    def read(self, cypher, parameters, bookmark):
        raise RuntimeError("hydradb unavailable")


class HydraEntityHydratorTests(unittest.TestCase):
    def test_fetch_returns_entities_with_grouped_aliases(self) -> None:
        transport = FakeHydraTransport(
            entity_rows=[
                {"id": 7, "canonical_name": "lord farquaad", "entity_type": "person"},
                {"id": 8, "canonical_name": "shrek", "entity_type": "person"},
            ],
            alias_rows=[
                {"entity_id": 7, "canonical_alias": "farquaad"},
                {"entity_id": 7, "canonical_alias": "the lord"},
            ],
        )
        entities = HydraEntityHydrator(transport).fetch("ctx")
        self.assertEqual(
            sorted(entities, key=lambda e: e.graph_id),
            [
                HydratedEntity(7, "lord farquaad", "person", ("farquaad", "the lord")),
                HydratedEntity(8, "shrek", "person", ()),
            ],
        )

    def test_fetch_skips_malformed_entity_rows(self) -> None:
        transport = FakeHydraTransport(
            entity_rows=[
                {"id": 7, "canonical_name": "shrek", "entity_type": "person"},
                {"id": 8, "canonical_name": "", "entity_type": "person"},
                {"id": None, "canonical_name": "donkey", "entity_type": "person"},
            ],
        )
        entities = HydraEntityHydrator(transport).fetch("ctx")
        self.assertEqual([e.graph_id for e in entities], [7])

    def test_fetch_skips_malformed_alias_rows(self) -> None:
        transport = FakeHydraTransport(
            entity_rows=[{"id": 7, "canonical_name": "shrek", "entity_type": "person"}],
            alias_rows=[
                {"entity_id": 7, "canonical_alias": "ogre"},
                {"entity_id": None, "canonical_alias": "dropped"},
                {"entity_id": 7, "canonical_alias": ""},
            ],
        )
        (entity,) = HydraEntityHydrator(transport).fetch("ctx")
        self.assertEqual(entity.aliases, ("ogre",))

    def test_fetch_returns_empty_list_on_transport_failure(self) -> None:
        entities = HydraEntityHydrator(_RaisingTransport()).fetch("ctx")
        self.assertEqual(entities, [])

    def test_fetch_returns_empty_list_for_context_with_no_rows(self) -> None:
        entities = HydraEntityHydrator(FakeHydraTransport()).fetch("ctx")
        self.assertEqual(entities, [])
