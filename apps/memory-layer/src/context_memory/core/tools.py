"""Phase 9: tool registry. `ToolAnnotations` mirrors MCP's own tool
annotation schema (readOnlyHint/destructiveHint/idempotentHint/
openWorldHint, https://modelcontextprotocol.io) rather than inventing a
mem1-specific vocabulary -- same reasoning as reusing the real `gen_ai.*`
attributes in Phase 7 instead of hand-rolling names. `ToolRegistry` is a
deep module: register a `Tool`, get one call-loop-ready rendering
(`to_openai_tools`) back for free.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ToolAnnotations:
    """Hints, not guarantees -- a client (or a `PreToolUse` hook) may still
    choose to confirm a `destructive_hint=True` call, exactly as MCP
    specifies these are advisory. Defaults match MCP's own: unknown tools
    are assumed destructive and non-idempotent until declared otherwise."""

    read_only_hint: bool = False
    destructive_hint: bool = True
    idempotent_hint: bool = False
    open_world_hint: bool = True


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[dict[str, Any]], dict[str, Any]]
    annotations: ToolAnnotations = field(default_factory=ToolAnnotations)


class ToolRegistry:
    """One process-lifetime table of `Tool`s. No plugin/backend abstraction
    -- there is exactly one kind of registry, register/get/list is the
    whole interface."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}

    def register(self, tool: Tool) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> Tool | None:
        return self._tools.get(name)

    def list(self) -> list[Tool]:
        return list(self._tools.values())

    def to_openai_tools(self) -> list[dict[str, Any]]:
        """Renders every registered tool into the `tools=[...]` shape the
        OpenAI-compatible chat-completions function-calling API expects --
        the one translation `run_tool_loop` needs, kept here rather than
        duplicated at every call site."""
        return [
            {
                "type": "function",
                "function": {"name": tool.name, "description": tool.description, "parameters": tool.input_schema},
            }
            for tool in self._tools.values()
        ]
