"""Pydantic request and response schemas for master-mode Minigames.

StateMutation is imported from app.models.condition, never redefined — the
single-definition rule in practice (docs/specs/master-mode-minigames.spec.md).
"""

import uuid

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.condition import StateMutation

MINIGAME_TYPES = ("dodge", "replit_embed")
_MINIGAME_TYPE_PATTERN = "^(" + "|".join(MINIGAME_TYPES) + ")$"

OUTCOME_MODES = ("binary", "tiered")
_OUTCOME_MODE_PATTERN = "^(" + "|".join(OUTCOME_MODES) + ")$"


class TieredOutcomeRange(BaseModel):
    """One score range within a tiered-outcome minigame's mutation table."""

    min_score: int
    max_score: int
    mutation: StateMutation


class DodgeConfig(BaseModel):
    """Play-time configuration for the built-in dodge/survival minigame."""

    difficulty: int = Field(..., ge=1, le=5)


class MinigameCreate(BaseModel):
    """Payload to create a new minigame trigger on a master-mode scenario."""

    label: str = Field(..., max_length=255)
    minigame_type: str = Field(..., pattern=_MINIGAME_TYPE_PATTERN)
    trigger_condition_expression: dict[str, object] = Field(default_factory=dict)
    priority: int = 0
    outcome_mode: str = Field(..., pattern=_OUTCOME_MODE_PATTERN)
    win_mutation: StateMutation | None = None
    lose_mutation: StateMutation | None = None
    tiered_outcomes: list[TieredOutcomeRange] = Field(default_factory=list)
    timeout_mutation: StateMutation | None = None
    narrator_instruction_template: str | None = None
    dodge_config: DodgeConfig | None = None
    replit_embed_url: str | None = Field(default=None, max_length=1024)

    @model_validator(mode="after")
    def _validate_shape(self) -> "MinigameCreate":
        _validate_type_config_pairing(
            self.minigame_type, self.dodge_config, self.replit_embed_url
        )
        _validate_outcome_mutation_pairing(
            self.outcome_mode,
            self.win_mutation,
            self.lose_mutation,
            self.tiered_outcomes,
        )
        return self


class MinigameUpdate(BaseModel):
    """Payload to update an existing minigame's mutable fields.

    Cross-field shape validation (type/config pairing, outcome/mutation
    pairing) only applies at create time here — a partial PATCH cannot see
    the persisted fields it isn't touching, so MinigameService re-validates
    the merged result after applying the update.
    """

    label: str | None = Field(default=None, max_length=255)
    trigger_condition_expression: dict[str, object] | None = None
    priority: int | None = None
    outcome_mode: str | None = Field(default=None, pattern=_OUTCOME_MODE_PATTERN)
    win_mutation: StateMutation | None = None
    lose_mutation: StateMutation | None = None
    tiered_outcomes: list[TieredOutcomeRange] | None = None
    timeout_mutation: StateMutation | None = None
    narrator_instruction_template: str | None = None
    dodge_config: DodgeConfig | None = None
    replit_embed_url: str | None = Field(default=None, max_length=1024)


class MinigameResponse(BaseModel):
    """Response model for a single minigame."""

    model_config = ConfigDict(from_attributes=True)

    minigame_id: uuid.UUID
    scenario_id: uuid.UUID
    label: str
    minigame_type: str
    trigger_condition_expression: dict[str, object] = Field(default_factory=dict)
    priority: int = 0
    outcome_mode: str
    win_mutation: StateMutation | None = None
    lose_mutation: StateMutation | None = None
    tiered_outcomes: list[TieredOutcomeRange] = Field(default_factory=list)
    timeout_mutation: StateMutation | None = None
    narrator_instruction_template: str | None = None
    dodge_config: DodgeConfig | None = None
    replit_embed_url: str | None = None


class MinigameListResponse(BaseModel):
    """Response model for listing a scenario's minigames."""

    items: list[MinigameResponse]


class MinigameReorderRequest(BaseModel):
    """Payload to reorder a scenario's minigames in one batch, matching
    end_conditions' reorder-by-priority pattern."""

    ordered_minigame_ids: list[uuid.UUID]


def _validate_type_config_pairing(
    minigame_type: str,
    dodge_config: DodgeConfig | None,
    replit_embed_url: str | None,
) -> None:
    """dodge xor replit_embed: each minigame_type owns exactly one of the
    two play-time config fields, never both, never neither."""
    if minigame_type == "dodge" and (
        dodge_config is None or replit_embed_url is not None
    ):
        raise ValueError("dodge minigames require dodge_config, not replit_embed_url")
    if minigame_type == "replit_embed" and (
        not replit_embed_url or dodge_config is not None
    ):
        raise ValueError(
            "replit_embed minigames require replit_embed_url, not dodge_config"
        )


def _validate_outcome_mutation_pairing(
    outcome_mode: str,
    win_mutation: StateMutation | None,
    lose_mutation: StateMutation | None,
    tiered_outcomes: list[TieredOutcomeRange],
) -> None:
    """binary requires both win_mutation/lose_mutation and no tiered_outcomes;
    tiered requires at least one tiered_outcomes entry."""
    if outcome_mode == "binary" and (
        win_mutation is None or lose_mutation is None or tiered_outcomes
    ):
        raise ValueError(
            "binary outcome_mode requires win_mutation and lose_mutation, "
            "no tiered_outcomes"
        )
    if outcome_mode == "tiered" and not tiered_outcomes:
        raise ValueError(
            "tiered outcome_mode requires at least one tiered_outcomes entry"
        )
