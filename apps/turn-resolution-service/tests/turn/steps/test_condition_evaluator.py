"""Unit tests for condition_evaluator.py."""

import time
import uuid

from app.models.turn import LoadedState
from app.turn.steps import condition_evaluator

_CAIRN_CONDITION = {
    "label": "The Cairn Presses In",
    "condition_expression": {"field": "flags.entered_cairn", "op": "==", "value": True},
    "narrator_instruction": "The cairn presses in on the player's mind.",
    "state_mutation": {"path": "player.sanity", "op": "decrement", "value": 2},
}


def _loaded_state(
    state: dict, scenario_conditions: list, turn_count: int = 0
) -> LoadedState:
    return LoadedState(
        scenario_id=uuid.uuid4(),
        scenario_snapshot={
            "state_schema": {
                "player": {"type": "object", "fields": {"sanity": {"type": "number"}}},
                "flags": {
                    "type": "object",
                    "fields": {"entered_cairn": {"type": "boolean"}},
                },
            },
            "entities": [],
            "rule_invariants": [],
            "scenario_conditions": scenario_conditions,
        },
        state=state,
        turn_count=turn_count,
        checkpoint=None,
    )


def test_effect_c_fires_and_decrements_when_condition_true() -> None:
    loaded_state = _loaded_state(
        {"player": {"sanity": 100}, "flags": {"entered_cairn": True}},
        [_CAIRN_CONDITION],
    )
    result = condition_evaluator.evaluate_conditions(loaded_state)

    assert result.state["player"]["sanity"] == 98.0
    assert result.mutated_paths == {"player.sanity"}
    assert result.active_instructions == ["The cairn presses in on the player's mind."]


def test_effect_c_does_not_fire_when_condition_false() -> None:
    loaded_state = _loaded_state(
        {"player": {"sanity": 100}, "flags": {"entered_cairn": False}},
        [_CAIRN_CONDITION],
    )
    result = condition_evaluator.evaluate_conditions(loaded_state)

    assert result.state["player"]["sanity"] == 100
    assert result.mutated_paths == set()
    assert result.active_instructions == []


def test_condition_evaluator_never_imports_gemini_client() -> None:
    """CLAUDE.md: only ai_orchestrator.py may call gemini_client — this step
    must have no such coupling at all (call-order relative to the actual
    Gemini call is asserted at the pipeline level, see
    test_pipeline.py::test_run_turn_master_mode_effect_c_precedes_gemini_call)."""
    assert not hasattr(condition_evaluator, "gemini_client")


def test_field_relevance_skips_conditions_referencing_unchanged_fields() -> None:
    unrelated_condition = {
        "label": "Unrelated",
        "condition_expression": {"field": "player.sanity", "op": "<", "value": 1000},
        "narrator_instruction": "Should not fire — irrelevant field didn't change.",
    }
    loaded_state = _loaded_state(
        {
            "player": {"sanity": 100},
            "flags": {"entered_cairn": True},
            "_last_changed_fields": ["flags.entered_cairn"],
        },
        [unrelated_condition, _CAIRN_CONDITION],
        turn_count=5,
    )

    result = condition_evaluator.evaluate_conditions(loaded_state)

    # _CAIRN_CONDITION references flags.entered_cairn (changed) -> evaluated, fires.
    # unrelated_condition references player.sanity (not in _last_changed_fields) -> skipped.
    assert (
        "Should not fire — irrelevant field didn't change."
        not in result.active_instructions
    )
    assert result.mutated_paths == {"player.sanity"}


def test_turn_zero_evaluates_all_conditions_regardless_of_last_changed() -> None:
    loaded_state = _loaded_state(
        {"player": {"sanity": 100}, "flags": {"entered_cairn": True}},
        [_CAIRN_CONDITION],
        turn_count=0,
    )
    result = condition_evaluator.evaluate_conditions(loaded_state)
    assert result.mutated_paths == {"player.sanity"}


def test_effect_c_mutation_violating_invariant_is_rejected_not_applied() -> None:
    snapshot_condition = {
        "label": "Runaway Buff",
        "condition_expression": {
            "field": "flags.entered_cairn",
            "op": "==",
            "value": True,
        },
        "narrator_instruction": "A surge of unnatural clarity.",
        "state_mutation": {"path": "player.sanity", "op": "set", "value": 500},
    }
    loaded_state = LoadedState(
        scenario_id=uuid.uuid4(),
        scenario_snapshot={
            "state_schema": {
                "player": {
                    "type": "object",
                    "fields": {"sanity": {"type": "number", "min": 0, "max": 100}},
                },
                "flags": {
                    "type": "object",
                    "fields": {"entered_cairn": {"type": "boolean"}},
                },
            },
            "entities": [],
            "rule_invariants": [],
            "scenario_conditions": [snapshot_condition],
        },
        state={"player": {"sanity": 50}, "flags": {"entered_cairn": True}},
        turn_count=0,
        checkpoint=None,
    )
    result = condition_evaluator.evaluate_conditions(loaded_state)

    assert result.state["player"]["sanity"] == 50  # rejected, unchanged
    assert result.mutated_paths == set()


def test_condition_evaluator_stays_well_under_100ms_with_many_conditions() -> None:
    """Informational latency benchmark, not a hard CI gate."""
    many_conditions = [
        {
            "label": f"Condition {i}",
            "condition_expression": {
                "field": "flags.entered_cairn",
                "op": "==",
                "value": True,
            },
            "narrator_instruction": f"Instruction {i}",
        }
        for i in range(20)
    ]
    loaded_state = _loaded_state(
        {"player": {"sanity": 100}, "flags": {"entered_cairn": True}}, many_conditions
    )

    start = time.monotonic()
    condition_evaluator.evaluate_conditions(loaded_state)
    duration_ms = (time.monotonic() - start) * 1000

    assert duration_ms < 100


def test_list_active_condition_labels_returns_only_true_conditions() -> None:
    inactive = {
        "label": "Warden Is Wary",
        "condition_expression": {
            "field": "the_warden.awareness",
            "op": ">=",
            "value": 50,
        },
    }
    state = {"flags": {"entered_cairn": True}, "the_warden": {"awareness": 10}}

    labels = condition_evaluator.list_active_condition_labels(
        [_CAIRN_CONDITION, inactive], state
    )

    assert labels == ["The Cairn Presses In"]


def test_list_active_condition_labels_evaluates_every_condition_not_just_changed() -> (
    None
):
    """Unlike evaluate_conditions, this checks all conditions regardless of
    _last_changed_fields — a returning player's reload has no such scoping."""
    state = {"flags": {"entered_cairn": True}}

    labels = condition_evaluator.list_active_condition_labels([_CAIRN_CONDITION], state)

    assert labels == ["The Cairn Presses In"]


def test_list_active_condition_labels_skips_non_dict_entries() -> None:
    labels = condition_evaluator.list_active_condition_labels(
        ["not-a-condition", None], {"flags": {"entered_cairn": True}}
    )

    assert labels == []


def test_list_active_condition_labels_empty_for_no_conditions() -> None:
    assert condition_evaluator.list_active_condition_labels([], {}) == []
