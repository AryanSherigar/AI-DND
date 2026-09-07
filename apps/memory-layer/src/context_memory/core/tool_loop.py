"""Phase 9: turn-loop primitive. `run_tool_loop` is the smallest real
function-calling loop over `LLMClient.chat_with_tools` + a
`GuardedToolExecutor` -- call the model, execute whatever tools it asks
for, feed results back, repeat until it answers in plain text or
`max_iterations` is spent. Bounded on purpose: an ungoverned loop is
exactly the failure mode `PreToolUse` hooks and this cap both exist to
prevent.
"""

from __future__ import annotations

import json
from typing import Protocol

from context_memory.core.llm_client import LLMClient
from context_memory.core.logging import get_logger, timed_operation
from context_memory.core.tool_executor import GuardedToolExecutor
from context_memory.core.tools import ToolRegistry

logger = get_logger(__name__)


class ToolLoopExhaustedError(RuntimeError):
    """The model was still calling tools after `max_iterations` turns.
    Raised rather than returned as if it were a real answer -- a caller
    silently treating an exhausted loop as a normal response would hide a
    genuine runaway-tool-use failure."""


class _FunctionCall(Protocol):
    name: str
    arguments: str


class _ToolCall(Protocol):
    id: str
    function: _FunctionCall


def _execute_tool_call(executor: GuardedToolExecutor, tool_call: _ToolCall) -> str:
    try:
        args = json.loads(tool_call.function.arguments or "{}")
        result = executor.execute(tool_call.function.name, args)
        return json.dumps(result)
    except Exception as error:
        logger.warning(
            "Tool execution failed for %s: %s",
            tool_call.function.name,
            error,
            exc_info=True,
        )
        return json.dumps({"error": f"{type(error).__name__}: {error}"})


def _process_tool_calls(
    executor: GuardedToolExecutor, tool_calls: list[_ToolCall]
) -> list[dict[str, object]]:
    tool_messages: list[dict[str, object]] = []
    for tool_call in tool_calls:
        content = _execute_tool_call(executor, tool_call)
        tool_messages.append(
            {"role": "tool", "tool_call_id": tool_call.id, "content": content}
        )
    return tool_messages


def run_tool_loop(
    client: LLMClient,
    registry: ToolRegistry,
    executor: GuardedToolExecutor,
    system_prompt: str,
    user_prompt: str,
    *,
    max_iterations: int = 4,
    temperature: float = 0.0,
    max_tokens: int | None = None,
    timeout: float | None = None,
) -> str:
    messages: list[dict[str, object]] = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt},
    ]
    tools = registry.to_openai_tools()

    with timed_operation(
        logger, "tool_loop.run", {"max_iterations": max_iterations}
    ) as ctx:
        for iteration in range(max_iterations):
            response = client.chat_with_tools(
                messages,
                tools or None,
                temperature=temperature,
                max_tokens=max_tokens,
                timeout=timeout,
            )
            message = response.choices[0].message
            if not message.tool_calls:
                ctx["iterations"] = iteration + 1
                return message.content or ""

            messages.append(
                {
                    "role": "assistant",
                    "content": message.content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments,
                            },
                        }
                        for tc in message.tool_calls
                    ],
                }
            )
            messages.extend(_process_tool_calls(executor, message.tool_calls))

        raise ToolLoopExhaustedError(
            f"model still calling tools after {max_iterations} iterations"
        )
