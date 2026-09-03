"""Pydantic request and response schemas for Playthroughs."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PlaythroughCreate(BaseModel):
    """Payload to start a new playthrough of a published scenario."""

    scenario_id: uuid.UUID
    setup_values: dict[str, object] = Field(default_factory=dict)


class ParticipantSummary(BaseModel):
    """Lightweight participant info for frontend turn-order derivation."""

    model_config = ConfigDict(from_attributes=True)

    participant_id: uuid.UUID
    user_id: uuid.UUID
    role: str
    turn_order_position: int


class PlaythroughResponse(BaseModel):
    """Response model for a created or fetched playthrough."""

    model_config = ConfigDict(from_attributes=True)

    playthrough_id: uuid.UUID
    scenario_id: uuid.UUID
    scenario_title: str
    created_by: uuid.UUID
    state: dict[str, object]
    checkpoint: str | None = None
    turn_count: int
    status: str
    scenario_version: int
    scenario_snapshot: dict[str, object]
    created_at: datetime
    updated_at: datetime
    # The requesting user's own participant_id — needed to submit turns
    # (POST /v1/turn requires it) and absent from the RFC's original schema.
    participant_id: uuid.UUID
    participants: list[ParticipantSummary] = Field(default_factory=list)
