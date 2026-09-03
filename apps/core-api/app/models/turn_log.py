"""Pydantic response schemas for TurnLog scrollback."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TurnLogResponse(BaseModel):
    """A single recorded turn: the player's action and the AI's narration."""

    model_config = ConfigDict(from_attributes=True)

    turn_id: uuid.UUID
    playthrough_id: uuid.UUID
    turn_number: int
    participant_id: uuid.UUID | None
    action_text: str
    narration_text: str | None
    created_at: datetime


class TurnLogListResponse(BaseModel):
    """A paginated page of a playthrough's turn history."""

    items: list[TurnLogResponse]
    total_count: int
