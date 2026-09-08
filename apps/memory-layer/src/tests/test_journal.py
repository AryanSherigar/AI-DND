from __future__ import annotations

import threading
import unittest
from contextlib import nullcontext

from context_memory.core.journal import (
    JournalContext,
    JournaledLLMClient,
    StepJournal,
    correlation_scope,
    current_correlation,
    hash_request,
)
from pydantic import BaseModel


class _Answer(BaseModel):
    value: str


class FakeCursor:
    def __init__(self, rows: list[tuple]) -> None:
        self.rows = rows
        self.executed: list[tuple[str, tuple]] = []

    def execute(self, query: str, params: tuple | None = None) -> None:
        self.executed.append((query, params or ()))
        if "ON CONFLICT" in query:
            # §10 fix: journal_steps conflicts on step_id (params[0], a
            # fresh uuid4 every call) now, not (step_type, idempotency_key)
            # -- append-only, matching the real ON CONFLICT (step_id) DO
            # NOTHING StepJournal.record now issues.
            step_id = params[0]
            if any(r[0] == step_id for r in self.rows):
                return
            self.rows.append(params)

    def fetchone(self):
        return None

    def __enter__(self) -> FakeCursor:
        return self

    def __exit__(self, *exc) -> None:
        return None


class FakeConnection:
    def __init__(self) -> None:
        self.rows: list[tuple] = []
        self._cursor = FakeCursor(self.rows)

    def cursor(self) -> FakeCursor:
        return self._cursor

    def transaction(self):
        return nullcontext()


class RaisingConnection:
    def cursor(self):
        raise RuntimeError("connection unavailable")

    def transaction(self):
        return nullcontext()


class FakePool:
    """`StepJournal` now acquires a connection per call via `pool.connection()`
    -- this just yields the same fake connection every time, so existing
    tests can keep asserting against one shared connection's recorded state.
    Mirrors `test_rollback.py`'s `FakePool`, added for the same reason
    (`SavePointStore`/`RollbackService` moving to per-call pool acquisition)."""

    def __init__(self, connection: object) -> None:
        self._connection = connection

    def connection(self):
        return nullcontext(self._connection)


class FakeLLMClient:
    """Minimal `LLMClient`-shaped fake; no provider, no database, no graph."""

    model = "fake-model"

    def __init__(
        self, structured_result: BaseModel | None = None, text_result: str = "an answer"
    ) -> None:
        self._structured_result = structured_result
        self._text_result = text_result
        self.structured_calls: list[tuple] = []
        self.text_calls: list[tuple] = []

    def structured_completion(
        self, system_prompt, user_prompt, response_schema, **kwargs
    ):
        self.structured_calls.append((system_prompt, user_prompt, response_schema))
        return self._structured_result

    def text_completion(self, system_prompt, user_prompt, temperature=0.0, **kwargs):
        self.text_calls.append((system_prompt, user_prompt))
        return self._text_result


class HashRequestTests(unittest.TestCase):
    def test_deterministic_for_same_inputs(self) -> None:
        self.assertEqual(
            hash_request("reader", "m1", "sys", "user"),
            hash_request("reader", "m1", "sys", "user"),
        )

    def test_differs_on_any_part(self) -> None:
        base = hash_request("reader", "m1", "sys", "user")
        self.assertNotEqual(base, hash_request("rerank", "m1", "sys", "user"))
        self.assertNotEqual(base, hash_request("reader", "m2", "sys", "user"))
        self.assertNotEqual(base, hash_request("reader", "m1", "sys2", "user"))

    def test_join_boundary_is_not_forgeable_by_content(self) -> None:
        # Without a real separator, ("ab", "c") and ("a", "bc") would collide.
        self.assertNotEqual(hash_request("ab", "c"), hash_request("a", "bc"))


class CorrelationScopeTests(unittest.TestCase):
    def test_mints_one_id_per_scope(self) -> None:
        self.assertIsNone(current_correlation())
        with correlation_scope() as correlation_id:
            self.assertIsNotNone(correlation_id)
            self.assertEqual(current_correlation(), correlation_id)
        self.assertIsNone(current_correlation())

    def test_nested_scope_reuses_ambient_id(self) -> None:
        with correlation_scope() as outer_id:
            with correlation_scope(JournalContext(context_id="ctx-2")) as inner_id:
                self.assertEqual(inner_id, outer_id)
            # still inside the outer scope after the inner one exits
            self.assertEqual(current_correlation(), outer_id)


class StepJournalRecordTests(unittest.TestCase):
    def test_record_inserts_one_row(self) -> None:
        connection = FakeConnection()
        journal = StepJournal(FakePool(connection))
        step_id = journal.record(
            step_type="llm.text_completion",
            call_role="reader",
            idempotency_key="key-1",
            request_payload={"user_prompt": "hi"},
            response_payload={"text": "hello"},
            outcome="ok",
            elapsed_ms=12.5,
            model_name="m1",
        )
        self.assertIsNotNone(step_id)
        self.assertEqual(len(connection.rows), 1)

    def test_journal_is_append_only_repeated_idempotency_key_does_not_dedupe(
        self,
    ) -> None:
        """§10 fix: was `self.assertEqual(len(connection.rows), 1)` -- three
        calls sharing an idempotency_key (a real scenario: the same prompt
        legitimately retried, or two different requests happening to
        fingerprint identically) used to silently collapse into one row,
        with no trace the other two calls ever happened. Each call gets its
        own step_id and its own row now."""
        connection = FakeConnection()
        journal = StepJournal(FakePool(connection))
        step_ids = [
            journal.record(
                step_type="llm.text_completion",
                call_role="reader",
                idempotency_key="same-key",
                request_payload={},
                response_payload=None,
                outcome="ok",
                elapsed_ms=1.0,
            )
            for _ in range(3)
        ]
        self.assertEqual(len(connection.rows), 3)
        self.assertEqual(len(set(step_ids)), 3)  # every call got its own event identity

    def test_different_step_types_do_not_collide_on_same_key(self) -> None:
        connection = FakeConnection()
        journal = StepJournal(FakePool(connection))
        journal.record(
            step_type="llm.text_completion",
            call_role="reader",
            idempotency_key="same-key",
            request_payload={},
            response_payload=None,
            outcome="ok",
            elapsed_ms=1.0,
        )
        journal.record(
            step_type="llm.structured_completion[X]",
            call_role="reader",
            idempotency_key="same-key",
            request_payload={},
            response_payload=None,
            outcome="ok",
            elapsed_ms=1.0,
        )
        self.assertEqual(len(connection.rows), 2)

    def test_never_raises_on_connection_failure(self) -> None:
        journal = StepJournal(FakePool(RaisingConnection()))
        step_id = journal.record(
            step_type="llm.text_completion",
            call_role="reader",
            idempotency_key="key-1",
            request_payload={},
            response_payload=None,
            outcome="ok",
            elapsed_ms=1.0,
        )
        self.assertIsNone(step_id)

    def test_context_threaded_from_correlation_scope(self) -> None:
        connection = FakeConnection()
        journal = StepJournal(FakePool(connection))
        with correlation_scope(JournalContext(context_id="ctx-1", session_id="sess-1")):
            journal.record(
                step_type="llm.text_completion",
                call_role="reader",
                idempotency_key="key-1",
                request_payload={},
                response_payload=None,
                outcome="ok",
                elapsed_ms=1.0,
            )
        row = connection.rows[0]
        # (step_id, correlation_id, context_id, session_id, turn_index, scenario_id, ...)
        self.assertEqual(row[2], "ctx-1")
        self.assertEqual(row[3], "sess-1")

    def test_scenario_id_threaded_from_correlation_scope(self) -> None:
        connection = FakeConnection()
        journal = StepJournal(FakePool(connection))
        with correlation_scope(
            JournalContext(context_id="ctx-1", scenario_id="scenario-forest-of-echoes")
        ):
            journal.record(
                step_type="llm.text_completion",
                call_role="reader",
                idempotency_key="key-1",
                request_payload={},
                response_payload=None,
                outcome="ok",
                elapsed_ms=1.0,
            )
        row = connection.rows[0]
        self.assertEqual(row[5], "scenario-forest-of-echoes")


class SharedRowsPool:
    """Simulates the real `ConnectionPool`: each `.connection()` acquisition
    hands out a *distinct* `FakeConnection` (so concurrent `record()` calls
    don't contend on one shared connection object, the way the pre-fix
    single-connection design did), but every connection's cursor writes into
    one shared `rows` list -- standing in for the one underlying Postgres
    table every pooled connection ultimately reaches."""

    def __init__(self) -> None:
        self.rows: list[tuple] = []

    def connection(self):
        conn = FakeConnection()
        conn.rows = self.rows
        conn._cursor = FakeCursor(self.rows)
        return nullcontext(conn)


class StepJournalConcurrencyTests(unittest.TestCase):
    """Regression test for a real bug: Phase 0 runs the temporal resolver and
    query rewriter concurrently (their own `ThreadPoolExecutor`, since Track
    A), and the old design -- one `StepJournal` holding a single shared
    connection for its whole lifetime -- silently lost most rows when
    accessed from multiple threads without synchronization (a live
    30-instance run: 30 expected per role, ~7 landed, zero raised exceptions).

    `StepJournal` now acquires a fresh connection per `record()` call from
    the pool instead, so concurrent calls no longer share any connection to
    race on -- correctness comes from Postgres safely handling concurrent
    inserts from separate connections, not from an app-level lock. This test
    asserts the property that still matters: no rows lost under concurrency,
    not that calls were serialized (they no longer are, and shouldn't be)."""

    def test_concurrent_record_calls_all_persist_without_loss(self) -> None:
        pool = SharedRowsPool()
        journal = StepJournal(pool)

        def record_one(i: int) -> None:
            journal.record(
                step_type="llm.text_completion",
                call_role="reader",
                idempotency_key=f"key-{i}",
                request_payload={},
                response_payload=None,
                outcome="ok",
                elapsed_ms=1.0,
            )

        threads = [threading.Thread(target=record_one, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(pool.rows), 20)


class JournaledLLMClientTests(unittest.TestCase):
    def test_wraps_structured_completion_and_records_one_row(self) -> None:
        connection = FakeConnection()
        journal = StepJournal(FakePool(connection))
        inner = FakeLLMClient(structured_result=_Answer(value="42"))
        client = JournaledLLMClient(inner, journal, call_role="reader")

        result = client.structured_completion("sys", "user", _Answer)

        self.assertEqual(result.value, "42")
        self.assertEqual(len(inner.structured_calls), 1)
        self.assertEqual(len(connection.rows), 1)

    def test_wraps_text_completion_and_records_one_row(self) -> None:
        connection = FakeConnection()
        journal = StepJournal(FakePool(connection))
        inner = FakeLLMClient(text_result="hello there")
        client = JournaledLLMClient(inner, journal, call_role="rerank")

        result = client.text_completion("sys", "user")

        self.assertEqual(result, "hello there")
        self.assertEqual(len(connection.rows), 1)

    def test_records_error_outcome_and_reraises(self) -> None:
        connection = FakeConnection()
        journal = StepJournal(FakePool(connection))

        class FailingClient:
            model = "fake-model"

            def text_completion(self, *args, **kwargs):
                raise RuntimeError("provider down")

        client = JournaledLLMClient(FailingClient(), journal, call_role="reader")
        with self.assertRaises(RuntimeError):
            client.text_completion("sys", "user")

        self.assertEqual(len(connection.rows), 1)
        row = connection.rows[0]
        outcome_index = 12  # step_id, correlation_id, context_id, session_id, turn_index, scenario_id,
        # step_type, call_role, idempotency_key, model_name, request_payload, response_payload, outcome
        self.assertEqual(row[outcome_index], "error")

    def test_identical_calls_produce_the_same_idempotency_key_but_both_are_recorded(
        self,
    ) -> None:
        """§10 fix: was `self.assertEqual(len(connection.rows), 1)` -- two
        real, distinct calls (both actually happened) used to leave only
        one trace. The fingerprint (`idempotency_key`) is still
        deterministic -- same inputs, same key -- but it no longer decides
        whether a call gets recorded at all."""
        connection = FakeConnection()
        journal = StepJournal(FakePool(connection))
        inner = FakeLLMClient(text_result="same answer")
        client = JournaledLLMClient(inner, journal, call_role="reader")

        client.text_completion("sys", "user")
        client.text_completion("sys", "user")

        self.assertEqual(len(connection.rows), 2)
        idempotency_index = 8
        self.assertEqual(
            connection.rows[0][idempotency_index], connection.rows[1][idempotency_index]
        )


if __name__ == "__main__":
    unittest.main()
