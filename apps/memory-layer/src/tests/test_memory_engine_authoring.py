"""MemoryEngine.write_template_entity/write_template_fact/ingest_template_lore
/clone_playthrough_space -- Milestone 3's engine-layer glue over
direct_authoring.py/template_clone.py (already unit-tested on their own in
test_direct_authoring.py/test_template_clone.py). This file only checks the
wiring: the right dependency is required, the right module-level function
gets called with the right arguments.
"""

from __future__ import annotations

import unittest

from context_memory.cloning.template_clone import CloneResult
from context_memory.engine import MemoryEngine
from context_memory.ingestion.direct_authoring import DirectEntityInput, DirectFactInput
from context_memory.ingestion.fakes import InMemoryGraphIdAllocator, InMemoryGraphManifestStore
from context_memory.ingestion.graph_writer import GraphWriter


class FakeOrchestrator:
    def __init__(self):
        self.batches = []

    def run_batch(self, batch):
        self.batches.append(batch)


class FakeHydraTransport:
    def __init__(self, rows_by_query=None):
        self._rows = rows_by_query or {}
        self.reads = []

    def read(self, cypher, parameters, bookmark):
        self.reads.append(cypher)
        for needle, rows in self._rows.items():
            if needle in cypher:
                return rows
        return []

    def write(self, cypher, rows, idempotency_key):
        raise AssertionError("clone should read from this transport, not write to it")


def _writer():
    return GraphWriter(InMemoryGraphManifestStore(), _RecordingWriteTransport())


class _RecordingWriteTransport:
    def __init__(self):
        self.writes = []

    def write(self, cypher, rows, idempotency_key):
        self.writes.append((cypher, list(rows)))
        return "bookmark-1"

    def read(self, cypher, parameters, bookmark):
        raise AssertionError("write transport should never be read from directly")


def _engine(**authoring_kwargs) -> tuple[MemoryEngine, FakeOrchestrator]:
    orchestrator = FakeOrchestrator()
    engine = MemoryEngine(orchestrator, retrieval_engine=None, llm_client=None, pool=object(), **authoring_kwargs)
    return engine, orchestrator


class MissingDependencyTests(unittest.TestCase):
    def test_write_template_entity_without_deps_raises(self):
        engine, _ = _engine()
        with self.assertRaises(RuntimeError):
            engine.write_template_entity("ctx", DirectEntityInput(canonical_name="Sukuna", entity_type="character"))

    def test_clone_without_hydra_transport_raises(self):
        engine, _ = _engine(
            graph_id_allocator=InMemoryGraphIdAllocator(), authoring_graph_writer=_writer()
        )
        with self.assertRaises(RuntimeError):
            engine.clone_playthrough_space("template-ctx", "playthrough-ctx")


class DirectAuthoringWiringTests(unittest.TestCase):
    def test_write_template_entity_reaches_the_graph_writer(self):
        writer = _writer()
        engine, _ = _engine(graph_id_allocator=InMemoryGraphIdAllocator(), authoring_graph_writer=writer)

        graph_id = engine.write_template_entity(
            "scenario-template::s1", DirectEntityInput(canonical_name="Sukuna", entity_type="character")
        )

        self.assertIsInstance(graph_id, int)
        self.assertEqual(len(writer._transport.writes), 1)

    def test_write_template_fact_reaches_the_graph_writer(self):
        allocator = InMemoryGraphIdAllocator()
        writer = _writer()
        engine, _ = _engine(graph_id_allocator=allocator, authoring_graph_writer=writer)
        engine.write_template_entity("ctx", DirectEntityInput(canonical_name="Sukuna", entity_type="character"))

        engine.write_template_fact(
            "ctx", DirectFactInput(predicate="is_strongest", subject_canonical_name="Sukuna", object_literal="true")
        )

        fact_writes = [w for w in writer._transport.writes if "Fact" in w[0] and "Entity" not in w[0]]
        self.assertEqual(len(fact_writes), 1)


class IngestTemplateLoreTests(unittest.TestCase):
    def test_runs_synchronously_through_the_orchestrator_not_the_executor(self):
        # AI-DND memory-layer contract fix: ingest_template_lore now calls
        # begin_template_republish first (archives any prior version's
        # facts before re-extracting), which needs the same authoring deps
        # write_template_fact/entity already require.
        engine, orchestrator = _engine(
            graph_id_allocator=InMemoryGraphIdAllocator(), authoring_graph_writer=_writer(),
            hydra_transport=FakeHydraTransport(),
        )

        engine.ingest_template_lore("scenario-template::s1", "A cursed realm where Sukuna rules.")

        self.assertEqual(len(orchestrator.batches), 1)
        batch = orchestrator.batches[0]
        self.assertEqual(batch.context_id, "scenario-template::s1")
        self.assertEqual(batch.records[0].content, "A cursed realm where Sukuna rules.")
        # record_id is now content-addressed (a republish fix) -- still
        # namespaced under this context's own template-lore prefix.
        self.assertTrue(batch.records[0].record_id.startswith("scenario-template::s1:template-lore:"))

    def test_republish_with_different_lore_text_does_not_collide(self):
        """The bug this fix closes: before content-addressing, a second
        publish of the same scenario with EDITED lore text reused the same
        fixed record_id, and chunk immutability rejected it outright."""
        engine, orchestrator = _engine(
            graph_id_allocator=InMemoryGraphIdAllocator(), authoring_graph_writer=_writer(),
            hydra_transport=FakeHydraTransport(),
        )

        engine.ingest_template_lore("scenario-template::s1", "A cursed realm where Sukuna rules.")
        engine.ingest_template_lore("scenario-template::s1", "A peaceful realm where Sukuna was sealed away.")

        self.assertEqual(len(orchestrator.batches), 2)
        first_id = orchestrator.batches[0].records[0].record_id
        second_id = orchestrator.batches[1].records[0].record_id
        self.assertNotEqual(first_id, second_id)

    def test_republish_archives_facts_from_the_prior_version(self):
        transport = FakeHydraTransport(rows_by_query={
            "MATCH (f:Fact": [{"id": 7, "logical_key": "fact:old-lore-fact"}],
        })
        engine, orchestrator = _engine(
            graph_id_allocator=InMemoryGraphIdAllocator(), authoring_graph_writer=_writer(),
            hydra_transport=transport,
        )

        engine.ingest_template_lore("scenario-template::s1", "A new version of the lore.")

        archived_rows = [
            row for _, rows in engine._authoring_graph_writer._transport.writes for row in rows
            if row.get("id") == 7
        ]
        self.assertEqual(len(archived_rows), 1)
        self.assertFalse(archived_rows[0]["is_current"])
        self.assertTrue(archived_rows[0]["archived"])


class ClonePlaythroughSpaceTests(unittest.TestCase):
    def test_delegates_to_template_clone_with_configured_deps(self):
        allocator = InMemoryGraphIdAllocator()
        writer = _writer()
        transport = FakeHydraTransport(rows_by_query={
            "MATCH (n:Entity": [{"id": 1, "logical_key": "entity:Sukuna", "canonical_name": "Sukuna", "entity_type": "character"}],
        })
        engine, _ = _engine(graph_id_allocator=allocator, authoring_graph_writer=writer, hydra_transport=transport)

        result = engine.clone_playthrough_space("scenario-template::s1", "playthrough-1")

        self.assertIsInstance(result, CloneResult)
        self.assertEqual(result.entities_cloned, 1)


class FakeFactMetadataStore:
    def __init__(self):
        self.puts: list[tuple[str, int, str | None, dict | None, str | None, bool]] = []
        self._by_context: dict[str, dict[int, tuple[str | None, dict | None, str | None, bool]]] = {}

    def put(self, context_id, fact_id, checkpoint, when_active, visible_to_participant_id=None, hidden=False):
        self.puts.append((context_id, fact_id, checkpoint, when_active, visible_to_participant_id, hidden))
        self._by_context.setdefault(context_id, {})[fact_id] = (checkpoint, when_active, visible_to_participant_id, hidden)

    def get_many(self, context_id, fact_ids):
        rows = self._by_context.get(context_id, {})
        return {fid: rows[fid] for fid in fact_ids if fid in rows}


class FakeCheckpointStore:
    def __init__(self):
        self.puts: list[tuple[str, list[str]]] = []

    def put(self, context_id, checkpoints):
        self.puts.append((context_id, list(checkpoints)))


class Milestone45WiringTests(unittest.TestCase):
    def test_write_template_fact_persists_when_active_and_checkpoint(self):
        fact_metadata_store = FakeFactMetadataStore()
        engine, _ = _engine(
            graph_id_allocator=InMemoryGraphIdAllocator(), authoring_graph_writer=_writer(),
            fact_metadata_store=fact_metadata_store,
        )
        engine.write_template_entity("ctx", DirectEntityInput(canonical_name="Sukuna", entity_type="character"))

        when_active = {"field": "player.health", "op": "<", "value": 5}
        fact_id = engine.write_template_fact(
            "ctx",
            DirectFactInput(
                predicate="is_pursued_by_ghost", subject_canonical_name="Sukuna", object_literal="true",
                when_active=when_active, checkpoint="chapter_2",
            ),
        )

        self.assertEqual(fact_metadata_store.puts, [("ctx", fact_id, "chapter_2", when_active, None, False)])

    def test_write_template_fact_persists_participant_visibility_alone(self):
        """§5 fix: `visible_to_participant_id` alone (no when_active/
        checkpoint) must still trigger a metadata write -- a fact restricted
        to one participant needs that persisted even with nothing else set."""
        fact_metadata_store = FakeFactMetadataStore()
        engine, _ = _engine(
            graph_id_allocator=InMemoryGraphIdAllocator(), authoring_graph_writer=_writer(),
            fact_metadata_store=fact_metadata_store,
        )
        engine.write_template_entity("ctx", DirectEntityInput(canonical_name="Sukuna", entity_type="character"))

        fact_id = engine.write_template_fact(
            "ctx",
            DirectFactInput(
                predicate="knows_secret", subject_canonical_name="Sukuna", object_literal="true",
                visible_to_participant_id="participant-1",
            ),
        )

        self.assertEqual(fact_metadata_store.puts, [("ctx", fact_id, None, None, "participant-1", False)])

    def test_write_template_fact_without_when_active_or_checkpoint_writes_no_metadata(self):
        fact_metadata_store = FakeFactMetadataStore()
        engine, _ = _engine(
            graph_id_allocator=InMemoryGraphIdAllocator(), authoring_graph_writer=_writer(),
            fact_metadata_store=fact_metadata_store,
        )
        engine.write_template_entity("ctx", DirectEntityInput(canonical_name="Sukuna", entity_type="character"))

        engine.write_template_fact(
            "ctx", DirectFactInput(predicate="is_strongest", subject_canonical_name="Sukuna", object_literal="true")
        )

        self.assertEqual(fact_metadata_store.puts, [])

    def test_write_scenario_checkpoints_delegates_to_checkpoint_store(self):
        checkpoint_store = FakeCheckpointStore()
        engine, _ = _engine(checkpoint_store=checkpoint_store)

        engine.write_scenario_checkpoints("scenario-template::s1", ["chapter_1", "chapter_2", "chapter_3"])

        self.assertEqual(checkpoint_store.puts, [("scenario-template::s1", ["chapter_1", "chapter_2", "chapter_3"])])

    # clone_playthrough_space's fact-metadata cloning (Milestones 4-5) is
    # covered directly in test_template_clone.py::FactMetadataCloneTests,
    # against template_clone.clone()'s own fixtures -- MemoryEngine's role
    # here is only to pass its configured fact_metadata_store through,
    # already exercised by ClonePlaythroughSpaceTests above.


class GetEntityTests(unittest.TestCase):
    """AI-DND memory-layer contract §4.5: GET /v1/memory/entity/{entity_id}."""

    def test_returns_the_entity_when_found(self):
        transport = FakeHydraTransport(rows_by_query={
            "MATCH (n:Entity": [{
                "id": 1, "canonical_name": "Sukuna", "entity_type": "character",
                "description": "A cursed spirit", "aliases": "King of Curses, Ryomen",
            }],
        })
        engine, _ = _engine(hydra_transport=transport)

        entity = engine.get_entity("ctx-1", "Sukuna")

        self.assertEqual(entity["canonical_name"], "Sukuna")
        self.assertEqual(entity["entity_type"], "character")
        self.assertEqual(entity["aliases"], ["King of Curses", "Ryomen"])

    def test_returns_none_when_not_found(self):
        engine, _ = _engine(hydra_transport=FakeHydraTransport())

        self.assertIsNone(engine.get_entity("ctx-1", "does-not-exist"))

    def test_raises_without_hydra_transport_configured(self):
        engine, _ = _engine()

        with self.assertRaises(RuntimeError):
            engine.get_entity("ctx-1", "Sukuna")

