"""Unit tests for turn_summary_builder.py — pure, no I/O."""

from app.turn.steps.turn_summary_builder import build_turn_summary

_SNAPSHOT = {
    "state_schema": {
        "player": {
            "type": "object",
            "fields": {
                "health": {"type": "number", "label": "Health"},
                "sanity": {"type": "number"},
            },
        }
    },
    "entities": [
        {
            "entity_id": "warden-1",
            "canonical_name": "The Warden",
            "attributes_schema": {
                "awareness": {"type": "number", "label": "Awareness"}
            },
        },
        {"entity_id": "sword-1", "canonical_name": "Rusty Sword"},
    ],
}


def test_set_field_produces_stat_change_without_delta() -> None:
    tool_calls = [
        {
            "tool_name": "set_field",
            "arguments": {"path": "player.sanity", "value": 50},
            "result": {"success": True},
            "is_valid": True,
        }
    ]
    pre_state = {"player": {"sanity": 100}}
    post_state = {"player": {"sanity": 50}}

    summary = build_turn_summary(tool_calls, pre_state, post_state, _SNAPSHOT, [])

    assert len(summary.stat_changes) == 1
    change = summary.stat_changes[0]
    assert change.path == "player.sanity"
    assert change.label == "Sanity"
    assert change.before == 100
    assert change.after == 50
    assert change.delta is None


def test_adjust_numeric_field_produces_stat_change_with_delta_and_schema_label() -> (
    None
):
    tool_calls = [
        {
            "tool_name": "adjust_numeric_field",
            "arguments": {"path": "player.health", "delta": -15},
            "result": {"success": True},
            "is_valid": True,
        }
    ]
    pre_state = {"player": {"health": 100}}
    post_state = {"player": {"health": 85}}

    summary = build_turn_summary(tool_calls, pre_state, post_state, _SNAPSHOT, [])

    change = summary.stat_changes[0]
    assert change.label == "Health"
    assert change.before == 100
    assert change.after == 85
    assert change.delta == -15.0


def test_adjust_numeric_field_on_entity_uses_entity_name_and_attribute_label() -> None:
    tool_calls = [
        {
            "tool_name": "adjust_numeric_field",
            "arguments": {"path": "warden-1.awareness", "delta": 10},
            "result": {"success": True},
            "is_valid": True,
        }
    ]
    pre_state = {"entities": {"warden-1": {"awareness": 40}}}
    post_state = {"entities": {"warden-1": {"awareness": 50}}}

    summary = build_turn_summary(tool_calls, pre_state, post_state, _SNAPSHOT, [])

    assert summary.stat_changes[0].label == "The Warden — Awareness"


def test_add_inventory_item_resolves_entity_display_name() -> None:
    tool_calls = [
        {
            "tool_name": "add_inventory_item",
            "arguments": {"path": "player.inventory", "entity_id": "sword-1"},
            "result": {"success": True},
            "is_valid": True,
        }
    ]

    summary = build_turn_summary(tool_calls, {}, {}, _SNAPSHOT, [])

    assert len(summary.inventory_changes) == 1
    change = summary.inventory_changes[0]
    assert change.entity_id == "sword-1"
    assert change.entity_display_name == "Rusty Sword"


def test_add_inventory_item_falls_back_to_entity_id_when_unresolved() -> None:
    tool_calls = [
        {
            "tool_name": "add_inventory_item",
            "arguments": {"path": "player.inventory", "entity_id": "unknown-id"},
            "result": {"success": True},
            "is_valid": True,
        }
    ]

    summary = build_turn_summary(tool_calls, {}, {}, _SNAPSHOT, [])

    assert summary.inventory_changes[0].entity_display_name == "unknown-id"


def test_roll_dice_formats_expression_for_positive_negative_and_zero_modifier() -> None:
    def roll(sides, modifier, roll, total):
        return {
            "tool_name": "roll_dice",
            "arguments": {"sides": sides, "modifier": modifier},
            "result": {"roll": roll, "modifier": modifier, "total": total},
            "is_valid": True,
        }

    summary = build_turn_summary(
        [roll(20, 3, 10, 13), roll(6, -1, 4, 3), roll(20, 0, 15, 15)],
        {},
        {},
        _SNAPSHOT,
        [],
    )

    expressions = [r.expression for r in summary.dice_rolls]
    assert expressions == ["d20+3", "d6-1", "d20"]
    assert summary.dice_rolls[0].total == 13


def test_invalid_tool_calls_are_excluded() -> None:
    tool_calls = [
        {
            "tool_name": "adjust_numeric_field",
            "arguments": {"path": "player.health", "delta": -15},
            "result": {"error": "invariant violated"},
            "is_valid": False,
        }
    ]

    summary = build_turn_summary(tool_calls, {}, {}, _SNAPSHOT, [])

    assert summary.stat_changes == []


def test_empty_tool_calls_produce_empty_payload() -> None:
    summary = build_turn_summary([], {}, {}, _SNAPSHOT, ["Bleeding Out"])

    assert summary.stat_changes == []
    assert summary.inventory_changes == []
    assert summary.dice_rolls == []
    assert summary.active_conditions == ["Bleeding Out"]
