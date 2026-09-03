"""Unit tests for state_validator.py."""

from app.models.tool_call import ProposedMutation
from app.turn.steps import state_validator

_SNAPSHOT = {
    "state_schema": {
        "player": {
            "type": "object",
            "fields": {
                "health": {"type": "number", "min": 0, "max": 200, "initial": 100},
                "max_health": {"type": "number", "initial": 100},
            },
        },
        "flags": {
            "type": "object",
            "fields": {"entered_cairn": {"type": "boolean", "initial": False}},
        },
    },
    "entities": [],
    "rule_invariants": [
        {
            "label": "Health cannot exceed its cap",
            "invariant_expression": {
                "field": "player.health",
                "op": "<=",
                "value": "player.max_health",
            },
            "narrator_text": "Health can never be restored beyond its maximum.",
        }
    ],
}

_STATE = {
    "player": {"health": 100, "max_health": 100},
    "flags": {"entered_cairn": False},
}


def test_validate_mutation_rejects_wrong_type() -> None:
    mutation = ProposedMutation(
        tool_name="set_field", op="set", path="player.health", value="high"
    )
    result = state_validator.validate_mutation(mutation, _STATE, _SNAPSHOT)
    assert result.is_valid is False
    assert "health" in (result.error_message or "")


def test_validate_mutation_rejects_out_of_range_value() -> None:
    mutation = ProposedMutation(
        tool_name="set_field", op="set", path="player.health", value="500"
    )
    result = state_validator.validate_mutation(mutation, _STATE, _SNAPSHOT)
    assert result.is_valid is False


def test_validate_mutation_rejects_invariant_violation_even_when_type_and_range_valid() -> (
    None
):
    """player.health=120 is within its own 0-200 range but violates the
    cross-field invariant health <= max_health (100)."""
    mutation = ProposedMutation(
        tool_name="set_field", op="set", path="player.health", value="120"
    )
    result = state_validator.validate_mutation(mutation, _STATE, _SNAPSHOT)
    assert result.is_valid is False
    assert result.error_message == "Health can never be restored beyond its maximum."


def test_validate_mutation_accepts_valid_change() -> None:
    mutation = ProposedMutation(
        tool_name="adjust_numeric_field",
        op="increment",
        path="player.health",
        delta=-10,
    )
    result = state_validator.validate_mutation(mutation, _STATE, _SNAPSHOT)
    assert result.is_valid is True
    assert result.updated_state["player"]["health"] == 90.0


def test_validate_mutation_rejects_derived_field_target() -> None:
    """derived is a flag alongside a real type (docs/specs/master-mode-demo
    -scenario.md §4's warden_awareness), not a type value of its own."""
    snapshot = {
        **_SNAPSHOT,
        "state_schema": {
            **_SNAPSHOT["state_schema"],
            "warden_awareness": {"type": "number", "derived": True},
        },
    }
    mutation = ProposedMutation(
        tool_name="set_field", op="set", path="warden_awareness", value="5"
    )
    result = state_validator.validate_mutation(mutation, _STATE, snapshot)
    assert result.is_valid is False
    assert "derived" in (result.error_message or "")


def test_validate_mutation_rejects_unknown_field_path() -> None:
    mutation = ProposedMutation(
        tool_name="set_field", op="set", path="nowhere.field", value="x"
    )
    result = state_validator.validate_mutation(mutation, _STATE, _SNAPSHOT)
    assert result.is_valid is False


def test_validate_mutation_roll_is_always_valid_noop() -> None:
    mutation = ProposedMutation(tool_name="roll_dice", op="roll", sides=20, modifier=0)
    result = state_validator.validate_mutation(mutation, _STATE, _SNAPSHOT)
    assert result.is_valid is True
    assert result.updated_state == _STATE


def test_validate_mutation_add_item_appends_to_list() -> None:
    snapshot = {
        "state_schema": {
            "player": {
                "type": "object",
                "fields": {"inventory": {"type": "list", "item_type": "entity_ref"}},
            }
        },
        "entities": [],
        "rule_invariants": [],
    }
    state = {"player": {"inventory": ["rustbound_blade"]}}
    mutation = ProposedMutation(
        tool_name="add_inventory_item",
        op="add_item",
        path="player.inventory",
        value="ember_sigil",
    )
    result = state_validator.validate_mutation(mutation, state, snapshot)
    assert result.is_valid is True
    assert result.updated_state["player"]["inventory"] == [
        "rustbound_blade",
        "ember_sigil",
    ]


def test_validate_applied_change_checks_invariants_on_already_mutated_state() -> None:
    """Used by condition_evaluator for Effect C: the mutation is already
    applied, this only re-checks schema + invariants."""
    already_mutated = {"player": {"health": 150, "max_health": 100}, "flags": {}}
    result = state_validator.validate_applied_change(
        "player.health", already_mutated, _SNAPSHOT
    )
    assert result.is_valid is False

    valid_state = {"player": {"health": 80, "max_health": 100}, "flags": {}}
    ok_result = state_validator.validate_applied_change(
        "player.health", valid_state, _SNAPSHOT
    )
    assert ok_result.is_valid is True


def test_validate_mutation_entity_scoped_attribute() -> None:
    entity_id = "3fa85f64-5717-4562-b3fc-2c963f66afa6"
    snapshot = {
        "state_schema": {},
        "entities": [
            {
                "entity_id": entity_id,
                "attributes_schema": {
                    "health": {"type": "number", "min": 0, "max": 150, "initial": 150}
                },
            }
        ],
        "rule_invariants": [],
    }
    state = {"entities": {entity_id: {"health": 150}}}
    mutation = ProposedMutation(
        tool_name="adjust_numeric_field",
        op="increment",
        path=f"{entity_id}.health",
        delta=-20,
    )
    result = state_validator.validate_mutation(mutation, state, snapshot)
    assert result.is_valid is True
    assert result.updated_state["entities"][entity_id]["health"] == 130.0

    over_max = ProposedMutation(
        tool_name="adjust_numeric_field",
        op="increment",
        path=f"{entity_id}.health",
        delta=1000,
    )
    rejected = state_validator.validate_mutation(over_max, state, snapshot)
    assert rejected.is_valid is False
