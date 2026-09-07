"""Unit tests for turn/state_paths.py."""

from app.turn import state_paths


def test_apply_mutation_preserves_integer_types_on_increment() -> None:
    state: dict[str, object] = {"player": {"gold": 100}}
    updated = state_paths.apply_mutation(state, "player.gold", "increment", 15)
    result_value = state_paths.get_field_value(updated, "player.gold")

    assert result_value == 115
    assert type(result_value) is int


def test_apply_mutation_preserves_integer_types_on_decrement() -> None:
    state: dict[str, object] = {"player": {"gold": 100}}
    updated = state_paths.apply_mutation(state, "player.gold", "decrement", 30)
    result_value = state_paths.get_field_value(updated, "player.gold")

    assert result_value == 70
    assert type(result_value) is int


def test_apply_mutation_uses_float_when_operands_contain_float() -> None:
    state: dict[str, object] = {"player": {"gold": 100.5}}
    updated = state_paths.apply_mutation(state, "player.gold", "increment", 5)
    result_value = state_paths.get_field_value(updated, "player.gold")

    assert result_value == 105.5
    assert type(result_value) is float

    state_int: dict[str, object] = {"player": {"gold": 100}}
    updated_float_delta = state_paths.apply_mutation(
        state_int, "player.gold", "increment", 5.5
    )
    result_float_delta = state_paths.get_field_value(updated_float_delta, "player.gold")

    assert result_float_delta == 105.5
    assert type(result_float_delta) is float


def test_apply_mutation_does_not_treat_bool_as_int() -> None:
    state: dict[str, object] = {"flags": {"has_key": True}}
    updated = state_paths.apply_mutation(state, "flags.has_key", "increment", 1)
    result_value = state_paths.get_field_value(updated, "flags.has_key")

    assert result_value == 2.0
    assert type(result_value) is float


def test_apply_mutation_set_op() -> None:
    state: dict[str, object] = {"player": {"name": "Hero"}}
    updated = state_paths.apply_mutation(state, "player.name", "set", "Champion")
    assert state_paths.get_field_value(updated, "player.name") == "Champion"


def test_apply_mutation_unknown_op_returns_unchanged_state() -> None:
    state: dict[str, object] = {"player": {"gold": 50}}
    updated = state_paths.apply_mutation(state, "player.gold", "unknown_op", 10)
    assert updated == state
