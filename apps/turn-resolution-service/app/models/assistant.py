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


class AssistantEntitySummary(BaseModel):
    entity_id: str
    entity_type: str
    canonical_name: str
    description: str | None = None
    attributes_schema: dict[str, object] = Field(default_factory=dict)


class AssistantFactSummary(BaseModel):
    fact_id: str
    subject_entity_id: str
    predicate: str
    object_entity_id: str | None = None
    object_literal: str | None = None


class AssistantConditionSummary(BaseModel):
    condition_id: str
    label: str


class AssistantInvariantSummary(BaseModel):
    invariant_id: str
    label: str


class AssistantEndConditionSummary(BaseModel):
    end_condition_id: str
    outcome_tag: str
    outcome_title: str


class AssistantMasterContext(BaseModel):
    title: str = ""
    logline: str = ""
    narrator_persona: str = ""
    opening_scene: str = ""
    state_schema: dict[str, object] = Field(default_factory=dict)
    entities: list[AssistantEntitySummary] = Field(default_factory=list)
    facts: list[AssistantFactSummary] = Field(default_factory=list)
    conditions: list[AssistantConditionSummary] = Field(default_factory=list)
    invariants: list[AssistantInvariantSummary] = Field(default_factory=list)
    end_conditions: list[AssistantEndConditionSummary] = Field(default_factory=list)
    active_tab: str = "entities"


class AssistantChatRequest(BaseModel):
    messages: list[AssistantChatMessage]
    mode: Literal["newbie", "master"] = "newbie"
    draft_context: AssistantDraftContext | None = None
    master_context: AssistantMasterContext | None = None
