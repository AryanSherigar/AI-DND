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

from context_memory.core.llm_client import LLMClient
from context_memory.core.logging import get_logger, timed_operation
from context_memory.core.tool_executor import GuardedToolExecutor, ToolDeniedError, ToolNotFoundError
from context_memory.core.tools import ToolRegistry

logger = get_logger(__name__)


class ToolLoopExhaustedError(RuntimeError):
    """The model was still calling tools after `max_iterations` turns.
    Raised rather than returned as if it were a real answer -- a caller
    silently treating an exhausted loop as a normal response would hide a
    genuine runaway-tool-use failure."""


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

    with timed_operation(logger, "tool_loop.run", {"max_iterations": max_iterations}) as ctx:
        for iteration in range(max_iterations):
            response = client.chat_with_tools(
                messages, tools or None, temperature=temperature, max_tokens=max_tokens, timeout=timeout,
            )
            message = response.choices[0].message
            if not message.tool_calls:
                ctx["iterations"] = iteration + 1
                return message.content or ""

            messages.append({
                "role": "assistant", "content": message.content,
                "tool_calls": [
                    {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                    for tc in message.tool_calls
                ],
            })
            for tool_call in message.tool_calls:
                try:
                    args = json.loads(tool_call.function.arguments or "{}")
                    result = executor.execute(tool_call.function.name, args)
                    content = json.dumps(result)
                except (ToolNotFoundError, ToolDeniedError, json.JSONDecodeError) as error:
                    # Fed back to the model as the tool's own result, not
                    # raised -- a real agent loop routes a bad call back to
                    # the model to retry or explain, the same way a human
                    # tool-user would see "permission denied" and adjust,
                    # rather than crashing the whole turn.
                    content = json.dumps({"error": str(error)})
                messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": content})

        raise ToolLoopExhaustedError(f"model still calling tools after {max_iterations} iterations")
