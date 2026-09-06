"""Unit tests for minigame_result_resolver.py."""

from app.turn.steps import minigame_result_resolver

_SCENARIO_SNAPSHOT = {
    "state_schema": {
        "player": {
            "type": "object",
            "fields": {"health": {"type": "number", "min": 0, "max": 100}},
        },
        "flags": {
            "type": "object",
            "fields": {"tactical_advantage": {"type": "boolean"}},
        },
    },
    "entities": [],
    "rule_invariants": [],
}

_BINARY_MINIGAME = {
    "minigame_id": "mg-1",
    "outcome_mode": "binary",
    "win_mutation": {"path": "flags.tactical_advantage", "op": "set", "value": True},
    "lose_mutation": {"path": "player.health", "op": "decrement", "value": 15},
    "tiered_outcomes": [],
    "timeout_mutation": {"path": "player.health", "op": "decrement", "value": 5},
    "narrator_instruction_template": "The dodge concludes: {outcome_tag}.",
}

_TIERED_MINIGAME = {
    "minigame_id": "mg-2",
    "outcome_mode": "tiered",
    "win_mutation": None,
    "lose_mutation": None,
    "tiered_outcomes": [
        {
            "min_score": 0,
            "max_score": 49,
            "mutation": {"path": "player.health", "op": "decrement", "value": 20},
        },
        {
            "min_score": 50,
            "max_score": 100,
            "mutation": {
                "path": "flags.tactical_advantage",
                "op": "set",
                "value": True,
            },
        },
    ],
    "timeout_mutation": None,
    "narrator_instruction_template": "Runes fade: {outcome_tag} (score {score}).",
}

_STATE = {"player": {"health": 100}, "flags": {"tactical_advantage": False}}


def test_binary_win_applies_win_mutation_and_builds_instruction() -> None:
    resolution = minigame_result_resolver.resolve_result(
        [_BINARY_MINIGAME], _STATE, _SCENARIO_SNAPSHOT, "mg-1", "win", None
    )

    assert resolution.state["flags"]["tactical_advantage"] is True
    assert resolution.state["player"]["health"] == 100
    assert resolution.instruction == "The dodge concludes: win."
    assert resolution.mutated_paths == {"flags.tactical_advantage"}
    assert "_pending_minigame" not in resolution.state


def test_binary_lose_applies_lose_mutation() -> None:
    resolution = minigame_result_resolver.resolve_result(
        [_BINARY_MINIGAME], _STATE, _SCENARIO_SNAPSHOT, "mg-1", "lose", None
    )

    assert resolution.state["player"]["health"] == 85.0
    assert resolution.mutated_paths == {"player.health"}


def test_timeout_applies_timeout_mutation() -> None:
    resolution = minigame_result_resolver.resolve_result(
        [_BINARY_MINIGAME], _STATE, _SCENARIO_SNAPSHOT, "mg-1", "timeout", None
    )

    assert resolution.state["player"]["health"] == 95.0
    assert resolution.mutated_paths == {"player.health"}


def test_tiered_score_in_range_applies_that_tiers_mutation() -> None:
    resolution = minigame_result_resolver.resolve_result(
        [_TIERED_MINIGAME], _STATE, _SCENARIO_SNAPSHOT, "mg-2", "win", 75
    )

    assert resolution.state["flags"]["tactical_advantage"] is True
    assert resolution.mutated_paths == {"flags.tactical_advantage"}
    assert resolution.instruction == "Runes fade: win (score 75)."


def test_tiered_score_outside_all_ranges_applies_no_mutation_but_still_clears_pending() -> (
    None
):
    state_with_pending = {**_STATE, "_pending_minigame": {"minigame_id": "mg-2"}}

    resolution = minigame_result_resolver.resolve_result(
        [_TIERED_MINIGAME], state_with_pending, _SCENARIO_SNAPSHOT, "mg-2", "win", 999
    )

    assert resolution.state["player"]["health"] == 100
    assert resolution.state["flags"]["tactical_advantage"] is False
    assert resolution.mutated_paths == set()
    assert "_pending_minigame" not in resolution.state
    assert resolution.instruction == "Runes fade: win (score 999)."


def test_minigame_not_found_in_snapshot_falls_back_gracefully() -> None:
    state_with_pending = {**_STATE, "_pending_minigame": {"minigame_id": "mg-1"}}

    resolution = minigame_result_resolver.resolve_result(
        [], state_with_pending, _SCENARIO_SNAPSHOT, "mg-1", "win", None
    )

    assert resolution.instruction == minigame_result_resolver.FALLBACK_INSTRUCTION
    assert resolution.mutated_paths == set()
    assert "_pending_minigame" not in resolution.state


def test_malformed_mutation_violating_schema_falls_back_without_failing_the_turn() -> (
    None
):
    """A win_mutation whose value violates state_schema's numeric bounds
    (health's max: 100) fails state_validator.validate_applied_change
    gracefully — no mutation applied, _pending_minigame still cleared, a
    generic fallback narrator instruction used, turn does not fail."""
    malformed_minigame = {
        **_BINARY_MINIGAME,
        "win_mutation": {"path": "player.health", "op": "set", "value": 500},
    }

    resolution = minigame_result_resolver.resolve_result(
        [malformed_minigame], _STATE, _SCENARIO_SNAPSHOT, "mg-1", "win", None
    )

    assert resolution.state["player"]["health"] == 100
    assert resolution.mutated_paths == set()
    assert resolution.instruction == minigame_result_resolver.FALLBACK_INSTRUCTION
    assert "_pending_minigame" not in resolution.state


def test_pending_minigame_cleared_unconditionally() -> None:
    state_with_pending = {**_STATE, "_pending_minigame": {"minigame_id": "mg-1"}}

    resolution = minigame_result_resolver.resolve_result(
        [_BINARY_MINIGAME], state_with_pending, _SCENARIO_SNAPSHOT, "mg-1", "win", None
    )

    assert "_pending_minigame" not in resolution.state
