"""Pydantic models for AI image generation endpoints."""

from pydantic import BaseModel, Field


class CoverImageGenerationRequest(BaseModel):
    """Input used to compose a scenario cover image prompt."""

    title: str = Field(..., max_length=255)
    genre_tags: list[str] = Field(default_factory=list)
    opening_scene: str | None = None
