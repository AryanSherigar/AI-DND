"""Unit tests for tool_handler.py."""

from google.genai import types

from app.turn.steps import tool_handler


def test_prepare_mutation_set_field() -> None:
    call = types.FunctionCall(
        name="set_field", args={"path": "flags.entered_cairn", "value": "true"}
    )
    mutation = tool_handler.prepare_mutation(call)
    assert mutation.op == "set"
    assert mutation.path == "flags.entered_cairn"
    assert mutation.value == "true"


def test_prepare_mutation_adjust_numeric_field() -> None:
    call = types.FunctionCall(
        name="adjust_numeric_field", args={"path": "player.health", "delta": -15}
    )
    mutation = tool_handler.prepare_mutation(call)
    assert mutation.op == "increment"
    assert mutation.path == "player.health"
    assert mutation.delta == -15.0


def test_prepare_mutation_add_inventory_item() -> None:
    call = types.FunctionCall(
        name="add_inventory_item",
        args={"path": "player.inventory", "entity_id": "ember_sigil"},
    )
    mutation = tool_handler.prepare_mutation(call)
    assert mutation.op == "add_item"
    assert mutation.path == "player.inventory"
    assert mutation.value == "ember_sigil"


def test_prepare_mutation_roll_dice() -> None:
    call = types.FunctionCall(name="roll_dice", args={"sides": 20, "modifier": 3})
    mutation = tool_handler.prepare_mutation(call)
    assert mutation.op == "roll"
    assert mutation.sides == 20
    assert mutation.modifier == 3


def test_prepare_mutation_roll_dice_defaults_when_args_missing() -> None:
    call = types.FunctionCall(name="roll_dice", args={})
    mutation = tool_handler.prepare_mutation(call)
    assert mutation.op == "roll"
    assert mutation.sides == 20
    assert mutation.modifier == 0


def test_prepare_mutation_unknown_tool_name() -> None:
    call = types.FunctionCall(name="some_future_tool", args={})
    mutation = tool_handler.prepare_mutation(call)
    assert mutation.op == "unknown"


def test_execute_roll_dice_within_bounds() -> None:
    for _ in range(50):
        result = tool_handler.execute_roll_dice(sides=6, modifier=2)
        assert 1 <= result["roll"] <= 6
        assert result["total"] == result["roll"] + 2


def test_execute_roll_dice_handles_nonpositive_sides_safely() -> None:
    result = tool_handler.execute_roll_dice(sides=0, modifier=0)
    assert result["roll"] == 1
