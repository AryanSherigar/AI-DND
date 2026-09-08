from __future__ import annotations

import unittest
from datetime import datetime, timezone

from context_memory.core.enums import MemoryScope, MemoryType
from context_memory.core.models import (
    ContextBatch,
    ContextRecord,
    EntityCandidate,
    ExtractedMemoryCandidate,
    SourceDescriptor,
    SourceSpan,
    TemporalBounds,
)
from context_memory.core.resolution import EntityProfile
from context_memory.core.validation import chunk_from_record
from context_memory.ingestion.extraction import ExtractionResult
from context_memory.ingestion.fakes import InMemoryGraphIdAllocator
from context_memory.ingestion.graph_plan_builder import GraphPlanBuilder


def _candidate(entities=(), subject=None, object=None) -> ExtractedMemoryCandidate:
    return ExtractedMemoryCandidate(
        candidate_id="fact-001",
        text="Max likes walks",
        memory_type=MemoryType.SEMANTIC,
        scope_type=MemoryScope.SESSION,
        scope_id="session-001",
        source_span=SourceSpan("record-001", 0, 3),
        confidence=0.9,
        temporal=TemporalBounds(datetime(2026, 1, 10, 9, tzinfo=timezone.utc)),
        entities=entities,
        subject=subject,
        object=object,
    )


class GraphPlanBuilderTests(unittest.TestCase):
    def setUp(self) -> None:
        self.allocator = InMemoryGraphIdAllocator()
        self.builder = GraphPlanBuilder(self.allocator)
        record = ContextRecord(
            record_id="record-001",
            session_id="session-001",
            occurred_at=datetime(2026, 1, 10, 9, tzinfo=timezone.utc),
            content="Max likes walks",
        )
        batch = ContextBatch(
            "ingestion-001",
            "context-001",
            SourceDescriptor("fixture", "fixture-001"),
            (record,),
        )
        self.chunk = chunk_from_record(batch, record)

    def test_no_candidates_still_writes_session_and_turn(self) -> None:
        extraction = ExtractionResult("attempt-1", (), ())
        plan = self.builder.build(self.chunk, extraction, resolve=lambda *a: None)
        labels = {node.label for node in plan.nodes}
        self.assertEqual(labels, {"Session", "Turn", "Entity"})
        self.assertEqual(
            {r.relationship_type for r in plan.relationships}, {"HAS_TURN"}
        )

    def test_unresolved_entity_mention_creates_no_about_edge(self) -> None:
        candidate = _candidate(entities=(EntityCandidate("Max", "pet"),))
        extraction = ExtractionResult("attempt-1", (candidate,), ())
        plan = self.builder.build(
            self.chunk, extraction, resolve=lambda *a: None
        )  # always unresolved
        about_edges = [r for r in plan.relationships if r.relationship_type == "ABOUT"]
        self.assertEqual(len(about_edges), 0)
        # Note: speaker Entity is still created, but no ABOUT edge
        speaker_entities = [
            n
            for n in plan.nodes
            if n.label == "Entity" and n.properties.get("entity_type") == "speaker"
        ]
        self.assertEqual(len(speaker_entities), 1)

    def test_resolved_entity_creates_entity_node_and_about_edge(self) -> None:
        candidate = _candidate(entities=(EntityCandidate("Max", "pet"),))
        extraction = ExtractionResult("attempt-1", (candidate,), ())
        profile = EntityProfile(99, self.chunk.context_id, "Max (pet)", "pet")
        plan = self.builder.build(
            self.chunk, extraction, resolve=lambda cid, surface, etype: profile
        )
        entity_nodes = [
            n
            for n in plan.nodes
            if n.label == "Entity" and n.properties.get("entity_type") != "speaker"
        ]
        self.assertEqual(len(entity_nodes), 1)
        self.assertEqual(entity_nodes[0].properties["canonical_name"], "Max (pet)")
        about_edges = [r for r in plan.relationships if r.relationship_type == "ABOUT"]
        self.assertEqual(len(about_edges), 1)
        stated_by = [
            r for r in plan.relationships if r.relationship_type == "STATED_BY"
        ]
        self.assertEqual(len(stated_by), 1)

    def test_fact_node_carries_subject_and_object_literal_properties(self) -> None:
        """§9 fix: the real triple components end up as scalar properties on
        the Fact node itself, named to match `direct_authoring.write_fact`'s
        `object_literal` convention -- one schema regardless of fact source."""
        candidate = _candidate(
            entities=(EntityCandidate("Max", "pet"),), subject="Max", object="the park"
        )
        extraction = ExtractionResult("attempt-1", (candidate,), ())
        profile = EntityProfile(99, self.chunk.context_id, "Max (pet)", "pet")
        plan = self.builder.build(
            self.chunk, extraction, resolve=lambda cid, surface, etype: profile
        )
        fact_nodes = [n for n in plan.nodes if n.label == "Fact"]
        self.assertEqual(len(fact_nodes), 1)
        self.assertEqual(fact_nodes[0].properties["subject"], "Max")
        self.assertEqual(fact_nodes[0].properties["object_literal"], "the park")

    def test_fact_node_omits_subject_and_object_when_extraction_left_them_blank(
        self,
    ) -> None:
        candidate = _candidate(entities=(EntityCandidate("Max", "pet"),))
        extraction = ExtractionResult("attempt-1", (candidate,), ())
        profile = EntityProfile(99, self.chunk.context_id, "Max (pet)", "pet")
        plan = self.builder.build(
            self.chunk, extraction, resolve=lambda cid, surface, etype: profile
        )
        fact_nodes = [n for n in plan.nodes if n.label == "Fact"]
        self.assertNotIn("subject", fact_nodes[0].properties)
        self.assertNotIn("object_literal", fact_nodes[0].properties)

    def test_aliases_produce_alias_nodes_and_has_alias_edges(self) -> None:
        entity_id = self.allocator.allocate_graph_id(
            "entity", "context-001", "entity:max"
        )
        profile = EntityProfile(
            entity_id, "context-001", "max", "pet", aliases=("my dog", "the retriever")
        )
        candidate = _candidate(entities=(EntityCandidate("my dog", "pet"),))
        extraction = ExtractionResult("attempt-1", (candidate,), ())
        plan = self.builder.build(
            self.chunk, extraction, resolve=lambda cid, surface, etype: profile
        )
        alias_nodes = [n for n in plan.nodes if n.label == "Alias"]
        has_alias = [
            r for r in plan.relationships if r.relationship_type == "HAS_ALIAS"
        ]
        self.assertEqual(len(alias_nodes), 2)
        self.assertEqual(len(has_alias), 2)

    def test_every_node_and_relationship_carries_context_id(self) -> None:
        entity_id = self.allocator.allocate_graph_id(
            "entity", "context-001", "entity:max"
        )
        profile = EntityProfile(
            entity_id, "context-001", "max", "pet", aliases=("my dog",)
        )
        candidate = _candidate(entities=(EntityCandidate("my dog", "pet"),))
        extraction = ExtractionResult("attempt-1", (candidate,), ())
        plan = self.builder.build(
            self.chunk, extraction, resolve=lambda cid, surface, etype: profile
        )
        for record in plan.records():
            self.assertEqual(record.properties["context_id"], "context-001")

    def test_repeated_build_is_deterministically_replayable(self) -> None:
        candidate = _candidate()
        extraction = ExtractionResult("attempt-1", (candidate,), ())
        plan_a = self.builder.build(self.chunk, extraction, resolve=lambda *a: None)
        plan_b = self.builder.build(self.chunk, extraction, resolve=lambda *a: None)
        self.assertEqual(
            {n.graph_id for n in plan_a.nodes}, {n.graph_id for n in plan_b.nodes}
        )
        self.assertEqual(plan_a.nodes, plan_b.nodes)

    def test_speaker_node_does_not_collide_with_extracted_entity_of_same_name(
        self,
    ) -> None:
        """The extractor genuinely emits "user"/"assistant" as entity surfaces.
        When the speaker node also lived at `entity:{role}`, both resolved to the
        same logical_key and the same allocated graph_id but carried different
        entity_type values ("speaker" vs "other") -- a same-key/different-payload
        pair that PostgresGraphManifestStore rejects by design. That aborted a
        real LongMemEval run with GraphPayloadConflictError on
        `node entity:assistant`."""
        role = self.chunk.actor_role or "unknown"
        profile = EntityProfile(
            self.allocator.allocate_graph_id("entity", "context-001", f"entity:{role}"),
            "context-001",
            role,
            "other",
        )
        candidate = _candidate(entities=(EntityCandidate(role, "other"),))
        extraction = ExtractionResult("attempt-1", (candidate,), ())
        plan = self.builder.build(self.chunk, extraction, resolve=lambda *a: profile)

        by_key = {n.logical_key: n for n in plan.nodes}
        self.assertIn(f"speaker:{role}", by_key)
        self.assertIn(f"entity:{role}", by_key)
        self.assertEqual(by_key[f"speaker:{role}"].properties["entity_type"], "speaker")
        self.assertEqual(by_key[f"entity:{role}"].properties["entity_type"], "other")
        # Distinct identities, so neither can overwrite the other's payload.
        self.assertNotEqual(
            by_key[f"speaker:{role}"].graph_id, by_key[f"entity:{role}"].graph_id
        )

    def test_supersedes_edge_created(self) -> None:
        from context_memory.core.resolution import (
            FactState,
            TemporalRelation,
            TemporalUpdateDecision,
        )

        class FakeTemporalClassifier:
            def classify(self, new_fact, prior_fact):
                return TemporalUpdateDecision(
                    TemporalRelation.STATE_CHANGE,
                    "test",
                    prior_superseded_at=new_fact.observed_at,
                )

        entity_id = self.allocator.allocate_graph_id(
            "entity", "context-001", "entity:max"
        )
        profile = EntityProfile(entity_id, "context-001", "max", "pet")
        candidate = ExtractedMemoryCandidate(
            candidate_id="fact-new",
            text="Max likes running",
            memory_type=MemoryType.SEMANTIC,
            scope_type=MemoryScope.SESSION,
            scope_id="session-001",
            source_span=SourceSpan("record-001", 0, 3),
            confidence=0.9,
            temporal=TemporalBounds(datetime(2026, 1, 10, 9, tzinfo=timezone.utc)),
            entities=(EntityCandidate("Max", "pet"),),
            action="UPDATE",
            predicate_key="likes",
        )
        extraction = ExtractionResult("attempt-1", (candidate,), ())
        prior_fact = FactState(
            "fact-old",
            entity_id,
            "likes",
            "Max likes walking",
            datetime(2025, 1, 1, tzinfo=timezone.utc),
        )

        def find_existing(context, subject, predicate):
            if subject == entity_id and predicate == "likes":
                return [prior_fact]
            return []

        plan = self.builder.build(
            self.chunk,
            extraction,
            lambda cid, s, e: profile,
            update_classifier=FakeTemporalClassifier(),
            find_existing_facts=find_existing,
        )

        supersedes = [
            r for r in plan.relationships if r.relationship_type == "SUPERSEDES"
        ]
        self.assertEqual(len(supersedes), 1)
        self.assertEqual(
            supersedes[0].destination_id,
            self.allocator.allocate_graph_id("fact", "context-001", "fact:fact-old"),
        )

        old_nodes = [
            n for n in plan.nodes if n.graph_id == supersedes[0].destination_id
        ]
        self.assertEqual(len(old_nodes), 1)
        self.assertEqual(old_nodes[0].properties["is_current"], False)

    def test_resolve_many_path_produces_the_same_plan_as_the_per_mention_path(
        self,
    ) -> None:
        """`resolve_many`, when supplied, replaces the per-mention `resolve`
        calls entirely (see build()'s docstring for the batched pre-resolve
        pass) -- the resulting plan must be identical either way."""
        candidate = _candidate(entities=(EntityCandidate("Max", "pet"),))
        extraction = ExtractionResult("attempt-1", (candidate,), ())
        profile = EntityProfile(99, self.chunk.context_id, "max", "pet")

        plan_via_resolve = self.builder.build(
            self.chunk, extraction, resolve=lambda cid, surface, etype: profile
        )

        calls: list[tuple[str, tuple[tuple[str, str], ...]]] = []

        def resolve_many(context_id, mentions):
            calls.append((context_id, tuple(mentions)))
            return [profile for _ in mentions]

        plan_via_batch = self.builder.build(
            self.chunk, extraction, resolve=lambda *a: None, resolve_many=resolve_many
        )

        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0], (self.chunk.context_id, (("Max", "pet"),)))
        self.assertEqual(plan_via_resolve.nodes, plan_via_batch.nodes)
        self.assertEqual(plan_via_resolve.relationships, plan_via_batch.relationships)

    def test_resolve_many_mentions_map_back_to_the_correct_fact_in_order(self) -> None:
        """Two facts, two different entities in one chunk -- the flat
        mention list `resolve_many` receives must map back to the right
        fact's ABOUT edge, not get swapped between them."""
        max_candidate = ExtractedMemoryCandidate(
            candidate_id="fact-max",
            text="Max likes walks",
            memory_type=MemoryType.SEMANTIC,
            scope_type=MemoryScope.SESSION,
            scope_id="session-001",
            source_span=SourceSpan("record-001", 0, 3),
            confidence=0.9,
            temporal=TemporalBounds(datetime(2026, 1, 10, 9, tzinfo=timezone.utc)),
            entities=(EntityCandidate("Max", "pet"),),
        )
        rex_candidate = ExtractedMemoryCandidate(
            candidate_id="fact-rex",
            text="Rex likes running",
            memory_type=MemoryType.SEMANTIC,
            scope_type=MemoryScope.SESSION,
            scope_id="session-001",
            source_span=SourceSpan("record-001", 0, 3),
            confidence=0.9,
            temporal=TemporalBounds(datetime(2026, 1, 10, 9, tzinfo=timezone.utc)),
            entities=(EntityCandidate("Rex", "pet"),),
        )
        extraction = ExtractionResult("attempt-1", (max_candidate, rex_candidate), ())
        max_profile = EntityProfile(101, self.chunk.context_id, "max", "pet")
        rex_profile = EntityProfile(102, self.chunk.context_id, "rex", "pet")

        def resolve_many(context_id, mentions):
            by_surface = {"Max": max_profile, "Rex": rex_profile}
            return [by_surface[surface] for surface, _ in mentions]

        plan = self.builder.build(
            self.chunk, extraction, resolve=lambda *a: None, resolve_many=resolve_many
        )

        about_edges = {
            r.source_id: r for r in plan.relationships if r.relationship_type == "ABOUT"
        }
        max_fact_id = self.allocator.allocate_graph_id(
            "fact", "context-001", "fact:fact-max"
        )
        rex_fact_id = self.allocator.allocate_graph_id(
            "fact", "context-001", "fact:fact-rex"
        )
        self.assertEqual(
            about_edges[max_fact_id].destination_id, 101
        )  # Max's fact links to Max's profile, not Rex's
        self.assertEqual(about_edges[rex_fact_id].destination_id, 102)

    def test_no_entities_in_chunk_never_calls_resolve_many(self) -> None:
        extraction = ExtractionResult("attempt-1", (), ())
        called = []
        self.builder.build(
            self.chunk,
            extraction,
            resolve=lambda *a: None,
            resolve_many=lambda *a: called.append(a) or [],
        )
        self.assertEqual(called, [])


if __name__ == "__main__":
    unittest.main()
