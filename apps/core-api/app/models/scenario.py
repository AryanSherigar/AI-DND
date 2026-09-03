"""Pydantic request and response schemas for Scenarios."""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class ScenarioCreate(BaseModel):
    """Payload to create a new draft scenario."""

    title: str = Field(..., max_length=255)
    mode: str = Field(..., pattern="^(newbie|master)$")
    complexity_tier: str = Field(..., pattern="^(newbie|intermediate|master)$")
    logline: str | None = Field(default=None, max_length=150)
    player_count_support: str = Field(
        default="solo", pattern="^(solo|multiplayer|both)$"
    )
    estimated_playtime: str | None = Field(default=None, max_length=50)
    cover_image_url: str | None = Field(default=None, max_length=1024)
    content_tag: str | None = Field(default=None, max_length=100)
    genre_tags: list[str] = Field(default_factory=list)
    narrator_persona: str | None = None
    world_data: dict[str, object] = Field(default_factory=dict)
    setup_schema: list[object] = Field(default_factory=list)
    state_schema: dict[str, object] = Field(default_factory=dict)
    end_conditions: list[object] = Field(default_factory=list)
    checkpoints: list[object] = Field(default_factory=list)
    rules: dict[str, object] = Field(default_factory=dict)


class ScenarioUpdate(BaseModel):
    """Payload to update scenario fields. Mode is immutable and omitted."""

    title: str | None = Field(default=None, max_length=255)
    status: str | None = Field(default=None, pattern="^(draft|archived)$")
    logline: str | None = Field(default=None, max_length=150)
    complexity_tier: str | None = Field(
        default=None, pattern="^(newbie|intermediate|master)$"
    )
    player_count_support: str | None = Field(
        default=None, pattern="^(solo|multiplayer|both)$"
    )
    estimated_playtime: str | None = Field(default=None, max_length=50)
    cover_image_url: str | None = Field(default=None, max_length=1024)
    content_tag: str | None = Field(default=None, max_length=100)
    genre_tags: list[str] | None = None
    narrator_persona: str | None = None
    world_data: dict[str, object] | None = None
    setup_schema: list[object] | None = None
    state_schema: dict[str, object] | None = None
    end_conditions: list[object] | None = None
    checkpoints: list[object] | None = None
    rules: dict[str, object] | None = None


class ScenarioResponse(BaseModel):
    """Detailed response model for a single scenario."""

    model_config = ConfigDict(from_attributes=True)

    scenario_id: uuid.UUID
    creator_id: uuid.UUID
    creator_display_name: str | None = None
    is_bookmarked: bool = False
    can_review: bool = False
    title: str
    logline: str | None = None
    mode: str
    status: str
    genre_tags: list[str] = Field(default_factory=list)
    complexity_tier: str
    player_count_support: str
    estimated_playtime: str | None = None
    cover_image_url: str | None = None
    content_tag: str | None = None
    publish_error: str | None = None
    published_at: datetime | None = None
    play_count: int = 0
    rating_avg: Decimal = Field(default=Decimal("0.00"))
    narrator_persona: str | None = None
    world_data: dict[str, object] = Field(default_factory=dict)
    setup_schema: list[object] = Field(default_factory=list)
    state_schema: dict[str, object] = Field(default_factory=dict)
    end_conditions: list[object] = Field(default_factory=list)
    checkpoints: list[object] = Field(default_factory=list)
    rules: dict[str, object] = Field(default_factory=dict)
    current_version: int = 1
    created_at: datetime
    updated_at: datetime


class ScenarioSummaryResponse(BaseModel):
    """Summary model used for discovery feed and scenario listing cards."""

    model_config = ConfigDict(from_attributes=True)

    scenario_id: uuid.UUID
    creator_id: uuid.UUID
    title: str
    logline: str | None = None
    mode: str
    status: str
    genre_tags: list[str] = Field(default_factory=list)
    complexity_tier: str
    player_count_support: str
    estimated_playtime: str | None = None
    cover_image_url: str | None = None
    content_tag: str | None = None
    play_count: int = 0
    rating_avg: Decimal = Field(default=Decimal("0.00"))
    created_at: datetime
    updated_at: datetime


class ScenarioListResponse(BaseModel):
    """Paginated response for scenario listing."""

    items: list[ScenarioSummaryResponse]
    next_cursor: str | None = None
    total_count: int
