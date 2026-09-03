"""Pydantic request and response schemas for master-mode End Conditions."""

import uuid

from pydantic import BaseModel, ConfigDict, Field

OUTCOME_TAGS = ("win", "lose")
_OUTCOME_TAG_PATTERN = "^(" + "|".join(OUTCOME_TAGS) + ")$"


class EndConditionCreate(BaseModel):
    """Payload to create a win/lose condition with a named outcome."""

    condition_expression: dict[str, object] = Field(default_factory=dict)
    outcome_tag: str = Field(..., pattern=_OUTCOME_TAG_PATTERN)
    outcome_title: str = Field(..., max_length=255)
    outcome_text: str
    is_secret: bool = False
    priority: int = 0


class EndConditionUpdate(BaseModel):
    """Payload to update an existing end condition."""

    condition_expression: dict[str, object] | None = None
    outcome_tag: str | None = Field(default=None, pattern=_OUTCOME_TAG_PATTERN)
    outcome_title: str | None = Field(default=None, max_length=255)
    outcome_text: str | None = None
    is_secret: bool | None = None
    priority: int | None = None


class EndConditionResponse(BaseModel):
    """Response model for a single end condition."""

    model_config = ConfigDict(from_attributes=True)

    end_condition_id: uuid.UUID
    scenario_id: uuid.UUID
    condition_expression: dict[str, object] = Field(default_factory=dict)
    outcome_tag: str
    outcome_title: str
    outcome_text: str
    is_secret: bool = False
    priority: int = 0


class EndConditionListResponse(BaseModel):
    """Response model for listing a scenario's end conditions."""

    items: list[EndConditionResponse]


class EndConditionReorderRequest(BaseModel):
    """Payload to reorder a scenario's end conditions in one batch.

    Consumed by the Studio's drag-reorder UI (master-mode-studio-ui.spec.md).
    """

    ordered_end_condition_ids: list[uuid.UUID]
