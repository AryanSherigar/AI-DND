"""Unit tests for minigame_trigger_evaluator.py."""

import uuid

from app.turn.steps import minigame_trigger_evaluator

_DODGE_MINIGAME = {
    "minigame_id": str(uuid.uuid4()),
    "minigame_type": "dodge",
    "label": "Warden's Onslaught",
    "trigger_condition_expression": {
        "field": "current_location_id",
        "op": "==",
        "value": "ambush_clearing",
    },
    "priority": 0,
    "outcome_mode": "binary",
    "win_mutation": {"path": "flags.tactical_advantage", "op": "set", "value": True},
    "lose_mutation": {"path": "player.health", "op": "decrement", "value": 15},
    "tiered_outcomes": [],
    "timeout_mutation": None,
    "narrator_instruction_template": "The dodge concludes: {outcome_tag}.",
    "dodge_config": {"difficulty": 3},
    "replit_embed_url": None,
}

_REPLIT_MINIGAME = {
    "minigame_id": str(uuid.uuid4()),
    "minigame_type": "replit_embed",
    "label": "Rune Matching",
    "trigger_condition_expression": {
        "field": "current_location_id",
        "op": "==",
        "value": "ambush_clearing",
    },
    "priority": 1,
    "outcome_mode": "tiered",
    "win_mutation": None,
    "lose_mutation": None,
    "tiered_outcomes": [
        {
            "min_score": 0,
            "max_score": 50,
            "mutation": {"path": "player.health", "op": "decrement", "value": 10},
        }
    ],
    "timeout_mutation": {"path": "player.health", "op": "decrement", "value": 5},
    "narrator_instruction_template": "Runes fade: {outcome_tag}.",
    "dodge_config": None,
    "replit_embed_url": "https://example.replit.dev/rune-game",
}

_STATE = {"current_location_id": "ambush_clearing"}


def test_matches_trigger_and_returns_play_time_payload() -> None:
    matched = minigame_trigger_evaluator.evaluate_trigger(
        [_DODGE_MINIGAME], _STATE, participant_count=1, timeout_seconds=20
    )

    assert matched is not None
    assert matched.payload == {
        "minigame_id": _DODGE_MINIGAME["minigame_id"],
        "minigame_type": "dodge",
        "label": "Warden's Onslaught",
        "dodge_config": {"difficulty": 3},
        "replit_embed_url": None,
        "timeout_seconds": 20,
    }


def test_payload_never_contains_mutation_or_instruction_keys() -> None:
    matched = minigame_trigger_evaluator.evaluate_trigger(
        [_DODGE_MINIGAME], _STATE, participant_count=1, timeout_seconds=20
    )

    assert matched is not None
    forbidden = {
        "win_mutation",
        "lose_mutation",
        "tiered_outcomes",
        "timeout_mutation",
        "narrator_instruction_template",
    }
    assert forbidden.isdisjoint(matched.payload.keys())


def test_priority_ordering_first_match_wins() -> None:
    """Both minigames' triggers are true; only the lower-priority (first in
    the already priority-sorted list) one's payload is stamped."""
    matched = minigame_trigger_evaluator.evaluate_trigger(
        [_DODGE_MINIGAME, _REPLIT_MINIGAME],
        _STATE,
        participant_count=1,
        timeout_seconds=20,
    )

    assert matched is not None
    assert matched.payload["minigame_id"] == _DODGE_MINIGAME["minigame_id"]


def test_solo_only_gate_blocks_multiplayer() -> None:
    matched = minigame_trigger_evaluator.evaluate_trigger(
        [_DODGE_MINIGAME], _STATE, participant_count=2, timeout_seconds=20
    )

    assert matched is None


def test_already_pending_minigame_blocks_a_new_trigger() -> None:
    state_with_pending = {**_STATE, "_pending_minigame": {"minigame_id": "already-set"}}

    matched = minigame_trigger_evaluator.evaluate_trigger(
        [_DODGE_MINIGAME], state_with_pending, participant_count=1, timeout_seconds=20
    )

    assert matched is None


def test_no_minigames_authored_returns_none() -> None:
    matched = minigame_trigger_evaluator.evaluate_trigger(
        [], _STATE, participant_count=1, timeout_seconds=20
    )

    assert matched is None


def test_no_trigger_matches_returns_none() -> None:
    matched = minigame_trigger_evaluator.evaluate_trigger(
        [_DODGE_MINIGAME],
        {"current_location_id": "safe_room"},
        participant_count=1,
        timeout_seconds=20,
    )

    assert matched is None


def test_malformed_expression_is_treated_as_no_match() -> None:
    malformed = {**_DODGE_MINIGAME, "trigger_condition_expression": 42}

    matched = minigame_trigger_evaluator.evaluate_trigger(
        [malformed], _STATE, participant_count=1, timeout_seconds=20
    )

    assert matched is None
