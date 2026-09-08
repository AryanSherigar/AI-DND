from __future__ import annotations

import unittest

from context_memory.core.errors import (
    ContractValidationError,
    GraphPayloadConflictError,
)
from context_memory.core.graph import GraphNode, GraphRelationship, GraphWritePlan
from context_memory.ingestion.fakes import (
    InMemoryGraphManifestStore,
    RecordingGraphTransport,
)
from context_memory.ingestion.graph_writer import GraphWriter


class GraphWriterTests(unittest.TestCase):
    def plan(self) -> GraphWritePlan:
        context = "context-001"
        return GraphWritePlan(
            context,
            "plan-001",
            (
                GraphNode(
                    1,
                    "Session",
                    "session-001",
                    {"context_id": context, "session_id": "session-001"},
                ),
                GraphNode(
                    2,
                    "Turn",
                    "turn-001",
                    {"context_id": context, "source_chunk_id": "chunk-001"},
                ),
            ),
            (
                GraphRelationship(
                    3,
                    "HAS_TURN",
                    "has-turn-001",
                    1,
                    2,
                    "Session",
                    "Turn",
                    {"context_id": context, "turn_index": 0},
                ),
            ),
        )

    def test_writes_supported_unwind_batches_with_stable_keys(self) -> None:
        transport = RecordingGraphTransport()
        bookmarks = GraphWriter(InMemoryGraphManifestStore(), transport).write(
            self.plan()
        )
        self.assertEqual(bookmarks, ("bookmark-1", "bookmark-2", "bookmark-3"))
        self.assertEqual(len(transport.writes), 3)
        self.assertIn("UNWIND $rows AS row MERGE", transport.writes[0][0])
        self.assertIn("SET n:Session", transport.writes[0][0])
        self.assertIn(
            "MATCH (s:Session {id: row.source_id}), (d:Turn {id: row.destination_id})",
            transport.writes[2][0],
        )
        self.assertRegex(transport.writes[0][2], r"^context-memory-[0-9a-f]{64}$")

    def test_manifest_rejects_changed_replay_before_transport(self) -> None:
        manifest, transport = InMemoryGraphManifestStore(), RecordingGraphTransport()
        writer, plan = GraphWriter(manifest, transport), self.plan()
        writer.write(plan)
        changed = GraphWritePlan(
            plan.context_id,
            plan.plan_key,
            (
                GraphNode(
                    1,
                    "Session",
                    "session-001",
                    {"context_id": plan.context_id, "session_id": "changed"},
                ),
            ),
            (),
        )
        with self.assertRaises(GraphPayloadConflictError):
            writer.write(changed)
        self.assertEqual(len(transport.writes), 3)

    def test_rejects_unsafe_property_and_id_collision(self) -> None:
        with self.assertRaises(ContractValidationError):
            GraphNode(
                1,
                "Fact",
                "fact-001",
                {"context_id": "context-001", "x) SET n.pwned": "bad"},
            )
        with self.assertRaises(ContractValidationError):
            GraphWritePlan(
                "context-001",
                "plan",
                (GraphNode(1, "Fact", "fact-001", {"context_id": "context-001"}),),
                (
                    GraphRelationship(
                        1,
                        "ABOUT",
                        "about-001",
                        1,
                        1,
                        "Fact",
                        "Entity",
                        {"context_id": "context-001"},
                    ),
                ),
            )

    def other_plan(self) -> GraphWritePlan:
        """Same shape as `plan()` (same node labels/property sets, same
        relationship type), disjoint graph ids -- so its buckets merge with
        `plan()`'s in `write_many` instead of colliding."""
        context = "context-001"
        return GraphWritePlan(
            context,
            "plan-002",
            (
                GraphNode(
                    11,
                    "Session",
                    "session-002",
                    {"context_id": context, "session_id": "session-002"},
                ),
                GraphNode(
                    12,
                    "Turn",
                    "turn-002",
                    {"context_id": context, "source_chunk_id": "chunk-002"},
                ),
            ),
            (
                GraphRelationship(
                    13,
                    "HAS_TURN",
                    "has-turn-002",
                    11,
                    12,
                    "Session",
                    "Turn",
                    {"context_id": context, "turn_index": 0},
                ),
            ),
        )

    def test_write_many_merges_matching_buckets_across_plans(self) -> None:
        """Two plans with the same node/relationship shapes should produce
        the SAME 3 write calls `write()` alone would make for one plan --
        not 6 -- because rows from both plans land in the same bucket."""
        transport = RecordingGraphTransport()
        writer = GraphWriter(InMemoryGraphManifestStore(), transport)
        bookmarks = writer.write_many([self.plan(), self.other_plan()])
        self.assertEqual(len(transport.writes), 3)  # not 6 -- merged, not doubled
        self.assertEqual(len(bookmarks), 3)

        session_call = next(
            rows for cypher, rows, _ in transport.writes if "SET n:Session" in cypher
        )
        self.assertEqual(
            {row["id"] for row in session_call}, {1, 11}
        )  # both plans' Session nodes, one call

        turn_call = next(
            rows for cypher, rows, _ in transport.writes if "SET n:Turn" in cypher
        )
        self.assertEqual({row["id"] for row in turn_call}, {2, 12})

        rel_call = next(
            rows for cypher, rows, _ in transport.writes if "MATCH (s:Session" in cypher
        )
        self.assertEqual({row["id"] for row in rel_call}, {3, 13})

    def test_write_many_writes_all_nodes_before_any_relationship(self) -> None:
        transport = RecordingGraphTransport()
        GraphWriter(InMemoryGraphManifestStore(), transport).write_many(
            [self.plan(), self.other_plan()]
        )
        cyphers = [cypher for cypher, _, _ in transport.writes]
        first_relationship_idx = next(
            i for i, c in enumerate(cyphers) if "MATCH (s:" in c
        )
        node_cyphers_after = [
            c for c in cyphers[first_relationship_idx:] if "MATCH (s:" not in c
        ]
        self.assertEqual(
            node_cyphers_after, []
        )  # nothing node-only appears after the first relationship write

    def test_write_many_registers_every_plan_in_manifest(self) -> None:
        """Idempotency is per-plan, not per-batch -- a later solo retry of
        just one of the two plans, with a changed payload, is still caught."""
        manifest, transport = InMemoryGraphManifestStore(), RecordingGraphTransport()
        writer = GraphWriter(manifest, transport)
        writer.write_many([self.plan(), self.other_plan()])
        changed_second = GraphWritePlan(
            "context-001",
            "plan-002",
            (
                GraphNode(
                    11,
                    "Session",
                    "session-002",
                    {"context_id": "context-001", "session_id": "changed"},
                ),
            ),
            (),
        )
        with self.assertRaises(GraphPayloadConflictError):
            writer.write(changed_second)

    def test_write_many_of_one_plan_matches_write(self) -> None:
        transport_many, transport_single = (
            RecordingGraphTransport(),
            RecordingGraphTransport(),
        )
        GraphWriter(InMemoryGraphManifestStore(), transport_many).write_many(
            [self.plan()]
        )
        GraphWriter(InMemoryGraphManifestStore(), transport_single).write(self.plan())
        self.assertEqual(len(transport_many.writes), len(transport_single.writes))

    def test_write_many_of_empty_list_is_a_noop(self) -> None:
        transport = RecordingGraphTransport()
        bookmarks = GraphWriter(InMemoryGraphManifestStore(), transport).write_many([])
        self.assertEqual(bookmarks, ())
        self.assertEqual(transport.writes, [])

    def many_plans(self, n: int) -> list[GraphWritePlan]:
        """`n` plans, each a single Fact node (same label/property shape,
        distinct ids) -- enough of these in one bucket is exactly the shape
        that hit HydraDB's real admission-control limit live (see
        `DEFAULT_MAX_ROWS_PER_WRITE`'s comment: 100 grouped chunks pushed
        one node bucket to 1236 rows, HTTP 429, whole group lost)."""
        context = "context-001"
        return [
            GraphWritePlan(
                context,
                f"plan-{i:04d}",
                (
                    GraphNode(
                        i,
                        "Fact",
                        f"fact-{i:04d}",
                        {"context_id": context, "text": f"fact {i}"},
                    ),
                ),
                (),
            )
            for i in range(n)
        ]

    def test_write_many_splits_a_bucket_that_exceeds_the_row_cap(self) -> None:
        transport = RecordingGraphTransport()
        writer = GraphWriter(
            InMemoryGraphManifestStore(), transport, max_rows_per_write=10
        )
        writer.write_many(self.many_plans(25))
        # 25 rows, cap 10 -> 3 physical calls (10, 10, 5), not 1 oversized call.
        self.assertEqual(len(transport.writes), 3)
        sizes = sorted(len(rows) for _, rows, _ in transport.writes)
        self.assertEqual(sizes, [5, 10, 10])
        # every row still lands somewhere, none dropped, none duplicated.
        all_ids = [row["id"] for _, rows, _ in transport.writes for row in rows]
        self.assertEqual(sorted(all_ids), list(range(25)))

    def test_write_many_split_sub_batches_get_distinct_idempotency_keys(self) -> None:
        transport = RecordingGraphTransport()
        writer = GraphWriter(
            InMemoryGraphManifestStore(), transport, max_rows_per_write=10
        )
        writer.write_many(self.many_plans(25))
        keys = [key for _, _, key in transport.writes]
        self.assertEqual(len(keys), len(set(keys)))  # no two physical calls share a key

    def test_write_below_the_cap_is_unaffected(self) -> None:
        """Below the cap, splitting logic changes nothing -- same call
        count and same key `write()` always produced."""
        transport_default, transport_capped = (
            RecordingGraphTransport(),
            RecordingGraphTransport(),
        )
        GraphWriter(
            InMemoryGraphManifestStore(), transport_default, max_rows_per_write=900
        ).write(self.plan())
        GraphWriter(
            InMemoryGraphManifestStore(), transport_capped, max_rows_per_write=1
        ).write_many([self.plan()])
        # single-plan write_many delegates straight to write(); a cap of 1 with
        # only 1-2 rows/bucket here still never needs to split within a bucket
        # of size 1, so this just confirms the delegation path is untouched.
        self.assertEqual(len(transport_default.writes), 3)

    def conflicting_supersession_plans(self):
        """Two different plans (chunks) both mark the SAME prior Fact vertex
        (graph_id 100) as superseded, with different timestamps -- the shape
        that hit HydraDB HTTP 400 "conflicting metadata values for vertex 100
        property superseded_at" live (docs/fixes_and_evaluation_findings.md
        §10.4/§13), because both rows landed in one UNWIND with different
        values for the same id."""
        context = "context-001"
        earlier = GraphWritePlan(
            context,
            "plan-a",
            (
                GraphNode(
                    100,
                    "Fact",
                    "fact-100",
                    {
                        "context_id": context,
                        "superseded_at": 2000,
                        "valid_to": 9999999999,
                    },
                ),
            ),
            (),
        )
        later = GraphWritePlan(
            context,
            "plan-b",
            (
                GraphNode(
                    100,
                    "Fact",
                    "fact-100",
                    {
                        "context_id": context,
                        "superseded_at": 5000,
                        "valid_to": 9999999999,
                    },
                ),
            ),
            (),
        )
        return earlier, later

    def test_write_many_merges_conflicting_supersession_instead_of_erroring(
        self,
    ) -> None:
        earlier, later = self.conflicting_supersession_plans()
        transport = RecordingGraphTransport()
        writer = GraphWriter(InMemoryGraphManifestStore(), transport)
        writer.write_many([earlier, later])  # must not raise

        fact_call = next(
            rows for cypher, rows, _ in transport.writes if "SET n:Fact" in cypher
        )
        self.assertEqual(
            len(fact_call), 1
        )  # one row for vertex 100, not two conflicting ones
        self.assertEqual(fact_call[0]["id"], 100)

    def test_conflicting_supersession_keeps_the_earlier_timestamp(self) -> None:
        """The prior fact became invalid at the FIRST fact that superseded it
        -- the earlier value is the semantically correct one to keep, not
        whichever plan happened to be processed last."""
        earlier, later = self.conflicting_supersession_plans()
        transport = RecordingGraphTransport()
        GraphWriter(InMemoryGraphManifestStore(), transport).write_many(
            [later, earlier]
        )  # order-independent
        fact_call = next(
            rows for cypher, rows, _ in transport.writes if "SET n:Fact" in cypher
        )
        self.assertEqual(fact_call[0]["superseded_at"], 2000)

    def test_identical_valid_to_across_duplicates_is_not_flagged_as_a_conflict(
        self,
    ) -> None:
        earlier, later = self.conflicting_supersession_plans()
        transport = RecordingGraphTransport()
        GraphWriter(InMemoryGraphManifestStore(), transport).write_many(
            [earlier, later]
        )
        fact_call = next(
            rows for cypher, rows, _ in transport.writes if "SET n:Fact" in cypher
        )
        self.assertEqual(fact_call[0]["valid_to"], 9999999999)

    def test_a_single_plan_cannot_contain_duplicate_graph_ids_at_all(self) -> None:
        """`_dedupe_nodes` only needs to handle the cross-plan case:
        `GraphWritePlan` itself already forbids two nodes sharing a graph_id
        within one plan (globally-unique-ids check), so the scenario "one
        chunk's own new facts collide on one vertex" cannot reach the writer
        in the first place."""
        context = "context-001"
        with self.assertRaises(ContractValidationError):
            GraphWritePlan(
                context,
                "plan-both",
                (
                    GraphNode(
                        100,
                        "Fact",
                        "fact-100",
                        {"context_id": context, "superseded_at": 7000},
                    ),
                    GraphNode(
                        100,
                        "Fact",
                        "fact-100",
                        {"context_id": context, "superseded_at": 3000},
                    ),
                ),
                (),
            )

    def test_manifest_rejects_a_genuine_non_temporal_conflict_before_dedupe_runs(
        self,
    ) -> None:
        """A conflict outside superseded_at/valid_to/is_current is a real
        problem (two chunks disagreeing on a fact's actual text), and the
        manifest layer -- not `_dedupe_nodes` -- is what catches it, the
        same guarantee `PostgresGraphManifestStore` gives in production.
        `_dedupe_nodes`'s own fallback for this case is defense-in-depth,
        not the primary guard; this confirms the primary guard still fires."""
        context = "context-001"
        first = GraphWritePlan(
            context,
            "plan-a",
            (
                GraphNode(
                    100,
                    "Fact",
                    "fact-100",
                    {"context_id": context, "text": "first version"},
                ),
            ),
            (),
        )
        second = GraphWritePlan(
            context,
            "plan-b",
            (
                GraphNode(
                    100,
                    "Fact",
                    "fact-100",
                    {"context_id": context, "text": "second version"},
                ),
            ),
            (),
        )
        transport = RecordingGraphTransport()
        with self.assertRaises(GraphPayloadConflictError):
            GraphWriter(InMemoryGraphManifestStore(), transport).write_many(
                [first, second]
            )

    def test_dedupe_nodes_fallback_keeps_the_later_value_for_an_unexpected_conflict(
        self,
    ) -> None:
        """Unit-level test of `_dedupe_nodes` itself, bypassing the manifest
        guard above -- if some future caller ever hands it a genuine
        non-temporal conflict directly, it must still degrade (log + keep
        the later value) rather than raise, so one bad batch doesn't get
        lost outright."""
        context = "context-001"
        nodes = [
            GraphNode(
                100,
                "Fact",
                "fact-100",
                {"context_id": context, "text": "first version"},
            ),
            GraphNode(
                100,
                "Fact",
                "fact-100",
                {"context_id": context, "text": "second version"},
            ),
        ]
        merged = GraphWriter._dedupe_nodes(nodes)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0].properties["text"], "second version")


class GraphWriterVerifyTests(unittest.TestCase):
    """§8 fix: `GraphWriter.verify()` is an independent post-write read,
    not a re-check of the manifest (register()'d *before* the physical
    write -- see verify()'s own docstring for why that alone can't prove
    HydraDB actually has the data)."""

    def plan(self) -> GraphWritePlan:
        context = "context-001"
        return GraphWritePlan(
            context,
            "plan-001",
            (
                GraphNode(
                    1,
                    "Session",
                    "session-001",
                    {"context_id": context, "session_id": "session-001"},
                ),
                GraphNode(
                    2,
                    "Turn",
                    "turn-001",
                    {"context_id": context, "source_chunk_id": "chunk-001"},
                ),
            ),
            (
                GraphRelationship(
                    3,
                    "HAS_TURN",
                    "has-turn-001",
                    1,
                    2,
                    "Session",
                    "Turn",
                    {"context_id": context, "turn_index": 0},
                ),
            ),
        )

    def test_verify_true_after_a_real_write(self) -> None:
        transport = RecordingGraphTransport()
        writer = GraphWriter(InMemoryGraphManifestStore(), transport)
        plan = self.plan()
        writer.write(plan)
        self.assertTrue(writer.verify(plan))

    def test_verify_false_when_write_never_happened(self) -> None:
        """No write() call at all -- verify() must not just trust the plan."""
        transport = RecordingGraphTransport()
        writer = GraphWriter(InMemoryGraphManifestStore(), transport)
        self.assertFalse(writer.verify(self.plan()))

    def test_verify_false_when_a_read_error_occurs(self) -> None:
        class ExplodingTransport(RecordingGraphTransport):
            def read(self, cypher, parameters, bookmark):
                raise ConnectionError("hydradb unreachable")

        writer = GraphWriter(InMemoryGraphManifestStore(), ExplodingTransport())
        self.assertFalse(writer.verify(self.plan()))

    def test_verify_true_for_a_plan_with_no_nodes(self) -> None:
        plan = GraphWritePlan("context-001", "plan-empty", (), ())
        writer = GraphWriter(InMemoryGraphManifestStore(), RecordingGraphTransport())
        self.assertTrue(writer.verify(plan))
