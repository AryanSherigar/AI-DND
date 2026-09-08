"""Pydantic request and response schemas for master-mode Minigames.

StateMutation is imported from app.models.condition, never redefined — the
single-definition rule in practice (docs/specs/master-mode-minigames.spec.md).
"""

import re
import uuid
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.config import settings
from app.models.condition import StateMutation

MINIGAME_TYPES = ("dodge", "replit_embed")
_MINIGAME_TYPE_PATTERN = "^(" + "|".join(MINIGAME_TYPES) + ")$"

OUTCOME_MODES = ("binary", "tiered")
_OUTCOME_MODE_PATTERN = "^(" + "|".join(OUTCOME_MODES) + ")$"
_UPLOADED_IMAGE_PATH = re.compile(
    r"^/uploads/(?:scenario-covers|scenario-maps)/"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    r"\.(?:jpg|png|webp)$",
    re.IGNORECASE,
)
_UPLOADED_AUDIO_PATH = re.compile(
    r"^/uploads/scenario-audio/"
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    r"\.(?:mp3|ogg|wav)$",
    re.IGNORECASE,
)


def _is_uploaded_reference(value: str, path_pattern: re.Pattern[str]) -> bool:
    """Accept only URLs emitted by the application's current image uploader.

    Development storage emits ``CORE_API_PUBLIC_URL/uploads/<known-prefix>/``
    and GCS emits a public bucket URL. A substring check would let an
    arbitrary third-party URL masquerade as an upload.
    """
    parsed = urlparse(value)
    if parsed.query or parsed.fragment:
        return False
    if not parsed.scheme and not parsed.netloc:
        return bool(path_pattern.fullmatch(parsed.path))

    core_api = urlparse(settings.core_api_public_url)
    if (
        parsed.scheme == core_api.scheme
        and parsed.netloc == core_api.netloc
        and path_pattern.fullmatch(parsed.path)
    ):
        return True
    # GCS stores object keys without the local "/uploads" path. It is handled
    # explicitly rather than permitting arbitrary public hosts.
    return (
        parsed.scheme == "https"
        and parsed.netloc == "storage.googleapis.com"
        and bool(settings.gcs_bucket_name)
        and bool(
            path_pattern.fullmatch(
                "/uploads/" + parsed.path.removeprefix(f"/{settings.gcs_bucket_name}/")
            )
        )
    )


def _is_uploaded_image_reference(value: str) -> bool:
    return _is_uploaded_reference(value, _UPLOADED_IMAGE_PATH)


def _is_uploaded_audio_reference(value: str) -> bool:
    return _is_uploaded_reference(value, _UPLOADED_AUDIO_PATH)


class TieredOutcomeRange(BaseModel):
    """One score range within a tiered-outcome minigame's mutation table."""

    min_score: int
    max_score: int
    mutation: StateMutation

    @model_validator(mode="after")
    def _validate_bounds(self) -> "TieredOutcomeRange":
        if self.min_score > self.max_score:
            raise ValueError("min_score cannot exceed max_score")
        return self


class DodgePerformanceThresholds(BaseModel):
    excellent_min_health: int = Field(default=3, ge=0, le=10)
    survive_min_health: int = Field(default=1, ge=0, le=10)

    @model_validator(mode="after")
    def _validate_order(self) -> "DodgePerformanceThresholds":
        if self.survive_min_health > self.excellent_min_health:
            raise ValueError("survive_min_health cannot exceed excellent_min_health")
        return self


class DodgeAudioSettings(BaseModel):
    music_asset_url: str | None = Field(default=None, max_length=1024)
    volume: float = Field(default=0.7, ge=0, le=1)
    muted: bool = False

    @field_validator("music_asset_url")
    @classmethod
    def _asset_is_storage_reference(cls, value: str | None) -> str | None:
        if value is not None and not _is_uploaded_audio_reference(value):
            raise ValueError(
                "asset must be an application upload reference, not an external URL"
            )
        return value


class DodgeCopy(BaseModel):
    instructions: str = Field(
        default="Survive the ashfall. Move with WASD and avoid hazards.",
        min_length=1,
        max_length=1000,
    )
    start_text: str = Field(default="Start", min_length=1, max_length=80)
    win_text: str = Field(default="Survived!", min_length=1, max_length=160)
    lose_text: str = Field(default="Defeated...", min_length=1, max_length=160)


class DodgeConfig(BaseModel):
    """Safe, presentation-focused configuration for Ashfall Dodge.

    Defaults intentionally live here rather than in clients so JSON written by
    older Studio versions (which only contained ``difficulty``) remains valid.
    Unknown future fields are ignored by older APIs for a version-tolerant
    snapshot/event contract. Collision geometry is not represented here.
    """

    model_config = ConfigDict(extra="ignore")

    version: int = Field(default=1, ge=1, le=1)
    difficulty: int = Field(default=3, ge=1, le=5)
    duration_seconds: int = Field(default=15, ge=10, le=120)
    health: int = Field(default=3, ge=1, le=10)
    invulnerability_ms: int = Field(default=1000, ge=250, le=3000)
    enabled_patterns: list[Literal["rain", "ring", "beam", "homing"]] = Field(
        default_factory=lambda: ["rain", "ring", "beam", "homing"], min_length=1
    )
    pattern_order: list[Literal["rain", "ring", "beam", "homing"]] = Field(
        default_factory=lambda: ["rain", "ring", "beam", "homing"], min_length=1
    )
    performance_thresholds: DodgePerformanceThresholds = Field(
        default_factory=DodgePerformanceThresholds
    )
    player_style: Literal["soul", "heart", "spark"] = "soul"
    obstacle_style: Literal["ash", "neon", "crystal"] = "ash"
    obstacle_color: str = Field(default="#ff8a65", pattern=r"^#[0-9a-fA-F]{6}$")
    background: Literal["void", "ember", "midnight"] = "void"
    texture: Literal["none", "grain", "stars"] = "none"
    palette: Literal["ashfall", "ember", "aurora"] = "ashfall"
    background_asset_url: str | None = Field(default=None, max_length=1024)
    audio: DodgeAudioSettings = Field(default_factory=DodgeAudioSettings)
    copy: DodgeCopy = Field(default_factory=DodgeCopy)

    @field_validator("enabled_patterns", "pattern_order")
    @classmethod
    def _patterns_are_unique(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("dodge patterns must not contain duplicates")
        return value

    @field_validator("background_asset_url")
    @classmethod
    def _asset_is_storage_reference(cls, value: str | None) -> str | None:
        if value is not None and not _is_uploaded_image_reference(value):
            raise ValueError(
                "asset must be an application upload reference, not an external URL"
            )
        return value

    @model_validator(mode="after")
    def _validate_pattern_order(self) -> "DodgeConfig":
        if set(self.enabled_patterns) != set(self.pattern_order):
            raise ValueError(
                "pattern_order must contain each enabled pattern exactly once"
            )
        return self


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
    if outcome_mode == "tiered":
        ordered_ranges = sorted(tiered_outcomes, key=lambda item: item.min_score)
        for previous, current in zip(ordered_ranges, ordered_ranges[1:]):
            # Score endpoints are inclusive, so 10..20 and 20..30 overlap.
            if current.min_score <= previous.max_score:
                raise ValueError("tiered_outcomes score ranges must not overlap")
