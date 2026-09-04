"""Pydantic request and response schemas for master-mode Entities."""

import uuid

from pydantic import BaseModel, ConfigDict, Field

ENTITY_TYPES = ("character", "location", "item", "faction", "organization")

# Accepts any lowercase slug (built-in or a scenario's custom type key), since
# custom types are validated against ScenarioEntityType rows at the service
# layer, not by a static pattern here.
_ENTITY_TYPE_SLUG_PATTERN = "^[a-z][a-z0-9_]{0,29}$"


class AttributeFieldSchema(BaseModel):
    """One typed instance-attribute field on an entity (e.g. health, loyalty)."""

    type: str = Field(..., pattern="^(string|number|boolean|enum)$")
    initial: object = None
    min: float | None = None
    max: float | None = None
    label: str | None = None


class EntityCreate(BaseModel):
    """Payload to create a new entity within a master-mode scenario."""

    entity_type: str = Field(..., pattern=_ENTITY_TYPE_SLUG_PATTERN)
    canonical_name: str = Field(..., max_length=255)
    aliases: list[str] = Field(default_factory=list)
    description: str | None = None
    obtainable: bool | None = None
    attributes_schema: dict[str, AttributeFieldSchema] = Field(default_factory=dict)
    narrator_instruction: str | None = None


class EntityUpdate(BaseModel):
    """Payload to update an existing entity, including its type. Changing
    entity_type may drop attributes that don't fit the new type's template —
    EntityService.preview_type_change lets a client warn before committing."""

    entity_type: str | None = Field(default=None, pattern=_ENTITY_TYPE_SLUG_PATTERN)
    canonical_name: str | None = Field(default=None, max_length=255)
    aliases: list[str] | None = None
    description: str | None = None
    obtainable: bool | None = None
    attributes_schema: dict[str, AttributeFieldSchema] | None = None
    narrator_instruction: str | None = None


class EntityResponse(BaseModel):
    """Response model for a single entity."""

    model_config = ConfigDict(from_attributes=True)

    entity_id: uuid.UUID
    scenario_id: uuid.UUID
    entity_type: str
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    description: str | None = None
    obtainable: bool | None = None
    attributes_schema: dict[str, object] = Field(default_factory=dict)
    narrator_instruction: str | None = None
    fact_count: int = 0


class EntityListResponse(BaseModel):
    """Response model for listing a scenario's entities."""

    items: list[EntityResponse]


class EntityTypeChangePreviewRequest(BaseModel):
    """Payload naming the prospective new type to preview a change against."""

    new_entity_type: str = Field(..., pattern=_ENTITY_TYPE_SLUG_PATTERN)


class EntityTypeChangePreviewResponse(BaseModel):
    """Preview of how an entity's attributes would compare against a
    prospective new type's template, before the type change is committed."""

    dropped_fields: list[str] = Field(default_factory=list)
    retained_fields: list[str] = Field(default_factory=list)
    added_fields: list[str] = Field(default_factory=list)
