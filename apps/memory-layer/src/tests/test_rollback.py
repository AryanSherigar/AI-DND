from __future__ import annotations

import unittest
from contextlib import nullcontext
from datetime import datetime, timezone

from context_memory.core.graph import GraphWritePlan
from context_memory.ingestion.rollback import RollbackService, SavePoint, SavePointStore, walk_restore_targets


class WalkRestoreTargetsTests(unittest.TestCase):
    def test_no_supersession_restores_nothing(self) -> None:
        self.assertEqual(walk_restore_targets(["a"], {}), set())

    def test_single_supersession_restores_direct_prior(self) -> None:
        # b superseded a (superseded_by: new -> prior)
        self.assertEqual(walk_restore_targets(["b"], {"b": "a"}), {"a"})

    def test_chain_entirely_within_archived_window_restores_root_ancestor(self) -> None:
        # a -> b -> c -> d, all archived (created after cutoff): restore 'a's own prior.
        superseded_by = {"d": "c", "c": "b", "b": "a"}
        self.assertEqual(walk_restore_targets(["b", "c", "d"], superseded_by), {"a"})

    def test_chain_stops_at_first_non_archived_ancestor(self) -> None:
        # pre-cutoff: root -> a. post-cutoff: a -> b -> c. Rolling back c/b/a should
        # restore 'a' itself only if a is NOT archived; here a IS archived (created
        # after cutoff), so it restores 'root' (walking past a).
        superseded_by = {"c": "b", "b": "a", "a": "root"}
        self.assertEqual(walk_restore_targets(["a", "b", "c"], superseded_by), {"root"})

    def test_unrelated_archived_facts_produce_independent_restores(self) -> None:
        superseded_by = {"x": "p", "y": "q"}
        self.assertEqual(walk_restore_targets(["x", "y"], superseded_by), {"p", "q"})

    def test_archived_fact_with_no_supersession_restores_nothing_for_itself(self) -> None:
        self.assertEqual(walk_restore_targets(["a", "b"], {"b": "z"}), {"z"})


class FakeCursor:
    def __init__(self, connection: "FakeConnection") -> None:
        self._conn = connection
        self._result: list[tuple] | None = None

    def execute(self, query: str, params: tuple = ()) -> None:
        self._conn.executed.append((query, params))
        q = " ".join(query.split())
        if "FROM extracted_memory_candidates c JOIN extraction_attempts" in q:
            context_id, cutoff = params
            self._result = [
                (cid,) for cid, ctx, observed_at in self._conn.candidates
                if ctx == context_id and observed_at > cutoff
            ]
        elif "FROM graph_write_manifests" in q:
            self._result = [(lk,) for lk in self._conn.supersedes_logical_keys]
        elif "SELECT candidate_id, valid_to FROM extracted_memory_candidates" in q:
            (ids,) = params
            self._result = [
                (cid, valid_to) for cid, valid_to in self._conn.valid_to_by_id.items() if cid in ids
            ]
        elif "FROM graph_id_registry" in q:
            context_id, logical_keys = params
            self._result = [
                (lk, gid) for lk, gid in self._conn.graph_ids.items() if lk in logical_keys
            ]
        elif query.startswith("INSERT INTO save_points"):
            self._conn.save_points[params[0]] = params
        elif query.startswith("SELECT save_id, context_id"):
            if "WHERE save_id = %s" in query:
                row = self._conn.save_points.get(params[0])
                self._result = [row] if row else []
            else:
                self._result = [row for row in self._conn.save_points.values() if row[1] == params[0]]
        else:
            self._result = []

    def fetchone(self):
        return self._result[0] if self._result else None

    def fetchall(self):
        return self._result or []

    def __enter__(self) -> "FakeCursor":
        return self

    def __exit__(self, *exc) -> None:
        return None


class FakeConnection:
    def __init__(self) -> None:
        self.executed: list[tuple[str, tuple]] = []
        self.candidates: list[tuple[str, str, datetime]] = []  # (candidate_id, context_id, observed_at)
        self.supersedes_logical_keys: list[str] = []
        self.valid_to_by_id: dict[str, datetime | None] = {}
        self.graph_ids: dict[str, int] = {}
        self.save_points: dict[str, tuple] = {}

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    def transaction(self):
        return nullcontext()


class FakeGraphWriter:
    def __init__(self) -> None:
        self.plans: list[GraphWritePlan] = []

    def write(self, plan: GraphWritePlan) -> tuple[str, ...]:
        self.plans.append(plan)
        return ()


class SavePointStoreTests(unittest.TestCase):
    def test_create_then_get_round_trips(self) -> None:
        connection = FakeConnection()
        store = SavePointStore(connection)
        created = store.create("ctx-1", "sess-1", "before boss fight")
        fetched = store.get(created.save_id)
        self.assertEqual(fetched, created)

    def test_get_unknown_save_id_returns_none(self) -> None:
        self.assertIsNone(SavePointStore(FakeConnection()).get("nope"))


UTC = timezone.utc


class RollbackServiceTests(unittest.TestCase):
    def test_no_writes_after_save_point_is_a_no_op(self) -> None:
        connection = FakeConnection()
        writer = FakeGraphWriter()
        service = RollbackService(connection, writer)
        save_point = SavePoint("save-1", "ctx-1", None, None, datetime.now(UTC), datetime.now(UTC))

        result = service.rollback_to(save_point)

        self.assertEqual(result.archived_fact_ids, ())
        self.assertEqual(result.restored_fact_ids, ())
        self.assertEqual(writer.plans, [])

    def test_archives_fact_created_after_cutoff(self) -> None:
        connection = FakeConnection()
        cutoff = datetime(2026, 1, 1, tzinfo=UTC)
        connection.candidates = [("cand-new", "ctx-1", datetime(2026, 1, 2, tzinfo=UTC))]
        connection.graph_ids = {"fact:cand-new": 101}
        writer = FakeGraphWriter()
        service = RollbackService(connection, writer)
        save_point = SavePoint("save-1", "ctx-1", None, None, cutoff, datetime.now(UTC))

        result = service.rollback_to(save_point)

        self.assertEqual(result.archived_fact_ids, ("cand-new",))
        self.assertEqual(len(writer.plans), 1)
        node = writer.plans[0].nodes[0]
        self.assertEqual(node.graph_id, 101)
        self.assertEqual(node.properties["archived"], True)

    def test_restores_fact_superseded_after_cutoff_with_original_valid_to(self) -> None:
        connection = FakeConnection()
        cutoff = datetime(2026, 1, 1, tzinfo=UTC)
        original_valid_to = datetime(2027, 6, 1, tzinfo=UTC)
        connection.candidates = [("cand-new", "ctx-1", datetime(2026, 1, 2, tzinfo=UTC))]
        connection.supersedes_logical_keys = ["supersedes:cand-new:cand-old"]
        connection.valid_to_by_id = {"cand-old": original_valid_to}
        connection.graph_ids = {"fact:cand-new": 101, "fact:cand-old": 100}
        writer = FakeGraphWriter()
        service = RollbackService(connection, writer)
        save_point = SavePoint("save-1", "ctx-1", None, None, cutoff, datetime.now(UTC))

        result = service.rollback_to(save_point)

        self.assertEqual(result.archived_fact_ids, ("cand-new",))
        self.assertEqual(result.restored_fact_ids, ("cand-old",))
        by_graph_id = {n.graph_id: n for n in writer.plans[0].nodes}
        restored_node = by_graph_id[100]
        self.assertEqual(restored_node.properties["is_current"], True)
        self.assertEqual(restored_node.properties["superseded_at"], 9999999999)
        self.assertEqual(restored_node.properties["valid_to"], int(original_valid_to.timestamp()))

    def test_deactivates_and_reactivates_postgres_side_state(self) -> None:
        connection = FakeConnection()
        cutoff = datetime(2026, 1, 1, tzinfo=UTC)
        connection.candidates = [("cand-new", "ctx-1", datetime(2026, 1, 2, tzinfo=UTC))]
        connection.supersedes_logical_keys = ["supersedes:cand-new:cand-old"]
        connection.valid_to_by_id = {"cand-old": None}
        connection.graph_ids = {"fact:cand-new": 101, "fact:cand-old": 100}
        writer = FakeGraphWriter()
        service = RollbackService(connection, writer)
        save_point = SavePoint("save-1", "ctx-1", None, None, cutoff, datetime.now(UTC))

        service.rollback_to(save_point)

        queries = [q for q, _ in connection.executed]
        self.assertTrue(any("DELETE FROM conversation_buffer" in q for q in queries))
        self.assertTrue(any("UPDATE memory_embeddings SET is_active = false" in q for q in queries))
        self.assertTrue(any("UPDATE memory_embeddings SET is_active = true" in q for q in queries))
        self.assertTrue(any("UPDATE fact_search_index SET is_active = false" in q for q in queries))
        self.assertTrue(any("UPDATE fact_search_index SET is_active = true" in q for q in queries))


if __name__ == "__main__":
    unittest.main()
