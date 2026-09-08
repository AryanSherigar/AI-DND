"""Contract tests for version-tolerant Ashfall Dodge authoring config."""

import pytest
from pydantic import ValidationError

from app.models.minigame import DodgeConfig, MinigameCreate


def test_legacy_difficulty_only_config_receives_safe_defaults() -> None:
    config = DodgeConfig(difficulty=2)

    assert config.duration_seconds == 15
    assert config.health == 3
    assert config.pattern_order == ["rain", "ring", "beam", "homing"]
    assert config.copy.start_text == "Start"


def test_dodge_config_rejects_unfair_pattern_order_and_external_assets() -> None:
    with pytest.raises(ValidationError, match="pattern_order"):
        DodgeConfig(enabled_patterns=["rain"], pattern_order=["beam"])

    with pytest.raises(ValidationError, match="application upload"):
        DodgeConfig(background_asset_url="https://cdn.example.com/arena.png")

    # A path substring alone is not proof that this came from our uploader.
    with pytest.raises(ValidationError, match="application upload"):
        DodgeConfig(
            background_asset_url=(
                "https://attacker.example/uploads/scenario-covers/"
                "b3f91d47-bf96-4cc9-b247-705b0bb07d9a.png"
            )
        )


def test_dodge_config_accepts_existing_upload_reference() -> None:
    config = DodgeConfig(
        background_asset_url=(
            "/uploads/scenario-covers/b3f91d47-bf96-4cc9-b247-705b0bb07d9a.png"
        ),
        audio={
            "music_asset_url": (
                "/uploads/scenario-audio/b3f91d47-bf96-4cc9-b247-705b0bb07d9a.ogg"
            ),
            "volume": 0.4,
        },
    )

    assert config.audio.volume == 0.4


def test_dodge_config_rejects_image_or_foreign_audio_reference() -> None:
    with pytest.raises(ValidationError, match="application upload"):
        DodgeConfig(
            audio={
                "music_asset_url": "/uploads/scenario-covers/b3f91d47-bf96-4cc9-b247-705b0bb07d9a.png"
            }
        )


def test_tiered_outcome_ranges_reject_overlapping_inclusive_scores() -> None:
    with pytest.raises(ValidationError, match="must not overlap"):
        MinigameCreate(
            label="Tiered ashfall",
            minigame_type="dodge",
            outcome_mode="tiered",
            dodge_config={"difficulty": 3},
            tiered_outcomes=[
                {
                    "min_score": 0,
                    "max_score": 10,
                    "mutation": {"path": "player.health", "op": "set", "value": 1},
                },
                {
                    "min_score": 10,
                    "max_score": 20,
                    "mutation": {"path": "player.health", "op": "set", "value": 2},
                },
            ],
        )
