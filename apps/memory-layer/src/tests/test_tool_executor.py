from __future__ import annotations

import unittest
from contextlib import nullcontext

from context_memory.core.journal import StepJournal
from context_memory.core.tool_executor import (
    GuardedToolExecutor,
    HookDecision,
    HookResult,
    ToolDeniedError,
    ToolNotFoundError,
)
from context_memory.core.tools import Tool, ToolAnnotations, ToolRegistry


def _roll_dice(args: dict) -> dict:
    return {"result": 4, "sides": args.get("sides", 6)}


def _failing_tool(args: dict) -> dict:
    raise RuntimeError("tool blew up")


class FakeCursor:
    def __init__(self, rows: list[tuple]) -> None:
        self.rows = rows

    def execute(self, query: str, params: tuple = ()) -> None:
        if "ON CONFLICT" in query:
            step_type, idempotency_key = params[6], params[8]
            if any(r[6] == step_type and r[8] == idempotency_key for r in self.rows):
                return
            self.rows.append(params)

    def fetchone(self):
        return None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None


class FakeConnection:
    def __init__(self) -> None:
        self.rows: list[tuple] = []

    def cursor(self) -> FakeCursor:
        return FakeCursor(self.rows)

    def transaction(self):
        return nullcontext()


def _registry_with(*tools: Tool) -> ToolRegistry:
    registry = ToolRegistry()
    for tool in tools:
        registry.register(tool)
    return registry


class GuardedToolExecutorTests(unittest.TestCase):
    def test_executes_and_returns_the_handler_result(self) -> None:
        registry = _registry_with(Tool(name="roll_dice", description="", input_schema={}, handler=_roll_dice))
        executor = GuardedToolExecutor(registry)

        result = executor.execute("roll_dice", {"sides": 20})

        self.assertEqual(result, {"result": 4, "sides": 20})

    def test_unknown_tool_raises(self) -> None:
        executor = GuardedToolExecutor(ToolRegistry())
        with self.assertRaises(ToolNotFoundError):
            executor.execute("nope", {})

    def test_pre_hook_deny_blocks_execution(self) -> None:
        calls = []
        registry = _registry_with(Tool(name="roll_dice", description="", input_schema={}, handler=lambda a: calls.append(a) or {}))
        deny = lambda tool, args: HookResult(HookDecision.DENY, reason="not allowed mid-combat")
        executor = GuardedToolExecutor(registry, pre_hooks=(deny,))

        with self.assertRaisesRegex(ToolDeniedError, "not allowed mid-combat"):
            executor.execute("roll_dice", {})
        self.assertEqual(calls, [])  # handler never ran

    def test_pre_hook_allow_lets_execution_proceed(self) -> None:
        registry = _registry_with(Tool(name="roll_dice", description="", input_schema={}, handler=_roll_dice))
        allow = lambda tool, args: HookResult(HookDecision.ALLOW)
        executor = GuardedToolExecutor(registry, pre_hooks=(allow,))

        self.assertEqual(executor.execute("roll_dice", {})["result"], 4)

    def test_post_hook_observes_tool_args_and_result(self) -> None:
        observed = []
        registry = _registry_with(Tool(name="roll_dice", description="", input_schema={}, handler=_roll_dice))
        executor = GuardedToolExecutor(registry, post_hooks=(lambda tool, args, result: observed.append((tool.name, args, result)),))

        executor.execute("roll_dice", {"sides": 8})

        self.assertEqual(observed, [("roll_dice", {"sides": 8}, {"result": 4, "sides": 8})])

    def test_handler_exception_propagates_and_is_journaled_as_error(self) -> None:
        connection = FakeConnection()
        journal = StepJournal(connection)
        registry = _registry_with(Tool(name="explode", description="", input_schema={}, handler=_failing_tool))
        executor = GuardedToolExecutor(registry, journal=journal)

        with self.assertRaises(RuntimeError):
            executor.execute("explode", {})

        self.assertEqual(len(connection.rows), 1)
        self.assertEqual(connection.rows[0][12], "error")  # outcome column

    def test_non_idempotent_tool_gets_a_fresh_key_every_call(self) -> None:
        connection = FakeConnection()
        journal = StepJournal(connection)
        registry = _registry_with(Tool(
            name="roll_dice", description="", input_schema={}, handler=_roll_dice,
            annotations=ToolAnnotations(idempotent_hint=False),
        ))
        executor = GuardedToolExecutor(registry, journal=journal)

        executor.execute("roll_dice", {"sides": 6})
        executor.execute("roll_dice", {"sides": 6})

        self.assertEqual(len(connection.rows), 2)  # two real rolls, not deduped

    def test_idempotent_tool_dedups_identical_calls(self) -> None:
        connection = FakeConnection()
        journal = StepJournal(connection)
        registry = _registry_with(Tool(
            name="get_inventory", description="", input_schema={}, handler=lambda a: {"items": []},
            annotations=ToolAnnotations(read_only_hint=True, destructive_hint=False, idempotent_hint=True),
        ))
        executor = GuardedToolExecutor(registry, journal=journal)

        executor.execute("get_inventory", {"player": "p1"})
        executor.execute("get_inventory", {"player": "p1"})

        self.assertEqual(len(connection.rows), 1)  # same read, deduped


if __name__ == "__main__":
    unittest.main()
