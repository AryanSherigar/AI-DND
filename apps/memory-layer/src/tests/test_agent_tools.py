"""§11 fix: the first production wiring of the Phase 9 tool harness
(ToolRegistry/GuardedToolExecutor/run_tool_loop) -- core/agent_tools.py's
tool definitions and authorization hook, called from
MemoryEngine.agent_turn.
"""

from __future__ import annotations

import json
import unittest
from dataclasses import dataclass, field
from datetime import datetime, timezone

from context_memory.core.agent_tools import build_memory_agent_tools, build_rollback_authorization_hook
from context_memory.core.tool_executor import GuardedToolExecutor, HookDecision
from context_memory.core.tool_loop import run_tool_loop
from context_memory.ingestion.rollback import RollbackResult, SavePoint


class FakeSavePointStore:
    def __init__(self) -> None:
        self._points: dict[str, SavePoint] = {}

    def seed(self, save_id: str, context_id: str, label: str | None = None) -> None:
        now = datetime.now(timezone.utc)
        self._points[save_id] = SavePoint(save_id, context_id, None, label, now, now)

    def get(self, save_id: str):
        return self._points.get(save_id)


class FakeEngine:
    """Duck-typed to the slice of `MemoryEngine` `core/agent_tools.py`
    actually needs -- no Postgres/HydraDB required to test tool wiring."""

    def __init__(self) -> None:
        self._save_point_store = FakeSavePointStore()
        self.search_calls: list[tuple[str, str]] = []
        self.rollback_calls: list[str] = []

    def search_memories(self, context_id, query, question_date):
        self.search_calls.append((context_id, query))
        return f"answer about {query}"

    def create_save_point(self, context_id, session_id=None, label=None):
        save_id = f"save-{len(self._save_point_store._points) + 1}"
        self._save_point_store.seed(save_id, context_id, label)
        return self._save_point_store.get(save_id)

    def rollback_to(self, save_id):
        self.rollback_calls.append(save_id)
        return RollbackResult(save_id=save_id, archived_fact_ids=("fact-1",), restored_fact_ids=())


class BuildMemoryAgentToolsTests(unittest.TestCase):
    def test_registers_all_three_tools(self) -> None:
        engine = FakeEngine()
        registry = build_memory_agent_tools(engine, "context-1")
        names = {t.name for t in registry.list()}
        self.assertEqual(names, {"search_memory", "create_save_point", "rollback_to_save_point"})

    def test_search_memory_handler_is_closed_over_context_id_not_llm_controllable(self) -> None:
        """The tool's input_schema has no context_id property at all -- the
        model can only ever search the playthrough this agent turn was
        scoped to, never one it names itself."""
        engine = FakeEngine()
        registry = build_memory_agent_tools(engine, "context-1")
        tool = registry.get("search_memory")
        self.assertNotIn("context_id", tool.input_schema["properties"])

        result = tool.handler({"query": "who is the dragon?"})

        self.assertEqual(engine.search_calls, [("context-1", "who is the dragon?")])
        self.assertEqual(result, {"answer": "answer about who is the dragon?"})

    def test_create_save_point_handler_creates_against_the_bound_context(self) -> None:
        engine = FakeEngine()
        registry = build_memory_agent_tools(engine, "context-1")
        tool = registry.get("create_save_point")

        result = tool.handler({"label": "before the boss fight"})

        save_point = engine._save_point_store.get(result["save_id"])
        self.assertEqual(save_point.context_id, "context-1")
        self.assertEqual(save_point.label, "before the boss fight")

    def test_rollback_handler_delegates_to_engine(self) -> None:
        engine = FakeEngine()
        registry = build_memory_agent_tools(engine, "context-1")
        tool = registry.get("rollback_to_save_point")

        result = tool.handler({"save_id": "save-1"})

        self.assertEqual(engine.rollback_calls, ["save-1"])
        self.assertEqual(result["archived_fact_ids"], ["fact-1"])


class RollbackAuthorizationHookTests(unittest.TestCase):
    """§11 fix: the one real authorization boundary this module adds --
    `rollback_to_save_point`'s `save_id` is the only tool argument that can
    address a DIFFERENT playthrough's data than the one this agent turn is
    scoped to."""

    def test_allows_rollback_to_a_save_point_in_the_same_context(self) -> None:
        engine = FakeEngine()
        engine._save_point_store.seed("save-1", "context-1")
        hook = build_rollback_authorization_hook(engine, "context-1")
        registry = build_memory_agent_tools(engine, "context-1")

        result = hook(registry.get("rollback_to_save_point"), {"save_id": "save-1"})

        self.assertEqual(result.decision, HookDecision.ALLOW)

    def test_denies_rollback_to_a_save_point_in_a_different_context(self) -> None:
        engine = FakeEngine()
        engine._save_point_store.seed("save-1", "some-other-playthrough")
        hook = build_rollback_authorization_hook(engine, "context-1")
        registry = build_memory_agent_tools(engine, "context-1")

        result = hook(registry.get("rollback_to_save_point"), {"save_id": "save-1"})

        self.assertEqual(result.decision, HookDecision.DENY)

    def test_denies_an_unknown_save_id(self) -> None:
        engine = FakeEngine()
        hook = build_rollback_authorization_hook(engine, "context-1")
        registry = build_memory_agent_tools(engine, "context-1")

        result = hook(registry.get("rollback_to_save_point"), {"save_id": "does-not-exist"})

        self.assertEqual(result.decision, HookDecision.DENY)

    def test_never_blocks_other_tools(self) -> None:
        engine = FakeEngine()
        hook = build_rollback_authorization_hook(engine, "context-1")
        registry = build_memory_agent_tools(engine, "context-1")

        result = hook(registry.get("search_memory"), {"query": "anything"})

        self.assertEqual(result.decision, HookDecision.ALLOW)


# Reuses test_tool_loop.py's fake chat-completions shape.
@dataclass
class FakeFunctionCall:
    name: str
    arguments: str


@dataclass
class FakeToolCall:
    id: str
    function: FakeFunctionCall


@dataclass
class FakeMessage:
    content: str | None
    tool_calls: list[FakeToolCall] = field(default_factory=list)


@dataclass
class FakeChoice:
    message: FakeMessage


@dataclass
class FakeResponse:
    choices: list[FakeChoice]


class FakeToolCallingClient:
    model = "fake-model"

    def __init__(self, responses: list[FakeResponse]) -> None:
        self._responses = list(responses)

    def chat_with_tools(self, messages, tools=None, **kwargs):
        return self._responses.pop(0)


class EndToEndAgentToolLoopTests(unittest.TestCase):
    """Proves the denial actually reaches run_tool_loop's model-facing
    feedback path (fed back as a tool error, not silently allowed) end to
    end, not just at the hook's own return value."""

    def test_cross_context_rollback_is_denied_not_executed(self) -> None:
        engine = FakeEngine()
        engine._save_point_store.seed("save-from-another-playthrough", "someone-elses-context")
        registry = build_memory_agent_tools(engine, "context-1")
        executor = GuardedToolExecutor(
            registry, pre_hooks=(build_rollback_authorization_hook(engine, "context-1"),),
        )
        tool_call = FakeToolCall(
            "call-1", FakeFunctionCall("rollback_to_save_point", json.dumps({"save_id": "save-from-another-playthrough"}))
        )
        client = FakeToolCallingClient([
            FakeResponse([FakeChoice(FakeMessage(content=None, tool_calls=[tool_call]))]),
            FakeResponse([FakeChoice(FakeMessage(content="I can't roll back that save point."))]),
        ])

        result = run_tool_loop(client, registry, executor, "sys", "roll back to save-from-another-playthrough")

        self.assertEqual(result, "I can't roll back that save point.")
        self.assertEqual(engine.rollback_calls, [])  # never actually executed


class FakeRetrievalEngine:
    def __init__(self, answer: str) -> None:
        self._answer = answer
        self.calls: list[tuple[str, str]] = []

    def retrieve_and_answer(self, context_id, question, question_date, top_k=None):
        self.calls.append((context_id, question))
        return self._answer


class FakeOrchestrator:
    def run_batch(self, batch):
        raise AssertionError("agent_turn's search_memory tool must not ingest anything")


class MemoryEngineAgentTurnTests(unittest.TestCase):
    """§11 fix: `MemoryEngine.agent_turn` is the first real caller of
    `run_tool_loop`/`ToolRegistry`/`GuardedToolExecutor` -- this proves the
    engine wires them correctly, not just that the pieces work in
    isolation (covered above)."""

    def _engine(self, llm_client):
        from context_memory.engine import MemoryEngine

        return MemoryEngine(
            FakeOrchestrator(), FakeRetrievalEngine("Whiskers is the cat's name."), llm_client,
            pg_connection=object(), save_point_store=FakeSavePointStore(),
        )

    def test_agent_turn_answers_directly_when_the_model_calls_no_tool(self) -> None:
        client = FakeToolCallingClient([FakeResponse([FakeChoice(FakeMessage(content="Hi there!"))])])
        engine = self._engine(client)

        reply = engine.agent_turn("context-1", "hello")

        self.assertEqual(reply, "Hi there!")

    def test_agent_turn_routes_search_memory_through_the_real_search_memories_method(self) -> None:
        tool_call = FakeToolCall("call-1", FakeFunctionCall("search_memory", json.dumps({"query": "cat's name"})))
        client = FakeToolCallingClient([
            FakeResponse([FakeChoice(FakeMessage(content=None, tool_calls=[tool_call]))]),
            FakeResponse([FakeChoice(FakeMessage(content="Whiskers."))]),
        ])
        engine = self._engine(client)

        reply = engine.agent_turn("context-1", "what's the cat's name?")

        self.assertEqual(reply, "Whiskers.")
        self.assertEqual(engine._retrieval_engine.calls, [("context-1", "cat's name")])


if __name__ == "__main__":
    unittest.main()
