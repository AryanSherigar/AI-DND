"""Pydantic shapes for master-mode Gemini tool calls and validation results."""

from pydantic import BaseModel, Field


class ProposedMutation(BaseModel):
    """A single proposed state change, translated from a Gemini function call
    by tool_handler.py — not yet validated against schema or invariants."""

    tool_name: str
    op: str  # "set" | "increment" | "add_item" | "roll" | "unknown"
    path: str | None = None
    value: object = None
    delta: float | None = None
    sides: int | None = None
    modifier: int | None = None


class ValidationResult(BaseModel):
    """Outcome of state_validator.validate_mutation()/validate_applied_change()."""

    is_valid: bool
    updated_state: dict[str, object] | None = None
    error_message: str | None = None


class ToolCallLogEntry(BaseModel):
    """One tool call's record, persisted onto TurnLog.tool_calls."""

    tool_name: str
    arguments: dict[str, object] = Field(default_factory=dict)
    result: dict[str, object] = Field(default_factory=dict)
    is_valid: bool


class MasterModeTurnResult(BaseModel):
    """Mutable sink ai_orchestrator.generate_narration() populates while
    streaming; read by pipeline.py/state_writer.py after the narration
    generator is exhausted (a generator's body has fully run by the time an
    `async for` over it completes, so this is a safe hand-off pattern)."""

    final_state: dict[str, object] = Field(default_factory=dict)
    mutated_paths: list[str] = Field(default_factory=list)
    tool_calls: list[ToolCallLogEntry] = Field(default_factory=list)
