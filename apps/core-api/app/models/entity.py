"""Pydantic request and response schemas for master-mode Entities."""

import uuid

from pydantic import BaseModel, ConfigDict, Field

ENTITY_TYPES = ("character", "location", "item", "faction", "organization")
_ENTITY_TYPE_PATTERN = "^(" + "|".join(ENTITY_TYPES) + ")$"


class AttributeFieldSchema(BaseModel):
    """One typed instance-attribute field on an entity (e.g. health, loyalty)."""

    type: str = Field(..., pattern="^(string|number|boolean|enum)$")
    initial: object = None
    min: float | None = None
    max: float | None = None
    label: str | None = None


class EntityCreate(BaseModel):
    """Payload to create a new entity within a master-mode scenario."""

    entity_type: str = Field(..., pattern=_ENTITY_TYPE_PATTERN)
    canonical_name: str = Field(..., max_length=255)
    aliases: list[str] = Field(default_factory=list)
    description: str | None = None
    obtainable: bool | None = None
    attributes_schema: dict[str, AttributeFieldSchema] = Field(default_factory=dict)
    narrator_instruction: str | None = None


class EntityUpdate(BaseModel):
    """Payload to update an existing entity. entity_type is immutable."""

    canonical_name: str | None = Field(default=None, max_length=255)
    aliases: list[str] | None = None
    description: str | None = None
    obtainable: bool | None = None
    attributes_schema: dict[str, AttributeFieldSchema] | None = None
    narrator_instruction: str | None = None
    # entity_type is intentionally omitted: changing it after creation would
    # silently invalidate every fact/condition that assumed the old type.


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


class EntityListResponse(BaseModel):
    """Response model for listing a scenario's entities."""

    items: list[EntityResponse]
