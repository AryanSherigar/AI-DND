"""Pydantic models for scenario mood-music endpoints."""

import uuid
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class MoodSlot(str, Enum):
    """The 6 canonical mood slots a scenario's music can be customized for."""

    PEACEFUL = "peaceful"
    MYSTERY = "mystery"
    TENSION = "tension"
    COMBAT = "combat"
    MELANCHOLY = "melancholy"
    TRIUMPH = "triumph"


class MusicSource(str, Enum):
    """Where a mood slot's track came from."""

    UPLOAD = "upload"
    GENERATED = "generated"
    DEFAULT = "default"


class ScenarioMusicResponse(BaseModel):
    """A single mood slot's current track configuration."""

    model_config = ConfigDict(from_attributes=True)

    scenario_music_id: uuid.UUID
    scenario_id: uuid.UUID
    mood: MoodSlot
    source: MusicSource
    track_url: str | None = None
    generation_prompt: str | None = None
    key: str | None = None
    bpm: int | None = None
    duration_seconds: float | None = None
    created_at: datetime
    updated_at: datetime


class ScenarioMusicListResponse(BaseModel):
    """All 6 mood slots for a scenario; unfilled slots are synthesized as
    source='default' with no persisted row."""

    items: list[ScenarioMusicResponse] = Field(default_factory=list)


class MusicGenerationRequest(BaseModel):
    """Creator's request to generate a track for one mood slot via Lyria."""

    mood: MoodSlot
    prompt: str = Field(..., min_length=1, max_length=500)


class MusicGenerationJobResponse(BaseModel):
    """Status/result of a submitted Lyria generation job."""

    model_config = ConfigDict(from_attributes=True)

    job_id: uuid.UUID
    scenario_id: uuid.UUID
    mood: MoodSlot
    status: Literal["pending", "running", "succeeded", "failed"]
    preview_url: str | None = None
    key: str | None = None
    bpm: int | None = None
    duration_seconds: float | None = None
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime


class QuotaStatusResponse(BaseModel):
    """Current generation-quota usage for a scenario and its creator."""

    scenario_generations_used: int
    scenario_generations_limit: int
    creator_generations_used_today: int
    creator_generations_limit_per_day: int


class DefaultMusicTracksResponse(BaseModel):
    """The 6 canonical built-in default track URLs, keyed by mood."""

    tracks: dict[MoodSlot, str]
