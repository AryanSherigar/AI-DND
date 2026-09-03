"""Pydantic schemas for Scenario Ratings, Reviews, and Public Playthroughs."""

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ScenarioReviewCreate(BaseModel):
    """Payload to submit a scenario review."""

    rating: int = Field(..., ge=1, le=5)
    comment: str | None = Field(default=None, max_length=1000)


class ScenarioReviewResponse(BaseModel):
    """Response schema for a scenario review."""

    model_config = ConfigDict(from_attributes=True)

    review_id: uuid.UUID
    scenario_id: uuid.UUID
    user_id: uuid.UUID
    user_display_name: str = "Adventurer"
    rating: int
    comment: str | None = None
    created_at: datetime


class ScenarioReviewListResponse(BaseModel):
    """Paginated list of reviews for a scenario."""

    items: list[ScenarioReviewResponse]
    total_count: int
    average_rating: float = 0.0


class PublicPlaythroughSummary(BaseModel):
    """Summary of a public active/completed playthrough for a scenario."""

    model_config = ConfigDict(from_attributes=True)

    playthrough_id: uuid.UUID
    player_name: str = "Unknown Hero"
    character_name: str | None = None
    turn_count: int
    status: str
    updated_at: datetime
