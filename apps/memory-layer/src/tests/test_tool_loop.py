from __future__ import annotations

import json
import unittest
from dataclasses import dataclass, field

from context_memory.core.tool_executor import GuardedToolExecutor
from context_memory.core.tool_loop import ToolLoopExhaustedError, run_tool_loop
from context_memory.core.tools import Tool, ToolRegistry


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
    """`LLMClient`-shaped stand-in exposing only `chat_with_tools` -- no
    network, no SDK, scripted responses returned in order."""

    model = "fake-model"

    def __init__(self, responses: list[FakeResponse]) -> None:
        self._responses = list(responses)
        self.calls: list[list[dict]] = []

    def chat_with_tools(self, messages, tools=None, **kwargs):
        self.calls.append([dict(m) for m in messages])
        return self._responses.pop(0)


def _roll_dice(args: dict) -> dict:
    return {"result": 4, "sides": args.get("sides", 6)}


def _registry() -> ToolRegistry:
    registry = ToolRegistry()
    registry.register(
        Tool(
            name="roll_dice",
            description="Rolls a die.",
            input_schema={
                "type": "object",
                "properties": {"sides": {"type": "integer"}},
            },
            handler=_roll_dice,
        )
    )
    return registry


class RunToolLoopTests(unittest.TestCase):
    def test_returns_plain_text_when_no_tool_call_is_made(self) -> None:
        client = FakeToolCallingClient(
            [FakeResponse([FakeChoice(FakeMessage(content="Hello there."))])]
        )
        registry = _registry()
        executor = GuardedToolExecutor(registry)

        result = run_tool_loop(client, registry, executor, "sys", "hi")

        self.assertEqual(result, "Hello there.")
        self.assertEqual(len(client.calls), 1)

    def test_executes_a_requested_tool_and_feeds_the_result_back(self) -> None:
        tool_call = FakeToolCall(
            "call-1", FakeFunctionCall("roll_dice", json.dumps({"sides": 20}))
        )
        client = FakeToolCallingClient(
            [
                FakeResponse(
                    [FakeChoice(FakeMessage(content=None, tool_calls=[tool_call]))]
                ),
                FakeResponse([FakeChoice(FakeMessage(content="You rolled a 4."))]),
            ]
        )
        registry = _registry()
        executor = GuardedToolExecutor(registry)

        result = run_tool_loop(client, registry, executor, "sys", "roll a d20")

        self.assertEqual(result, "You rolled a 4.")
        self.assertEqual(len(client.calls), 2)
        # second call's message history includes the tool's real result
        second_call_messages = client.calls[1]
        tool_messages = [m for m in second_call_messages if m["role"] == "tool"]
        self.assertEqual(len(tool_messages), 1)
        self.assertEqual(
            json.loads(tool_messages[0]["content"]), {"result": 4, "sides": 20}
        )

    def test_unknown_tool_call_is_fed_back_as_an_error_not_raised(self) -> None:
        tool_call = FakeToolCall("call-1", FakeFunctionCall("nonexistent_tool", "{}"))
        client = FakeToolCallingClient(
            [
                FakeResponse(
                    [FakeChoice(FakeMessage(content=None, tool_calls=[tool_call]))]
                ),
                FakeResponse(
                    [FakeChoice(FakeMessage(content="Sorry, I can't do that."))]
                ),
            ]
        )
        registry = _registry()
        executor = GuardedToolExecutor(registry)

        result = run_tool_loop(client, registry, executor, "sys", "do the impossible")

        self.assertEqual(result, "Sorry, I can't do that.")
        tool_messages = [m for m in client.calls[1] if m["role"] == "tool"]
        self.assertEqual(len(tool_messages), 1)
        self.assertEqual(
            json.loads(tool_messages[0]["content"]),
            {"error": "ToolNotFoundError: no tool registered under 'nonexistent_tool'"},
        )

    def test_internal_handler_exception_is_fed_back_as_error_not_raised(self) -> None:
        def _failing_handler(args: dict) -> dict:
            raise RuntimeError("database connection lost")

        registry = ToolRegistry()
        registry.register(
            Tool(
                name="crash_tool",
                description="Fails always.",
                input_schema={},
                handler=_failing_handler,
            )
        )
        executor = GuardedToolExecutor(registry)

        tool_call = FakeToolCall("call-1", FakeFunctionCall("crash_tool", "{}"))
        client = FakeToolCallingClient(
            [
                FakeResponse(
                    [FakeChoice(FakeMessage(content=None, tool_calls=[tool_call]))]
                ),
                FakeResponse(
                    [FakeChoice(FakeMessage(content="The database had an issue."))]
                ),
            ]
        )

        result = run_tool_loop(client, registry, executor, "sys", "do failing action")

        self.assertEqual(result, "The database had an issue.")
        self.assertEqual(len(client.calls), 2)
        tool_messages = [m for m in client.calls[1] if m["role"] == "tool"]
        self.assertEqual(len(tool_messages), 1)
        self.assertEqual(
            json.loads(tool_messages[0]["content"]),
            {"error": "RuntimeError: database connection lost"},
        )

    def test_malformed_arguments_json_is_fed_back_as_error(self) -> None:
        registry = _registry()
        executor = GuardedToolExecutor(registry)

        tool_call = FakeToolCall(
            "call-1", FakeFunctionCall("roll_dice", "{invalid_json")
        )
        client = FakeToolCallingClient(
            [
                FakeResponse(
                    [FakeChoice(FakeMessage(content=None, tool_calls=[tool_call]))]
                ),
                FakeResponse(
                    [FakeChoice(FakeMessage(content="Invalid arguments format."))]
                ),
            ]
        )

        result = run_tool_loop(client, registry, executor, "sys", "roll with bad args")

        self.assertEqual(result, "Invalid arguments format.")
        self.assertEqual(len(client.calls), 2)
        tool_messages = [m for m in client.calls[1] if m["role"] == "tool"]
        self.assertEqual(len(tool_messages), 1)
        content = json.loads(tool_messages[0]["content"])
        self.assertTrue(content["error"].startswith("JSONDecodeError:"))

    def test_unserializable_tool_result_is_fed_back_as_error(self) -> None:
        def _bad_result_handler(args: dict) -> dict:
            return {"unserializable": object()}

        registry = ToolRegistry()
        registry.register(
            Tool(
                name="bad_result_tool",
                description="Returns bad type.",
                input_schema={},
                handler=_bad_result_handler,
            )
        )
        executor = GuardedToolExecutor(registry)

        tool_call = FakeToolCall("call-1", FakeFunctionCall("bad_result_tool", "{}"))
        client = FakeToolCallingClient(
            [
                FakeResponse(
                    [FakeChoice(FakeMessage(content=None, tool_calls=[tool_call]))]
                ),
                FakeResponse(
                    [
                        FakeChoice(
                            FakeMessage(content="Serialization error encountered.")
                        )
                    ]
                ),
            ]
        )

        result = run_tool_loop(client, registry, executor, "sys", "call bad tool")

        self.assertEqual(result, "Serialization error encountered.")
        self.assertEqual(len(client.calls), 2)
        tool_messages = [m for m in client.calls[1] if m["role"] == "tool"]
        self.assertEqual(len(tool_messages), 1)
        content = json.loads(tool_messages[0]["content"])
        self.assertTrue(content["error"].startswith("TypeError:"))

    def test_exhausting_max_iterations_raises_rather_than_returning_a_partial_answer(
        self,
    ) -> None:
        tool_call = FakeToolCall("call-1", FakeFunctionCall("roll_dice", "{}"))
        # Always asks for another tool call, never answers -- a runaway loop.
        client = FakeToolCallingClient(
            [
                FakeResponse(
                    [FakeChoice(FakeMessage(content=None, tool_calls=[tool_call]))]
                )
                for _ in range(3)
            ]
        )
        registry = _registry()
        executor = GuardedToolExecutor(registry)

        with self.assertRaises(ToolLoopExhaustedError):
            run_tool_loop(
                client, registry, executor, "sys", "keep rolling", max_iterations=3
            )


if __name__ == "__main__":
    unittest.main()
