"""Pydantic request and response schemas for scenario-scoped custom entity types."""

import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.entity import AttributeFieldSchema

_TYPE_KEY_PATTERN = "^[a-z][a-z0-9_]{0,29}$"


class ScenarioEntityTypeCreate(BaseModel):
    """Payload to define a new custom entity type template for a scenario."""

    type_key: str = Field(..., pattern=_TYPE_KEY_PATTERN)
    display_label: str = Field(..., max_length=60)
    attributes_schema: dict[str, AttributeFieldSchema] = Field(default_factory=dict)


class ScenarioEntityTypeUpdate(BaseModel):
    """Payload to update an existing custom entity type template. type_key is
    immutable: entities already reference it by value."""

    display_label: str | None = Field(default=None, max_length=60)
    attributes_schema: dict[str, AttributeFieldSchema] | None = None


class ScenarioEntityTypeResponse(BaseModel):
    """Response model for a single custom entity type template."""

    model_config = ConfigDict(from_attributes=True)

    scenario_entity_type_id: uuid.UUID
    scenario_id: uuid.UUID
    type_key: str
    display_label: str
    attributes_schema: dict[str, object] = Field(default_factory=dict)


class ScenarioEntityTypeListResponse(BaseModel):
    """Response model for listing a scenario's custom entity type templates."""

    items: list[ScenarioEntityTypeResponse]
