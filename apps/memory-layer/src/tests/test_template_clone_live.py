"""Live HydraDB clone smoke -- Milestone 3b. Same skip-unless-env pattern as
test_hydradb_live.py: requires a real local instance, never hosted
credentials. This is the test that actually validates template_clone.py's
query shapes (the unit tests in test_template_clone.py validate the id-
remapping/dedup logic built on top, against a fake)."""

from __future__ import annotations

import os
import unittest
from uuid import uuid4

from context_memory.client.hydradb_http import HydraHttpTransport
from context_memory.cloning.template_clone import clone
from context_memory.ingestion.direct_authoring import (
    DirectEntityInput,
    DirectFactInput,
    write_entity,
    write_fact,
)
from context_memory.ingestion.fakes import InMemoryGraphManifestStore
from context_memory.ingestion.graph_writer import GraphWriter

URI = os.environ.get("CONTEXT_MEMORY_HYDRADB_URL")
TOKEN = os.environ.get("CONTEXT_MEMORY_HYDRADB_TOKEN")
DATABASE = os.environ.get("CONTEXT_MEMORY_HYDRADB_DATABASE", "default")


class _RandomBaseGraphIdAllocator:
    """`InMemoryGraphIdAllocator` (ingestion/fakes.py) starts counting at 0 --
    correct for an isolated unit test, but unsafe here: this local HydraDB
    instance is real, persistent storage shared across every test run (and
    ad-hoc manual runs) against this container, and `MERGE (n {id: N})`
    matches purely on the raw integer id with no context_id/label scoping at
    the storage level -- two different runs both starting from id 0 collide
    on the *same physical node*, and `SET n += properties` is additive, so a
    reused id can end up carrying properties left over from whatever
    unrelated node occupied it in an earlier run. Random large starting
    offset, same collision-avoidance convention `test_hydradb_live.py`
    already uses for its own seed id."""

    def __init__(self) -> None:
        self._next = uuid4().int % 1_000_000_000
        self._ids: dict[tuple[str, str, str], int] = {}

    def allocate_graph_id(
        self, node_kind: str, context_id: str, logical_key: str
    ) -> int:
        key = (node_kind, context_id, logical_key)
        if key not in self._ids:
            self._ids[key] = self._next
            self._next += 1
        return self._ids[key]


@unittest.skipUnless(
    URI and TOKEN,
    "requires local CONTEXT_MEMORY_HYDRADB_URL and CONTEXT_MEMORY_HYDRADB_TOKEN",
)
class TemplateCloneLiveTests(unittest.TestCase):
    def test_clone_is_a_real_independent_copy(self) -> None:
        suffix = uuid4().hex
        template_ctx = f"live-template-{suffix}"
        playthrough_ctx = f"live-playthrough-{suffix}"

        transport = HydraHttpTransport(URI or "", TOKEN or "", graph_id=DATABASE)
        manifest = InMemoryGraphManifestStore()
        writer = GraphWriter(manifest, transport)
        allocator = _RandomBaseGraphIdAllocator()

        write_entity(
            template_ctx,
            DirectEntityInput(canonical_name="Sukuna", entity_type="character"),
            allocator,
            writer,
        )
        write_entity(
            template_ctx,
            DirectEntityInput(canonical_name="Jujutsu High", entity_type="faction"),
            allocator,
            writer,
        )
        write_fact(
            template_ctx,
            DirectFactInput(
                predicate="is_strongest",
                subject_canonical_name="Sukuna",
                object_literal="true",
            ),
            allocator,
            writer,
        )
        write_fact(
            template_ctx,
            DirectFactInput(
                predicate="member_of",
                subject_canonical_name="Sukuna",
                object_canonical_name="Jujutsu High",
            ),
            allocator,
            writer,
        )

        result = clone(template_ctx, playthrough_ctx, allocator, writer, transport)
        self.assertEqual(
            (result.entities_cloned, result.facts_cloned, result.relationships_cloned),
            (2, 2, 3),
        )

        cloned_facts = transport.read(
            "MATCH (n:Fact {context_id: $ctx}) RETURN n.id AS id, n.predicate_key AS pk",
            {"ctx": playthrough_ctx},
            None,
        )
        self.assertEqual(
            {row["pk"] for row in cloned_facts}, {"is_strongest", "member_of"}
        )

        # Mutating the clone must never touch the template.
        write_fact(
            playthrough_ctx,
            DirectFactInput(
                predicate="playthrough_only_event",
                subject_canonical_name="Sukuna",
                object_literal="met the player",
            ),
            allocator,
            writer,
        )
        template_facts_after = transport.read(
            "MATCH (n:Fact {context_id: $ctx}) RETURN n.id AS id",
            {"ctx": template_ctx},
            None,
        )
        self.assertEqual(len(template_facts_after), 2)

    def test_cloning_an_empty_template_is_a_no_op(self) -> None:
        suffix = uuid4().hex
        transport = HydraHttpTransport(URI or "", TOKEN or "", graph_id=DATABASE)
        writer = GraphWriter(InMemoryGraphManifestStore(), transport)
        allocator = _RandomBaseGraphIdAllocator()

        result = clone(
            f"live-empty-template-{suffix}",
            f"live-empty-playthrough-{suffix}",
            allocator,
            writer,
            transport,
        )

        self.assertEqual(
            (result.entities_cloned, result.facts_cloned, result.relationships_cloned),
            (0, 0, 0),
        )
