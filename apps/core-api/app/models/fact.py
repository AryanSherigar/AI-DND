"""Pydantic request and response schemas for master-mode Facts."""

import uuid

from pydantic import BaseModel, ConfigDict, Field


class FactCreate(BaseModel):
    """Payload to create a fact connecting a subject entity to an object.

    Exactly one of object_entity_id/object_literal must be set — enforced at
    the service layer (needs no DB lookup for the shape check itself, but is
    kept alongside the entity-reference checks that do) and, as a last-line
    guarantee, by the ck_facts_object_exclusive DB constraint.
    """

    subject_entity_id: uuid.UUID
    predicate: str = Field(..., max_length=100)
    object_entity_id: uuid.UUID | None = None
    object_literal: str | None = None
    valid_from: str | None = Field(default=None, max_length=100)
    when_active: dict[str, object] | None = None
    hidden: bool = False
    superseded_fact_id: uuid.UUID | None = None


class FactUpdate(BaseModel):
    """Payload to update an existing fact."""

    predicate: str | None = Field(default=None, max_length=100)
    object_entity_id: uuid.UUID | None = None
    object_literal: str | None = None
    valid_from: str | None = Field(default=None, max_length=100)
    when_active: dict[str, object] | None = None
    hidden: bool | None = None
    superseded_fact_id: uuid.UUID | None = None


class FactResponse(BaseModel):
    """Response model for a single fact."""

    model_config = ConfigDict(from_attributes=True)

    fact_id: uuid.UUID
    scenario_id: uuid.UUID
    subject_entity_id: uuid.UUID
    predicate: str
    object_entity_id: uuid.UUID | None = None
    object_literal: str | None = None
    valid_from: str | None = None
    when_active: dict[str, object] | None = None
    hidden: bool = False
    superseded_fact_id: uuid.UUID | None = None


class FactListResponse(BaseModel):
    """Response model for listing a scenario's facts."""

    items: list[FactResponse]
