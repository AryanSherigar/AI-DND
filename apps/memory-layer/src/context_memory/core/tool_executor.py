"""Phase 9: `PreToolUse`/`PostToolUse` guardrail hooks (named after Claude
Code's own hook convention, the harness plan's explicit reference point)
plus the audit trail every tool call gets for free by reusing Phase 5's
`StepJournal` -- a tool execution is journaled exactly like an LLM call,
same table, same tracing (`StepJournal._emit_span` already handles any
`step_type` generically), no second audit mechanism.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from hashlib import sha256
from typing import Any

from context_memory.core.journal import StepJournal
from context_memory.core.tools import Tool, ToolRegistry


class HookDecision(Enum):
    ALLOW = "allow"
    DENY = "deny"


@dataclass(frozen=True)
class HookResult:
    decision: HookDecision
    reason: str | None = None


PreToolUseHook = Callable[[Tool, dict[str, Any]], HookResult]
PostToolUseHook = Callable[[Tool, dict[str, Any], dict[str, Any]], None]


class ToolNotFoundError(RuntimeError):
    """No tool registered under this name."""


class ToolDeniedError(RuntimeError):
    """A `PreToolUse` hook denied this call. Carries the denying hook's
    `reason`, if any -- surfaced to the caller, not swallowed."""


def _tool_idempotency_key(tool: Tool, args: dict[str, Any]) -> str:
    """`idempotent_hint=True` tools fingerprint on (name, args) content, same
    as an LLM call's request content -- a genuine retry with the same
    arguments is recognizable as the same logical step from its
    idempotency_key alone. Everything else (the MCP-aligned default) gets a
    fresh key per call: two dice rolls with identical arguments are two
    different events, not the same one repeated. `journal_steps` is
    append-only (§10 fix) regardless -- every call gets its own row either
    way; the key's only job is being a meaningful fingerprint to query by,
    not a uniqueness constraint."""
    if tool.annotations.idempotent_hint:
        payload = json.dumps(args, sort_keys=True, default=str)
        return sha256(f"{tool.name}\x1f{payload}".encode()).hexdigest()
    return uuid.uuid4().hex


class GuardedToolExecutor:
    def __init__(
        self,
        registry: ToolRegistry,
        journal: StepJournal | None = None,
        pre_hooks: tuple[PreToolUseHook, ...] = (),
        post_hooks: tuple[PostToolUseHook, ...] = (),
    ) -> None:
        self._registry = registry
        self._journal = journal
        self._pre_hooks = pre_hooks
        self._post_hooks = post_hooks

    def execute(self, name: str, args: dict[str, Any]) -> dict[str, Any]:
        tool = self._registry.get(name)
        if tool is None:
            raise ToolNotFoundError(f"no tool registered under {name!r}")

        for hook in self._pre_hooks:
            result = hook(tool, args)
            if result.decision is HookDecision.DENY:
                raise ToolDeniedError(
                    result.reason or f"a PreToolUse hook denied {name!r}"
                )

        step_type = f"tool.execute[{name}]"
        idempotency_key = _tool_idempotency_key(tool, args)
        start = time.monotonic()
        try:
            result = tool.handler(args)
        except Exception as error:
            self._record(
                step_type, name, idempotency_key, args, None, "error", start, str(error)
            )
            raise
        self._record(step_type, name, idempotency_key, args, result, "ok", start, None)

        for hook in self._post_hooks:
            hook(tool, args, result)
        return result

    def _record(
        self,
        step_type: str,
        call_role: str,
        idempotency_key: str,
        args: dict[str, Any],
        result: dict[str, Any] | None,
        outcome: str,
        start: float,
        error_message: str | None,
    ) -> None:
        if self._journal is None:
            return
        self._journal.record(
            step_type=step_type,
            call_role=call_role,
            idempotency_key=idempotency_key,
            request_payload={"args": args},
            response_payload=result,
            outcome=outcome,  # type: ignore[arg-type]
            elapsed_ms=(time.monotonic() - start) * 1000,
            error_message=error_message,
        )
