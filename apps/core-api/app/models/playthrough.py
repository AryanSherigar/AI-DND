"""Pydantic request and response schemas for Playthroughs."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class PlaythroughCreate(BaseModel):
    """Payload to start a new playthrough of a published scenario."""

    scenario_id: uuid.UUID
    setup_values: dict[str, str] = Field(default_factory=dict)


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
