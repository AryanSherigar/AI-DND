from __future__ import annotations

import time
import unittest
from datetime import datetime, timezone
from pathlib import Path

from context_memory.core.replay import ReplayedError, ReplayingLLMClient, ReplayMissError, load_journal_fixture
from context_memory.retrieval.models import DateRange, QueryRewriterOutput, ScoredFact
from context_memory.retrieval.query_rewriter import QueryRewriter
from context_memory.retrieval.reader import AnswerReader
from context_memory.retrieval.reranker import Reranker
from context_memory.retrieval.sibling_expander import SiblingExpander
from context_memory.retrieval.temporal_resolver import TemporalQueryResolver

FIXTURE_PATH = Path(__file__).resolve().parents[2] / "benchmarks" / "fixtures" / "reader_sample_turn.json"
READER_RERANK_FIXTURE_PATH = Path(__file__).resolve().parents[2] / "benchmarks" / "fixtures" / "reader_rerank_sample.json"

# The exact question/date the fixture was recorded against (LongMemEval
# instance 0e4e4c46-r30b-bfbbc70f, sample30.json) -- prompts are deterministic
# functions of these, so replaying with the same inputs reproduces the same
# idempotency keys the real run recorded.
QUESTION = "What is my current highest score in Ticket to Ride?"
QUESTION_DATE = datetime.strptime("2023/06/10 (Sat) 16:46", "%Y/%m/%d (%a) %H:%M").replace(tzinfo=timezone.utc)


class LoadJournalFixtureTests(unittest.TestCase):
    def test_loads_the_committed_fixture(self) -> None:
        fixture = load_journal_fixture(FIXTURE_PATH)
        self.assertGreaterEqual(len(fixture), 3)
        step_types = {step_type for step_type, _ in fixture}
        self.assertIn("llm.structured_completion[DateRange]", step_types)
        self.assertIn("llm.structured_completion[QueryRewriterOutput]", step_types)


class ReplayingLLMClientTests(unittest.TestCase):
    """No LLM, no network, no Postgres, no HydraDB -- real adapter code
    (`TemporalQueryResolver`, `QueryRewriter`) driven against a committed,
    already-recorded fixture. This is the "layer-isolated" no-LLM test the
    harness plan calls for: it gates every commit in milliseconds."""

    def setUp(self) -> None:
        self.fixture = load_journal_fixture(FIXTURE_PATH)

    def test_temporal_resolver_replays_the_recorded_date_range(self) -> None:
        client = ReplayingLLMClient(self.fixture, call_role="temporal_resolver", model="qwen.qwen3-32b")
        resolver = TemporalQueryResolver(client)

        start = time.perf_counter()
        result = resolver.resolve(QUESTION, QUESTION_DATE)
        elapsed_ms = (time.perf_counter() - start) * 1000

        self.assertIsInstance(result, DateRange)
        self.assertIsNone(result.valid_from)
        self.assertIsNone(result.valid_to)
        self.assertLess(elapsed_ms, 50, "replay should be sub-network-latency, not just fast-ish")

    def test_query_rewriter_replays_the_recorded_decomposition(self) -> None:
        client = ReplayingLLMClient(self.fixture, call_role="query_rewriter", model="openai.gpt-oss-20b")
        rewriter = QueryRewriter(client)

        result = rewriter.rewrite(QUESTION)

        self.assertIsInstance(result, QueryRewriterOutput)
        self.assertIn("Ticket to Ride", result.synonyms)
        self.assertEqual(result.decomposed_queries, [QUESTION])

    def test_wrong_model_is_a_replay_miss_not_a_silent_fallback(self) -> None:
        # Same role/question, wrong recorded model -> different idempotency
        # key -> no match. Asserted at the ReplayingLLMClient boundary
        # itself, not through QueryRewriter -- that adapter deliberately
        # catches and degrades on ANY structured_completion failure
        # (network error, malformed JSON, a replay miss, ...), which is its
        # own correct, pre-existing resilience behavior, not something this
        # test should paper over by picking an input that never exercises it.
        client = ReplayingLLMClient(self.fixture, call_role="query_rewriter", model="a-model-never-recorded")

        with self.assertRaises(ReplayMissError):
            client.structured_completion(
                self._rewriter_system_prompt(), QUESTION, QueryRewriterOutput,
            )

    def test_wrong_question_is_a_replay_miss(self) -> None:
        client = ReplayingLLMClient(self.fixture, call_role="query_rewriter", model="openai.gpt-oss-20b")

        with self.assertRaises(ReplayMissError):
            client.structured_completion(
                self._rewriter_system_prompt(), "a completely different question never asked in this fixture",
                QueryRewriterOutput,
            )

    @staticmethod
    def _rewriter_system_prompt() -> str:
        from context_memory.core.config import Config

        return Config().query_rewriter_system_prompt

    def test_text_completion_miss_raises(self) -> None:
        client = ReplayingLLMClient(self.fixture, call_role="reader", model="openai.gpt-oss-20b")
        with self.assertRaises(ReplayMissError):
            client.text_completion("some system prompt", "some question")


# A second, purpose-built fixture: `reader_sample_turn.json` doesn't retain
# request text (by design -- replay computes its own idempotency key from
# the caller's actual request, see `core/replay.py`), so replaying the
# reranker/reader precisely requires knowing the exact facts they were
# originally run against. Captured with 3 hand-authored facts small enough
# to fully control and reproduce here, rather than depending on whatever a
# live LongMemEval ingestion happened to seed.
FACTS = [
    ScoredFact(fact_id="fact-1", text="The user's cat is named Whiskers.", observed_at=1700000000, speaker="user"),
    ScoredFact(fact_id="fact-2", text="The user's favorite color is teal.", observed_at=1700003600, speaker="user"),
    ScoredFact(fact_id="fact-3", text="The user works as a marine biologist.", observed_at=1700007200, speaker="user"),
]
READER_RERANK_QUESTION = "What is the user's cat's name?"


class ReaderAndRerankerReplayTests(unittest.TestCase):
    """Same no-LLM/no-network guarantee as `ReplayingLLMClientTests`, for
    the two adapters `reader_sample_turn.json` can't precisely replay."""

    def setUp(self) -> None:
        self.fixture = load_journal_fixture(READER_RERANK_FIXTURE_PATH)

    def test_reranker_replays_the_recorded_selection(self) -> None:
        client = ReplayingLLMClient(self.fixture, call_role="rerank", model="qwen.qwen3-32b")
        reranker = Reranker(client)

        # top_k=2 < len(FACTS) -- otherwise Reranker.rerank short-circuits
        # before ever calling the LLM (len(ranked) <= top_k), the same trap
        # that produced an empty capture on the first attempt at this fixture.
        ranked = reranker.rerank(READER_RERANK_QUESTION, list(FACTS), top_k=2)

        self.assertEqual(ranked[0].fact_id, "fact-1")  # the model's real recorded selection

    def test_reader_replays_the_recorded_answer(self) -> None:
        client = ReplayingLLMClient(self.fixture, call_role="reader", model="openai.gpt-oss-20b")
        reader = AnswerReader(client, SiblingExpander(None, None))

        answer = reader.read(READER_RERANK_QUESTION, list(FACTS), context_id=None, question_date=None)

        self.assertEqual(answer, "Whiskers.")


class OrderedRepeatedCallReplayTests(unittest.TestCase):
    """§10 fix: a fixture recording the SAME (step_type, idempotency_key)
    call twice, in order, must replay both occurrences in that order --
    not the first response looping forever, and not silently losing the
    second recording."""

    def _fixture_with_two_recordings(self, first_text: str, second_text: str) -> dict:
        from context_memory.core.journal import hash_request
        from context_memory.core.replay import RecordedStep

        # Real fingerprint -- must match exactly what
        # ReplayingLLMClient.text_completion("sys", "user") computes
        # internally, or the lookup below is a guaranteed miss.
        idempotency_key = hash_request("reader", "m", "sys", "user")
        key = ("llm.text_completion", idempotency_key)
        return {
            key: [
                RecordedStep(
                    step_type=key[0], call_role="reader", idempotency_key=idempotency_key, model_name="m",
                    response_payload={"text": first_text}, outcome="ok",
                ),
                RecordedStep(
                    step_type=key[0], call_role="reader", idempotency_key=idempotency_key, model_name="m",
                    response_payload={"text": second_text}, outcome="ok",
                ),
            ]
        }

    def test_second_identical_call_gets_the_second_recording(self) -> None:
        fixture = self._fixture_with_two_recordings("first answer", "second answer")
        client = ReplayingLLMClient(fixture, call_role="reader", model="m")

        first = client.text_completion("sys", "user")
        second = client.text_completion("sys", "user")

        self.assertEqual(first, "first answer")
        self.assertEqual(second, "second answer")

    def test_a_third_call_past_every_recorded_occurrence_is_a_replay_miss(self) -> None:
        fixture = self._fixture_with_two_recordings("first answer", "second answer")
        client = ReplayingLLMClient(fixture, call_role="reader", model="m")
        client.text_completion("sys", "user")
        client.text_completion("sys", "user")
        with self.assertRaises(ReplayMissError):
            client.text_completion("sys", "user")


class RecordedFailureReplayTests(unittest.TestCase):
    """§10 fix: `export_journal_fixture` used to drop every non-"ok" step,
    and `ReplayingLLMClient` had no way to tell "never recorded" apart from
    "recorded as a failure" even if it had one. Both fixed together."""

    def test_a_recorded_error_step_replays_as_replayed_error_not_a_miss(self) -> None:
        from context_memory.core.journal import hash_request
        from context_memory.core.replay import RecordedStep

        idempotency_key = hash_request("reader", "m", "sys", "user")
        key = ("llm.text_completion", idempotency_key)
        fixture = {
            key: [
                RecordedStep(
                    step_type=key[0], call_role="reader", idempotency_key=idempotency_key, model_name="m",
                    response_payload=None, outcome="error", error_message="provider timeout after 30s",
                ),
            ]
        }
        client = ReplayingLLMClient(fixture, call_role="reader", model="m")
        with self.assertRaises(ReplayedError) as ctx:
            client.text_completion("sys", "user")
        self.assertIn("provider timeout after 30s", str(ctx.exception))

    def test_export_no_longer_filters_out_error_outcomes(self) -> None:
        """Exercises the SQL shape directly against a fake cursor, since
        this repo's test suite doesn't require a live Postgres."""
        class FakeCursor:
            def __init__(self, rows):
                self._rows = rows
                self.last_query = None

            def execute(self, query, params=None):
                self.last_query = query

            def fetchall(self):
                return self._rows

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return None

        class FakeConnection:
            def __init__(self, rows):
                self._cursor = FakeCursor(rows)

            def cursor(self):
                return self._cursor

        from context_memory.core.replay import export_journal_fixture
        import tempfile, os

        rows = [
            ("llm.text_completion", "reader", "k1", "m", {"text": "ok answer"}, "ok", None),
            ("llm.text_completion", "reader", "k2", "m", None, "error", "boom"),
        ]
        conn = FakeConnection(rows)
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "fixture.json")
            count = export_journal_fixture(conn, correlation_id="corr-1", path=path)
            self.assertEqual(count, 2)
            self.assertNotIn("outcome = 'ok'", conn._cursor.last_query)


class ToolCallReplayTests(unittest.TestCase):
    """§10 fix: `ReplayingLLMClient` had no `chat_with_tools` at all --
    anything driving a tool-calling loop against a fixture hit
    `AttributeError` instead of a diagnosable replay miss/hit."""

    def test_replays_a_recorded_tool_call(self) -> None:
        import json

        from context_memory.core.journal import hash_request
        from context_memory.core.replay import RecordedStep

        messages = [{"role": "user", "content": "roll a d20"}]
        tools = [{"type": "function", "function": {"name": "roll_die"}}]
        idempotency_key = hash_request(
            "gm", "m", json.dumps(messages, sort_keys=True), json.dumps(tools, sort_keys=True),
        )
        fixture = {
            ("llm.chat_with_tools", idempotency_key): [
                RecordedStep(
                    step_type="llm.chat_with_tools", call_role="gm", idempotency_key=idempotency_key, model_name="m",
                    response_payload={
                        "content": None,
                        "tool_calls": [{"id": "call-1", "name": "roll_die", "arguments": '{"sides": 20}'}],
                    },
                    outcome="ok",
                ),
            ]
        }
        client = ReplayingLLMClient(fixture, call_role="gm", model="m")

        response = client.chat_with_tools(messages, tools)

        message = response.choices[0].message
        self.assertIsNone(message.content)
        self.assertEqual(len(message.tool_calls), 1)
        self.assertEqual(message.tool_calls[0].id, "call-1")
        self.assertEqual(message.tool_calls[0].function.name, "roll_die")
        self.assertEqual(message.tool_calls[0].function.arguments, '{"sides": 20}')

    def test_unrecorded_tool_call_is_a_replay_miss(self) -> None:
        client = ReplayingLLMClient({}, call_role="gm", model="m")
        with self.assertRaises(ReplayMissError):
            client.chat_with_tools([{"role": "user", "content": "hi"}])


if __name__ == "__main__":
    unittest.main()
