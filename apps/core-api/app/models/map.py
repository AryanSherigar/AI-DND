"""Pydantic request and response schemas for master-mode Maps."""

import uuid

from pydantic import BaseModel, ConfigDict, Field


class MapCreate(BaseModel):
    """Payload to create a new map within a master-mode scenario."""

    name: str = Field(..., max_length=255)
    display_order: int = 0


class MapUpdate(BaseModel):
    """Payload to update a map's fields."""

    name: str | None = Field(default=None, max_length=255)
    image_url: str | None = Field(default=None, max_length=1024)
    display_order: int | None = None


class MapResponse(BaseModel):
    """Response model for a single map."""

    model_config = ConfigDict(from_attributes=True)

    map_id: uuid.UUID
    scenario_id: uuid.UUID
    name: str
    image_url: str | None = None
    display_order: int = 0


class MapListResponse(BaseModel):
    """Response model for listing a scenario's maps."""

    items: list[MapResponse]


class MapPinCreate(BaseModel):
    """Payload to place a location entity's pin on a map."""

    entity_id: uuid.UUID
    x: float = Field(..., ge=0.0, le=1.0)
    y: float = Field(..., ge=0.0, le=1.0)
    is_start_location: bool = False


class MapPinUpdate(BaseModel):
    """Payload to update a pin's position or start-location flag.

    entity_id is immutable after creation — matches EntityUpdate's
    immutable-entity_type precedent; repin by deleting and recreating.
    """

    x: float | None = Field(default=None, ge=0.0, le=1.0)
    y: float | None = Field(default=None, ge=0.0, le=1.0)
    is_start_location: bool | None = None


class MapPinResponse(BaseModel):
    """Response model for a single map pin."""

    model_config = ConfigDict(from_attributes=True)

    pin_id: uuid.UUID
    map_id: uuid.UUID
    scenario_id: uuid.UUID
    entity_id: uuid.UUID
    x: float
    y: float
    is_start_location: bool = False


class MapPinListResponse(BaseModel):
    """Response model for listing a map's pins."""

    items: list[MapPinResponse]


class MapConnectionCreate(BaseModel):
    """Payload to connect two location entities in the scenario-wide graph.

    Accepted in either order — the service normalizes the pair into
    sorted-UUID order before persisting.
    """

    entity_id_a: uuid.UUID
    entity_id_b: uuid.UUID
    label: str | None = None


class MapConnectionResponse(BaseModel):
    """Response model for a single connection."""

    model_config = ConfigDict(from_attributes=True)

    connection_id: uuid.UUID
    scenario_id: uuid.UUID
    entity_id_a: uuid.UUID
    entity_id_b: uuid.UUID
    label: str | None = None


class MapConnectionListResponse(BaseModel):
    """Response model for listing a scenario's connections."""

    items: list[MapConnectionResponse]
