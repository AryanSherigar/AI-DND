"""Pydantic v2 schemas for the Studio AI Assistant."""

from typing import Literal

from pydantic import BaseModel, Field


class AssistantChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AssistantStoryCard(BaseModel):
    id: str | None = None
    type: str = "Character"
    name: str = ""
    content: str = ""


class AssistantDraftContext(BaseModel):
    title: str = ""
    logline: str = ""
    genre_tags: list[str] = Field(default_factory=list)
    complexity_tier: str = "newbie"
    player_count_support: str = "solo"
    estimated_playtime: str = ""
    world_lore: str = ""
    opening_prompt: str = ""
    main_conflict: str = ""
    single_lore_prompt: str = ""
    story_cards: list[AssistantStoryCard] = Field(default_factory=list)
    ai_instructions: str = ""
    narrative_style: str = ""
    active_section: str = "meta"


class AssistantChatRequest(BaseModel):
    messages: list[AssistantChatMessage]
    draft_context: AssistantDraftContext | None = None
