"""Master-mode direct graph writes -- Milestone 3a of the AI-DND bridge.

No LLM extractor is touched anywhere in this file -- that's the point: a
creator's structured Entity/Fact input maps straight onto the graph, per
AI-DND's stated master-mode trust guarantee.
"""

from __future__ import annotations

import unittest

from context_memory.ingestion.direct_authoring import (
    DirectEntityInput,
    DirectFactInput,
    write_entity,
    write_fact,
)
from context_memory.ingestion.fakes import (
    InMemoryGraphIdAllocator,
    InMemoryGraphManifestStore,
    RecordingGraphTransport,
)
from context_memory.ingestion.graph_writer import GraphWriter


def _writer():
    allocator = InMemoryGraphIdAllocator()
    manifest = InMemoryGraphManifestStore()
    transport = RecordingGraphTransport()
    return allocator, GraphWriter(manifest, transport), transport


class WriteEntityTests(unittest.TestCase):
    def test_writes_one_entity_node_with_creator_fields(self):
        allocator, writer, transport = _writer()

        graph_id = write_entity(
            "scenario-template::abc",
            DirectEntityInput(
                canonical_name="Sukuna",
                entity_type="character",
                description="A cursed spirit",
            ),
            allocator,
            writer,
        )

        self.assertIsInstance(graph_id, int)
        [(cypher, rows, _key)] = transport.writes
        self.assertIn("Entity", cypher)
        self.assertEqual(rows[0]["canonical_name"], "Sukuna")
        self.assertEqual(rows[0]["entity_type"], "character")
        self.assertEqual(rows[0]["description"], "A cursed spirit")

    def test_same_canonical_name_is_idempotent_same_graph_id(self):
        allocator, writer, _transport = _writer()
        entity = DirectEntityInput(canonical_name="Sukuna", entity_type="character")

        first = write_entity("ctx-1", entity, allocator, writer)
        second = write_entity("ctx-1", entity, allocator, writer)

        self.assertEqual(first, second)

    def test_aliases_are_flattened_to_a_scalar_property(self):
        """Graph node properties are scalar-only (core/graph.py's `_properties`)
        -- a tuple of aliases can't cross as-is."""
        allocator, writer, transport = _writer()

        write_entity(
            "ctx-1",
            DirectEntityInput(
                canonical_name="Sukuna",
                entity_type="character",
                aliases=("King of Curses", "Ryomen"),
            ),
            allocator,
            writer,
        )

        [(_cypher, rows, _key)] = transport.writes
        self.assertEqual(rows[0]["aliases"], "King of Curses, Ryomen")


class WriteFactTests(unittest.TestCase):
    def test_writes_fact_node_and_about_edge_to_subject(self):
        allocator, writer, transport = _writer()
        write_entity(
            "ctx-1",
            DirectEntityInput(canonical_name="Sukuna", entity_type="character"),
            allocator,
            writer,
        )

        write_fact(
            "ctx-1",
            DirectFactInput(
                predicate="is_strongest",
                subject_canonical_name="Sukuna",
                object_literal="true",
            ),
            allocator,
            writer,
        )

        fact_write = next(
            w for w in transport.writes if "Fact" in w[0] and "Entity" not in w[0]
        )
        self.assertEqual(fact_write[1][0]["predicate_key"], "is_strongest")
        self.assertEqual(fact_write[1][0]["confidence"], 1.0)
        about_write = next(w for w in transport.writes if "ABOUT" in w[0])
        self.assertTrue(len(about_write[1]) == 1)

    def test_object_entity_reference_gets_a_relates_to_edge(self):
        allocator, writer, transport = _writer()
        write_entity(
            "ctx-1",
            DirectEntityInput(canonical_name="Sukuna", entity_type="character"),
            allocator,
            writer,
        )
        write_entity(
            "ctx-1",
            DirectEntityInput(canonical_name="Jujutsu High", entity_type="faction"),
            allocator,
            writer,
        )

        write_fact(
            "ctx-1",
            DirectFactInput(
                predicate="member_of",
                subject_canonical_name="Sukuna",
                object_canonical_name="Jujutsu High",
            ),
            allocator,
            writer,
        )

        relates_write = next(w for w in transport.writes if "RELATES_TO" in w[0])
        self.assertEqual(len(relates_write[1]), 1)

    def test_object_literal_stored_without_a_relates_to_edge(self):
        allocator, writer, transport = _writer()
        write_entity(
            "ctx-1",
            DirectEntityInput(canonical_name="Sukuna", entity_type="character"),
            allocator,
            writer,
        )

        write_fact(
            "ctx-1",
            DirectFactInput(
                predicate="has_power_level",
                subject_canonical_name="Sukuna",
                object_literal="9999",
            ),
            allocator,
            writer,
        )

        self.assertFalse(any("RELATES_TO" in w[0] for w in transport.writes))
        fact_write = next(
            w for w in transport.writes if "Fact" in w[0] and "Entity" not in w[0]
        )
        self.assertEqual(fact_write[1][0]["object_literal"], "9999")

    def test_identical_triple_written_twice_is_idempotent(self):
        allocator, writer, _transport = _writer()
        write_entity(
            "ctx-1",
            DirectEntityInput(canonical_name="Sukuna", entity_type="character"),
            allocator,
            writer,
        )
        fact = DirectFactInput(
            predicate="is_strongest",
            subject_canonical_name="Sukuna",
            object_literal="true",
        )

        first = write_fact("ctx-1", fact, allocator, writer)
        second = write_fact("ctx-1", fact, allocator, writer)

        self.assertEqual(first, second)

    def test_requires_an_object(self):
        with self.assertRaises(ValueError):
            DirectFactInput(predicate="is_strongest", subject_canonical_name="Sukuna")

    def test_about_edge_carries_a_stub_entity_when_subject_was_never_authored(self):
        """HIGH-10: a fact written before its entity (or against a typo'd
        `canonical_name`) must not orphan its ABOUT edge -- HydraDB's
        `UNWIND ... MATCH ... MERGE` silently drops a relationship row when
        `MATCH` finds no entity, with no error surfaced."""
        allocator, writer, transport = _writer()

        write_fact(
            "ctx-1",
            DirectFactInput(
                predicate="is_strongest",
                subject_canonical_name="Typo'd Name",
                object_literal="true",
            ),
            allocator,
            writer,
        )

        entity_write = next(w for w in transport.writes if "n:Entity" in w[0])
        self.assertEqual(entity_write[1][0]["canonical_name"], "Typo'd Name")
        about_write = next(w for w in transport.writes if "ABOUT" in w[0])
        self.assertEqual(len(about_write[1]), 1)

    def test_object_reference_also_carries_a_stub_entity_when_never_authored(self):
        allocator, writer, transport = _writer()
        write_entity(
            "ctx-1",
            DirectEntityInput(canonical_name="Sukuna", entity_type="character"),
            allocator,
            writer,
        )

        write_fact(
            "ctx-1",
            DirectFactInput(
                predicate="member_of",
                subject_canonical_name="Sukuna",
                object_canonical_name="Jujutsu High",
            ),
            allocator,
            writer,
        )

        entity_writes = [w for w in transport.writes if "n:Entity" in w[0]]
        stub_names = {
            row["canonical_name"] for _, rows, _ in entity_writes for row in rows
        }
        self.assertIn("Jujutsu High", stub_names)
        relates_write = next(w for w in transport.writes if "RELATES_TO" in w[0])
        self.assertEqual(len(relates_write[1]), 1)

    def test_stub_entity_never_carries_entity_type_so_it_cannot_clobber_a_real_entity(
        self,
    ):
        allocator, writer, transport = _writer()
        write_entity(
            "ctx-1",
            DirectEntityInput(canonical_name="Sukuna", entity_type="character"),
            allocator,
            writer,
        )

        write_fact(
            "ctx-1",
            DirectFactInput(
                predicate="is_strongest",
                subject_canonical_name="Sukuna",
                object_literal="true",
            ),
            allocator,
            writer,
        )

        stub_write = next(
            w
            for w in transport.writes
            if "n:Entity" in w[0]
            and "entity_type" not in w[0]
            and any(row.get("canonical_name") == "Sukuna" for row in w[1])
        )
        self.assertNotIn("entity_type", stub_write[0])

    def test_different_playthrough_contexts_get_independent_graph_ids(self):
        """Same triple, two contexts (e.g. a template and its clone target
        before Milestone 3b's clone even runs) -- distinct graph_ids, no
        cross-context collision. Groundwork check for Milestone 3b."""
        allocator, writer, _transport = _writer()
        write_entity(
            "scenario-template::s1",
            DirectEntityInput(canonical_name="Sukuna", entity_type="character"),
            allocator,
            writer,
        )
        write_entity(
            "playthrough-1",
            DirectEntityInput(canonical_name="Sukuna", entity_type="character"),
            allocator,
            writer,
        )
        fact = DirectFactInput(
            predicate="is_strongest",
            subject_canonical_name="Sukuna",
            object_literal="true",
        )

        template_id = write_fact("scenario-template::s1", fact, allocator, writer)
        playthrough_id = write_fact("playthrough-1", fact, allocator, writer)

        self.assertNotEqual(template_id, playthrough_id)


class FakeFactMetadataStore:
    def __init__(self):
        self.puts = []

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


class FakeExternalFactIdStore:
    def __init__(self):
        self._rows = {}

    def get(self, context_id, external_fact_id):
        return self._rows.get((context_id, external_fact_id))

    def put(self, context_id, external_fact_id, graph_id, logical_key):
        self._rows[(context_id, external_fact_id)] = (graph_id, logical_key)


class FakeFactProjector:
    def __init__(self):
        self.calls: list[tuple[str, int, str]] = []

    def project(self, context_id, fact_graph_id, text):
        self.calls.append((context_id, fact_graph_id, text))


class FactProjectorWiringTests(unittest.TestCase):
    """mem1 gap #46 fix: write_fact must reach FactProjectionWriter (via its
    ingestion.fact_projection.FactProjector Protocol) after the graph write
    succeeds, or the fact stays invisible to CandidateSeeder forever."""

    def test_project_is_called_with_the_new_facts_own_graph_id_and_display_text(self):
        allocator, writer, _transport = _writer()
        write_entity(
            "ctx-1",
            DirectEntityInput(canonical_name="Sukuna", entity_type="character"),
            allocator,
            writer,
        )
        projector = FakeFactProjector()

        fact_id = write_fact(
            "ctx-1",
            DirectFactInput(
                predicate="is_strongest",
                subject_canonical_name="Sukuna",
                object_literal="true",
            ),
            allocator,
            writer,
            fact_projector=projector,
        )

        self.assertEqual(
            projector.calls, [("ctx-1", fact_id, "Sukuna is_strongest true")]
        )

    def test_no_projector_given_is_a_silent_no_op(self):
        """Every existing caller that never wires one (most tests above)
        must keep working exactly as before."""
        allocator, writer, _transport = _writer()
        write_entity(
            "ctx-1",
            DirectEntityInput(canonical_name="Sukuna", entity_type="character"),
            allocator,
            writer,
        )

        write_fact(  # must not raise
            "ctx-1",
            DirectFactInput(
                predicate="is_strongest",
                subject_canonical_name="Sukuna",
                object_literal="true",
            ),
            allocator,
            writer,
        )


class HiddenFactTests(unittest.TestCase):
    """AI-DND memory-layer contract: an author-marked-secret fact -- mem1
    never filters on it, just persists and returns it truthfully."""

    def test_hidden_true_persists_metadata(self):
        allocator, writer, _transport = _writer()
        write_entity(
            "ctx-1",
            DirectEntityInput(canonical_name="Sukuna", entity_type="character"),
            allocator,
            writer,
        )
        metadata_store = FakeFactMetadataStore()

        fact_id = write_fact(
            "ctx-1",
            DirectFactInput(
                predicate="knows_secret",
                subject_canonical_name="Sukuna",
                object_literal="true",
                hidden=True,
            ),
            allocator,
            writer,
            metadata_store,
        )

        self.assertEqual(
            metadata_store.puts, [("ctx-1", fact_id, None, None, None, True)]
        )

    def test_hidden_false_is_the_default_and_writes_no_metadata_alone(self):
        allocator, writer, _transport = _writer()
        write_entity(
            "ctx-1",
            DirectEntityInput(canonical_name="Sukuna", entity_type="character"),
            allocator,
            writer,
        )
        metadata_store = FakeFactMetadataStore()

        write_fact(
            "ctx-1",
            DirectFactInput(
                predicate="is_strongest",
                subject_canonical_name="Sukuna",
                object_literal="true",
            ),
            allocator,
            writer,
            metadata_store,
        )

        self.assertEqual(metadata_store.puts, [])


class SupersededFactIdTests(unittest.TestCase):
    """AI-DND memory-layer contract: a direct-authored fact can name the
    prior fact (by the CALLER's own opaque id) it replaces."""

    def test_registers_its_own_external_fact_id(self):
        allocator, writer, _transport = _writer()
        write_entity(
            "ctx-1",
            DirectEntityInput(canonical_name="Sukuna", entity_type="character"),
            allocator,
            writer,
        )
        external_store = FakeExternalFactIdStore()

        fact_id = write_fact(
            "ctx-1",
            DirectFactInput(
                predicate="is_alive",
                subject_canonical_name="Sukuna",
                object_literal="true",
                external_fact_id="core-api-fact-1",
            ),
            allocator,
            writer,
            external_fact_id_store=external_store,
        )

        resolved = external_store.get("ctx-1", "core-api-fact-1")
        self.assertEqual(resolved[0], fact_id)

    def test_superseded_fact_id_creates_a_supersedes_edge_and_closes_the_prior_fact(
        self,
    ):
        allocator, writer, transport = _writer()
        write_entity(
            "ctx-1",
            DirectEntityInput(canonical_name="Sukuna", entity_type="character"),
            allocator,
            writer,
        )
        external_store = FakeExternalFactIdStore()

        old_fact_id = write_fact(
            "ctx-1",
            DirectFactInput(
                predicate="is_alive",
                subject_canonical_name="Sukuna",
                object_literal="true",
                external_fact_id="core-api-fact-1",
            ),
            allocator,
            writer,
            external_fact_id_store=external_store,
        )
        new_fact_id = write_fact(
            "ctx-1",
            DirectFactInput(
                predicate="is_alive",
                subject_canonical_name="Sukuna",
                object_literal="false",
                external_fact_id="core-api-fact-2",
                superseded_fact_id="core-api-fact-1",
            ),
            allocator,
            writer,
            external_fact_id_store=external_store,
        )

        supersedes_write = next(w for w in transport.writes if "SUPERSEDES" in w[0])
        self.assertEqual(supersedes_write[1][0]["source_id"], new_fact_id)
        self.assertEqual(supersedes_write[1][0]["destination_id"], old_fact_id)
        # old_fact_id's node appears twice: its own creation (is_current=True)
        # and the archival update from superseding it (is_current=False) --
        # the closing update is what matters here, not merely "some row".
        closing_rows = [
            row
            for _, rows, _ in transport.writes
            for row in rows
            if row.get("id") == old_fact_id and row.get("is_current") is False
        ]
        self.assertEqual(len(closing_rows), 1)

    def test_unresolvable_superseded_fact_id_raises(self):
        allocator, writer, _transport = _writer()
        write_entity(
            "ctx-1",
            DirectEntityInput(canonical_name="Sukuna", entity_type="character"),
            allocator,
            writer,
        )

        with self.assertRaises(ValueError):
            write_fact(
                "ctx-1",
                DirectFactInput(
                    predicate="is_alive",
                    subject_canonical_name="Sukuna",
                    object_literal="false",
                    superseded_fact_id="does-not-exist",
                ),
                allocator,
                writer,
                external_fact_id_store=FakeExternalFactIdStore(),
            )

    def test_superseded_fact_id_without_a_store_configured_raises(self):
        allocator, writer, _transport = _writer()
        write_entity(
            "ctx-1",
            DirectEntityInput(canonical_name="Sukuna", entity_type="character"),
            allocator,
            writer,
        )

        with self.assertRaises(ValueError):
            write_fact(
                "ctx-1",
                DirectFactInput(
                    predicate="is_alive",
                    subject_canonical_name="Sukuna",
                    object_literal="false",
                    superseded_fact_id="core-api-fact-1",
                ),
                allocator,
                writer,
            )


if __name__ == "__main__":
    unittest.main()
