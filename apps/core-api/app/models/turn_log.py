"""Pydantic response schemas for TurnLog scrollback."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ToolCallLogEntry(BaseModel):
    """One master-mode tool call's record, read back from TurnLog.tool_calls.

    Mirrors turn-resolution-service's app/models/tool_call.py::ToolCallLogEntry
    shape. Core API and TRS are separate deployables with no shared package,
    so this is an intentional mirror of the JSONB contract each service reads
    and writes independently, not in-codebase schema duplication.
    """

    tool_name: str
    arguments: dict[str, object] = Field(default_factory=dict)
    result: dict[str, object] = Field(default_factory=dict)
    is_valid: bool


class TurnLogResponse(BaseModel):
    """A single recorded turn: the player's action and the AI's narration."""

    model_config = ConfigDict(from_attributes=True)

    turn_id: uuid.UUID
    playthrough_id: uuid.UUID
    turn_number: int
    participant_id: uuid.UUID | None
    action_text: str
    narration_text: str | None
    tool_calls: list[ToolCallLogEntry] = Field(default_factory=list)
    created_at: datetime


class TurnLogListResponse(BaseModel):
    """A paginated page of a playthrough's turn history."""

    items: list[TurnLogResponse]
    total_count: int
