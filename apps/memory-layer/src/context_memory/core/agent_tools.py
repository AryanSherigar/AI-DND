"""§11 fix: the first real runtime wiring of the Phase 9 tool harness
(`core/tools.py`'s `ToolRegistry`, `core/tool_executor.py`'s
`GuardedToolExecutor`, `core/tool_loop.py`'s `run_tool_loop`). Those three
had registry/hook/loop tests but no production code ever constructed or
called them -- library primitives, not an active capability. `MemoryEngine.
agent_turn` (engine.py) is the caller; this module is only the tool
definitions and the one authorization hook they need.

Every tool here is closed over one playthrough's `context_id` -- never an
LLM-controllable argument. An agent turn is always scoped to one
playthrough (`MemoryEngine.agent_turn(context_id, ...)`, itself set by
whatever authenticated caller reached that method, not by the model); a
tool schema that let the model pass an arbitrary `context_id` would hand a
prompt-injected end user a cross-playthrough read/write primitive for
free. `rollback_to_save_point`'s `save_id` argument is the one exception
(a save point is looked up, not addressed directly by context_id) --
`build_rollback_authorization_hook` is the real boundary for that one.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from context_memory.core.tool_executor import HookDecision, HookResult
from context_memory.core.tools import Tool, ToolAnnotations, ToolRegistry

DEFAULT_MEMORY_AGENT_SYSTEM_PROMPT = (
    "You are a memory assistant for one tabletop-RPG playthrough. Use "
    "search_memory to answer questions from what's actually been recorded "
    "-- never invent a fact search_memory didn't return. Use "
    "create_save_point before a risky or irreversible story event, and "
    "rollback_to_save_point only when explicitly asked to undo something. "
    "Answer in plain text once you have what you need; do not call a tool "
    "you don't need."
)


def build_memory_agent_tools(engine: Any, context_id: str) -> ToolRegistry:
    """Registers `search_memory`/`create_save_point`/`rollback_to_save_point`
    against one `MemoryEngine` instance, scoped to `context_id`."""
    registry = ToolRegistry()

    def _search_memory(args: dict[str, Any]) -> dict[str, Any]:
        answer = engine.search_memories(
            context_id, args["query"], datetime.now(timezone.utc)
        )
        return {"answer": answer}

    registry.register(
        Tool(
            name="search_memory",
            description="Search this playthrough's memory for facts relevant to a natural-language query.",
            input_schema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "What to search for."}
                },
                "required": ["query"],
            },
            handler=_search_memory,
            annotations=ToolAnnotations(
                read_only_hint=True,
                destructive_hint=False,
                idempotent_hint=True,
                open_world_hint=False,
            ),
        )
    )

    def _create_save_point(args: dict[str, Any]) -> dict[str, Any]:
        save_point = engine.create_save_point(context_id, label=args.get("label"))
        return {
            "save_id": save_point.save_id,
            "created_at": save_point.created_at.isoformat(),
        }

    registry.register(
        Tool(
            name="create_save_point",
            description=(
                "Create a rollback point for this playthrough's memory, before a risky or irreversible story event."
            ),
            input_schema={
                "type": "object",
                "properties": {
                    "label": {
                        "type": "string",
                        "description": "Optional human-readable label.",
                    }
                },
                "required": [],
            },
            handler=_create_save_point,
            annotations=ToolAnnotations(
                read_only_hint=False,
                destructive_hint=False,
                idempotent_hint=False,
                open_world_hint=False,
            ),
        )
    )

    def _rollback_to_save_point(args: dict[str, Any]) -> dict[str, Any]:
        result = engine.rollback_to(args["save_id"])
        return {
            "save_id": result.save_id,
            "archived_fact_ids": list(result.archived_fact_ids),
            "restored_fact_ids": list(result.restored_fact_ids),
        }

    registry.register(
        Tool(
            name="rollback_to_save_point",
            description="Roll this playthrough's memory back to a previously created save point, undoing everything since.",
            input_schema={
                "type": "object",
                "properties": {
                    "save_id": {
                        "type": "string",
                        "description": "A save_id from create_save_point.",
                    }
                },
                "required": ["save_id"],
            },
            handler=_rollback_to_save_point,
            annotations=ToolAnnotations(
                read_only_hint=False,
                destructive_hint=True,
                idempotent_hint=False,
                open_world_hint=False,
            ),
        )
    )
    return registry


def build_rollback_authorization_hook(engine: Any, context_id: str):
    """§11 fix: the real authorization boundary a bare `rollback_to_save_point`
    tool call doesn't have on its own. `MemoryEngine.rollback_to(save_id)`
    resolves `save_id`'s own `context_id` internally and rolls back
    WHATEVER playthrough that save point belongs to -- regardless of which
    playthrough this agent turn is actually scoped to. Without this hook, a
    prompt-injected end user could roll back a DIFFERENT playthrough's
    memory just by getting the model to call this tool with a `save_id` it
    was never meant to have. Every other tool here takes no
    context_id-shaped argument at all (closed over `context_id` instead),
    so this is the one place such a check is even meaningful."""

    def hook(tool: Tool, args: dict[str, Any]) -> HookResult:
        if tool.name != "rollback_to_save_point":
            return HookResult(HookDecision.ALLOW)
        save_id = args.get("save_id")
        save_point = engine._save_point_store.get(save_id) if save_id else None
        if save_point is None:
            return HookResult(HookDecision.DENY, f"unknown save_id: {save_id!r}")
        if save_point.context_id != context_id:
            return HookResult(
                HookDecision.DENY, "save point does not belong to this playthrough"
            )
        return HookResult(HookDecision.ALLOW)

    return hook
