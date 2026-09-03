"""Pydantic request and response schemas for master-mode active Conditions
(ScenarioCondition), including Effect C direct state mutation."""

import uuid

from pydantic import BaseModel, ConfigDict, Field


class StateMutation(BaseModel):
    """Effect C: a direct state mutation applied pre-turn by TRS when this
    condition's expression is true (master-mode-turn-pipeline.spec.md)."""

    path: str
    op: str = Field(..., pattern="^(set|increment|decrement)$")
    value: object


class ConditionCreate(BaseModel):
    """Payload to create an active condition on a master-mode scenario."""

    label: str = Field(..., max_length=255)
    condition_expression: dict[str, object] = Field(default_factory=dict)
    narrator_instruction: str
    metadata: dict[str, object] = Field(default_factory=dict)
    state_mutation: StateMutation | None = None


class ConditionUpdate(BaseModel):
    """Payload to update an existing active condition."""

    label: str | None = Field(default=None, max_length=255)
    condition_expression: dict[str, object] | None = None
    narrator_instruction: str | None = None
    metadata: dict[str, object] | None = None
    state_mutation: StateMutation | None = None


class ConditionResponse(BaseModel):
    """Response model for a single active condition."""

    model_config = ConfigDict(from_attributes=True)

    condition_id: uuid.UUID
    scenario_id: uuid.UUID
    label: str
    condition_expression: dict[str, object] = Field(default_factory=dict)
    condition_version: str = "1.0"
    narrator_instruction: str
    # Field name matches the ORM attribute (metadata_, mapped to the DB
    # column "metadata") so from_attributes validation reads it directly;
    # serialization_alias renames it back to "metadata" in the JSON response.
    metadata_: dict[str, object] = Field(
        default_factory=dict, serialization_alias="metadata"
    )
    state_mutation: dict[str, object] | None = None


class ConditionListResponse(BaseModel):
    """Response model for listing a scenario's active conditions."""

    items: list[ConditionResponse]
