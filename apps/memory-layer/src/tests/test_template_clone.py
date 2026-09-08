"""Scenario-template -> playthrough clone -- Milestone 3b of the AI-DND
bridge. Query shapes here were live-verified against a real HydraDB instance
first (see template_clone.py's module docstring) -- this file re-checks the
*logic* built on top of those shapes (id remapping, dangling-edge handling,
null-property filtering) against a controllable fake, not the shapes
themselves.
"""

from __future__ import annotations

import unittest

from context_memory.cloning.template_clone import clone
from context_memory.ingestion.fakes import (
    InMemoryGraphIdAllocator,
    InMemoryGraphManifestStore,
)
from context_memory.ingestion.graph_writer import GraphWriter


class FakeHydraTransport:
    """Content-sniffs the Cypher (same approach test_retrieval_engine.py's
    FakeCursor uses for SQL) -- a real query sequence change here shouldn't
    silently misalign a fixed positional fixture list."""

    def __init__(
        self,
        entity_rows=(),
        fact_rows=(),
        about_rows=(),
        stated_by_rows=(),
        relates_to_rows=(),
        alias_rows=(),
        has_alias_rows=(),
    ):
        self.entity_rows = list(entity_rows)
        self.fact_rows = list(fact_rows)
        self.about_rows = list(about_rows)
        self.stated_by_rows = list(stated_by_rows)
        self.relates_to_rows = list(relates_to_rows)
        self.alias_rows = list(alias_rows)
        self.has_alias_rows = list(has_alias_rows)
        self.read_calls: list[str] = []

    def read(self, cypher, parameters, bookmark):
        self.read_calls.append(cypher)
        if "MATCH (n:Entity" in cypher:
            return self.entity_rows
        if "MATCH (n:Fact" in cypher:
            return self.fact_rows
        if "MATCH (n:Alias" in cypher:
            return self.alias_rows
        if "[r:ABOUT]" in cypher:
            return self.about_rows
        if "[r:STATED_BY]" in cypher:
            return self.stated_by_rows
        if "[r:RELATES_TO]" in cypher:
            return self.relates_to_rows
        if "[r:HAS_ALIAS]" in cypher:
            return self.has_alias_rows
        raise AssertionError(f"unexpected cypher in FakeHydraTransport: {cypher}")

    def write(self, cypher, rows, idempotency_key):
        raise AssertionError(
            "template_clone should never call write() on the read transport"
        )


def _writer():
    return GraphWriter(InMemoryGraphManifestStore(), _NullWriteTransport())


class _NullWriteTransport:
    def __init__(self):
        self.writes = []

    def write(self, cypher, rows, idempotency_key):
        self.writes.append((cypher, list(rows), idempotency_key))
        return f"bookmark-{len(self.writes)}"

    def read(self, cypher, parameters, bookmark):
        raise AssertionError("write transport should never be read from")


class CloneTests(unittest.TestCase):
    def test_clones_entities_facts_and_about_edges_with_remapped_ids(self):
        source = FakeHydraTransport(
            entity_rows=[
                {
                    "id": 1,
                    "logical_key": "entity:Sukuna",
                    "canonical_name": "Sukuna",
                    "entity_type": "character",
                }
            ],
            fact_rows=[
                {
                    "id": 2,
                    "logical_key": "fact:direct:abc",
                    "text": "Sukuna is strongest",
                    "predicate_key": "is_strongest",
                    "confidence": 1.0,
                }
            ],
            about_rows=[{"src": 2, "dst": 1}],
        )
        allocator = InMemoryGraphIdAllocator()
        writer = _writer()
        write_transport = writer._transport

        result = clone(
            "scenario-template::s1", "playthrough-1", allocator, writer, source
        )

        self.assertEqual(result.entities_cloned, 1)
        self.assertEqual(result.facts_cloned, 1)
        self.assertEqual(result.relationships_cloned, 1)
        # Every written row must carry the TARGET context_id, never the source's.
        for cypher, rows, _key in write_transport.writes:
            for row in rows:
                self.assertEqual(row["context_id"], "playthrough-1")

    def test_same_logical_key_gets_a_distinct_graph_id_in_the_target_context(self):
        """The whole isolation guarantee ADR-7 needs: cloning into a context
        that already used the same logical_key (e.g. re-cloning, or two
        playthroughs of the same scenario) never collides."""
        source = FakeHydraTransport(
            entity_rows=[
                {
                    "id": 1,
                    "logical_key": "entity:Sukuna",
                    "canonical_name": "Sukuna",
                    "entity_type": "character",
                }
            ],
            fact_rows=[],
        )
        allocator = InMemoryGraphIdAllocator()
        writer = _writer()

        clone("scenario-template::s1", "playthrough-1", allocator, writer, source)
        clone("scenario-template::s1", "playthrough-2", allocator, writer, source)

        id_in_p1 = allocator.allocate_graph_id(
            "entity", "playthrough-1", "entity:Sukuna"
        )
        id_in_p2 = allocator.allocate_graph_id(
            "entity", "playthrough-2", "entity:Sukuna"
        )
        self.assertNotEqual(id_in_p1, id_in_p2)

    def test_null_properties_are_dropped_not_written_as_none(self):
        """GraphNode.properties must be scalar (core/graph.py) -- a property
        HydraDB reads back as null for a node that never set it would fail
        GraphNode's own validation if passed through unfiltered."""
        source = FakeHydraTransport(
            entity_rows=[
                {
                    "id": 1,
                    "logical_key": "entity:Sukuna",
                    "canonical_name": "Sukuna",
                    "entity_type": "character",
                    "description": None,
                    "aliases": None,
                }
            ],
            fact_rows=[],
        )
        allocator = InMemoryGraphIdAllocator()
        writer = _writer()

        clone("scenario-template::s1", "playthrough-1", allocator, writer, source)

        [(_cypher, rows, _key)] = writer._transport.writes
        self.assertNotIn("description", rows[0])
        self.assertNotIn("aliases", rows[0])

    def test_dangling_edge_to_an_unclonable_node_is_dropped_not_crashed(self):
        source = FakeHydraTransport(
            entity_rows=[
                {
                    "id": 1,
                    "logical_key": "entity:Sukuna",
                    "canonical_name": "Sukuna",
                    "entity_type": "character",
                }
            ],
            fact_rows=[
                {
                    "id": 2,
                    "logical_key": "fact:direct:abc",
                    "text": "x",
                    "predicate_key": "p",
                }
            ],
            about_rows=[{"src": 2, "dst": 999}],  # dst 999 was never in entity_rows
        )
        allocator = InMemoryGraphIdAllocator()
        writer = _writer()

        result = clone(
            "scenario-template::s1", "playthrough-1", allocator, writer, source
        )

        self.assertEqual(result.relationships_cloned, 0)

    def test_empty_template_clones_to_nothing_without_error(self):
        source = FakeHydraTransport(entity_rows=[], fact_rows=[])
        allocator = InMemoryGraphIdAllocator()
        writer = _writer()

        result = clone(
            "scenario-template::empty", "playthrough-1", allocator, writer, source
        )

        self.assertEqual(
            (result.entities_cloned, result.facts_cloned, result.relationships_cloned),
            (0, 0, 0),
        )
        self.assertEqual(writer._transport.writes, [])

    def test_all_three_relationship_types_are_swept(self):
        source = FakeHydraTransport(
            entity_rows=[
                {
                    "id": 1,
                    "logical_key": "entity:Sukuna",
                    "canonical_name": "Sukuna",
                    "entity_type": "character",
                },
                {
                    "id": 2,
                    "logical_key": "entity:user",
                    "canonical_name": "user",
                    "entity_type": "speaker",
                },
                {
                    "id": 3,
                    "logical_key": "entity:JujutsuHigh",
                    "canonical_name": "Jujutsu High",
                    "entity_type": "faction",
                },
            ],
            fact_rows=[
                {"id": 4, "logical_key": "fact:x", "text": "x", "predicate_key": "p"}
            ],
            about_rows=[{"src": 4, "dst": 1}],
            stated_by_rows=[{"src": 4, "dst": 2}],
            relates_to_rows=[{"src": 4, "dst": 3}],
        )
        allocator = InMemoryGraphIdAllocator()
        writer = _writer()

        result = clone(
            "scenario-template::s1", "playthrough-1", allocator, writer, source
        )

        self.assertEqual(result.relationships_cloned, 3)


class FakeFactProjector:
    def __init__(self):
        self.calls: list[tuple[str, str, str, int, str]] = []

    def project_copy(
        self,
        source_context_id,
        source_subject_id,
        target_context_id,
        new_fact_graph_id,
        text,
    ):
        self.calls.append(
            (
                source_context_id,
                source_subject_id,
                target_context_id,
                new_fact_graph_id,
                text,
            )
        )


class FactProjectorCloneTests(unittest.TestCase):
    """mem1 gap #46 fix: clone() must reach FactProjectionWriter (via its
    ingestion.fact_projection.FactProjector Protocol) for every successfully
    cloned fact, or the playthrough's copy stays invisible to
    CandidateSeeder even though the template's own copy might already be
    indexed."""

    def test_direct_authored_origin_fact_is_read_back_by_its_own_old_graph_id(self):
        """logical_key `fact:direct:...` never encodes a graph_id (it's a
        content hash) -- FactProjectionWriter.project stores THIS kind of
        fact under its own graph_id instead, so that's what clone must ask
        project_copy to read back from the source context."""
        source = FakeHydraTransport(
            entity_rows=[
                {
                    "id": 1,
                    "logical_key": "entity:Sukuna",
                    "canonical_name": "Sukuna",
                    "entity_type": "character",
                }
            ],
            fact_rows=[
                {
                    "id": 2,
                    "logical_key": "fact:direct:abc",
                    "text": "Sukuna is strongest",
                    "predicate_key": "is_strongest",
                }
            ],
            about_rows=[{"src": 2, "dst": 1}],
        )
        allocator = InMemoryGraphIdAllocator()
        writer = _writer()
        projector = FakeFactProjector()

        clone(
            "scenario-template::s1",
            "playthrough-1",
            allocator,
            writer,
            source,
            fact_projector=projector,
        )

        new_fact_id = allocator.allocate_graph_id(
            "fact", "playthrough-1", "fact:direct:abc"
        )
        self.assertEqual(
            projector.calls,
            [
                (
                    "scenario-template::s1",
                    "2",
                    "playthrough-1",
                    new_fact_id,
                    "Sukuna is strongest",
                )
            ],
        )

    def test_extraction_origin_fact_is_read_back_by_its_candidate_id(self):
        """logical_key `fact:<candidate_id>` IS orchestrator.py's own
        projection identity for this fact -- clone must read the source row
        back under that candidate_id, not the old graph_id."""
        source = FakeHydraTransport(
            entity_rows=[],
            fact_rows=[
                {
                    "id": 9,
                    "logical_key": "fact:cand-abc123",
                    "text": "The user lives in Bengaluru",
                    "predicate_key": "location",
                }
            ],
        )
        allocator = InMemoryGraphIdAllocator()
        writer = _writer()
        projector = FakeFactProjector()

        clone(
            "scenario-template::s1",
            "playthrough-1",
            allocator,
            writer,
            source,
            fact_projector=projector,
        )

        new_fact_id = allocator.allocate_graph_id(
            "fact", "playthrough-1", "fact:cand-abc123"
        )
        self.assertEqual(
            projector.calls,
            [
                (
                    "scenario-template::s1",
                    "cand-abc123",
                    "playthrough-1",
                    new_fact_id,
                    "The user lives in Bengaluru",
                )
            ],
        )

    def test_a_fact_with_no_text_is_not_projected(self):
        source = FakeHydraTransport(
            entity_rows=[],
            fact_rows=[
                {
                    "id": 2,
                    "logical_key": "fact:direct:abc",
                    "text": None,
                    "predicate_key": "is_strongest",
                }
            ],
        )
        allocator = InMemoryGraphIdAllocator()
        writer = _writer()
        projector = FakeFactProjector()

        clone(
            "scenario-template::s1",
            "playthrough-1",
            allocator,
            writer,
            source,
            fact_projector=projector,
        )

        self.assertEqual(projector.calls, [])

    def test_no_projector_given_is_a_silent_no_op(self):
        source = FakeHydraTransport(
            entity_rows=[],
            fact_rows=[
                {
                    "id": 2,
                    "logical_key": "fact:direct:abc",
                    "text": "x",
                    "predicate_key": "p",
                }
            ],
        )
        allocator = InMemoryGraphIdAllocator()
        writer = _writer()

        clone(
            "scenario-template::s1", "playthrough-1", allocator, writer, source
        )  # must not raise


class FakeFactMetadataStore:
    """Milestones 4-5 fixture: in-memory stand-in for
    persistence.postgres.PostgresFactMetadataStore, matching its
    (get_many/put) shape exactly (cloning.template_clone.FactMetadataStore)."""

    def __init__(self, rows_by_context=None):
        self._rows = {ctx: dict(rows) for ctx, rows in (rows_by_context or {}).items()}
        self.puts: list[tuple[str, int, str | None, dict | None, str | None, bool]] = []

    def get_many(self, context_id, fact_ids):
        rows = self._rows.get(context_id, {})
        return {fid: rows[fid] for fid in fact_ids if fid in rows}

    def put(
        self,
        context_id,
        fact_id,
        checkpoint,
        when_active,
        visible_to_participant_id=None,
        hidden=False,
    ):
        self.puts.append(
            (
                context_id,
                fact_id,
                checkpoint,
                when_active,
                visible_to_participant_id,
                hidden,
            )
        )
        self._rows.setdefault(context_id, {})[fact_id] = (
            checkpoint,
            when_active,
            visible_to_participant_id,
            hidden,
        )


class FactMetadataCloneTests(unittest.TestCase):
    """`clone()`'s optional `fact_metadata_store` param -- carries a
    pre-authored fact's `when_active`/`checkpoint` onto its newly-allocated
    clone id, since `pre_authored_fact_metadata` is keyed by (context_id,
    fact_id) and cloning always mints a fresh fact_id."""

    def test_metadata_row_is_cloned_onto_the_new_fact_id(self):
        source = FakeHydraTransport(
            entity_rows=[
                {
                    "id": 1,
                    "logical_key": "entity:Sukuna",
                    "canonical_name": "Sukuna",
                    "entity_type": "character",
                }
            ],
            fact_rows=[
                {
                    "id": 2,
                    "logical_key": "fact:direct:abc",
                    "text": "x",
                    "predicate_key": "is_pursued_by_ghost",
                }
            ],
            about_rows=[{"src": 2, "dst": 1}],
        )
        when_active = {"field": "player.health", "op": "<", "value": 5}
        metadata_store = FakeFactMetadataStore(
            rows_by_context={
                "scenario-template::s1": {2: (None, when_active, "participant-1", True)}
            }
        )
        allocator = InMemoryGraphIdAllocator()
        writer = _writer()

        clone(
            "scenario-template::s1",
            "playthrough-1",
            allocator,
            writer,
            source,
            metadata_store,
        )

        new_fact_id = allocator.allocate_graph_id(
            "fact", "playthrough-1", "fact:direct:abc"
        )
        cloned = metadata_store.get_many("playthrough-1", [new_fact_id])
        # §5 fix: visible_to_participant_id (the third element) must survive
        # the clone too -- a participant-restricted template fact staying
        # restricted in every playthrough cloned from it. `hidden` (the
        # fourth) must survive the same way -- a secret stays a secret.
        self.assertEqual(
            cloned, {new_fact_id: (None, when_active, "participant-1", True)}
        )

    def test_fact_with_no_metadata_row_clones_nothing_extra(self):
        source = FakeHydraTransport(
            entity_rows=[
                {
                    "id": 1,
                    "logical_key": "entity:Sukuna",
                    "canonical_name": "Sukuna",
                    "entity_type": "character",
                }
            ],
            fact_rows=[
                {
                    "id": 2,
                    "logical_key": "fact:direct:abc",
                    "text": "x",
                    "predicate_key": "p",
                }
            ],
            about_rows=[{"src": 2, "dst": 1}],
        )
        metadata_store = FakeFactMetadataStore()
        allocator = InMemoryGraphIdAllocator()
        writer = _writer()

        clone(
            "scenario-template::s1",
            "playthrough-1",
            allocator,
            writer,
            source,
            metadata_store,
        )

        self.assertEqual(metadata_store.puts, [])

    def test_no_fact_metadata_store_given_is_a_pure_no_op(self):
        """Milestone 3b's own callers/tests (no fact_metadata_store arg)
        must keep working exactly as before Milestones 4-5 added this."""
        source = FakeHydraTransport(
            entity_rows=[
                {
                    "id": 1,
                    "logical_key": "entity:Sukuna",
                    "canonical_name": "Sukuna",
                    "entity_type": "character",
                }
            ],
            fact_rows=[
                {
                    "id": 2,
                    "logical_key": "fact:direct:abc",
                    "text": "x",
                    "predicate_key": "p",
                }
            ],
            about_rows=[{"src": 2, "dst": 1}],
        )
        allocator = InMemoryGraphIdAllocator()
        writer = _writer()

        result = clone(
            "scenario-template::s1", "playthrough-1", allocator, writer, source
        )

        self.assertEqual(result.facts_cloned, 1)


if __name__ == "__main__":
    unittest.main()
