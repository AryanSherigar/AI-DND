"""Unit tests for turn/expression_evaluator.py's condition-expression grammar."""

import uuid

from app.turn.expression_evaluator import evaluate, extract_field_paths


def test_evaluate_comparison_operators() -> None:
    state = {"player": {"health": 50}}
    assert evaluate({"field": "player.health", "op": "<", "value": 60}, state) is True
    assert evaluate({"field": "player.health", "op": ">", "value": 60}, state) is False
    assert evaluate({"field": "player.health", "op": "==", "value": 50}, state) is True
    assert evaluate({"field": "player.health", "op": "!=", "value": 50}, state) is False
    assert evaluate({"field": "player.health", "op": "<=", "value": 50}, state) is True
    assert evaluate({"field": "player.health", "op": ">=", "value": 50}, state) is True


def test_evaluate_empty_or_missing_expression_is_false() -> None:
    assert evaluate(None, {}) is False
    assert evaluate({}, {"player": {"health": 50}}) is False


def test_evaluate_and_composition() -> None:
    state = {"player": {"health": 3}, "flags": {"entered_cave": True}}
    expr = {
        "field": "player.health",
        "op": "<",
        "value": 5,
        "AND": {"field": "flags.entered_cave", "op": "==", "value": True},
    }
    assert evaluate(expr, state) is True

    state_false = {"player": {"health": 3}, "flags": {"entered_cave": False}}
    assert evaluate(expr, state_false) is False


def test_evaluate_or_composition() -> None:
    expr = {
        "field": "player.health",
        "op": "<",
        "value": 5,
        "OR": {"field": "flags.entered_cave", "op": "==", "value": True},
    }
    assert (
        evaluate(expr, {"player": {"health": 100}, "flags": {"entered_cave": True}})
        is True
    )
    assert (
        evaluate(expr, {"player": {"health": 100}, "flags": {"entered_cave": False}})
        is False
    )


def test_evaluate_not_negation() -> None:
    expr = {"NOT": {"field": "flags.entered_cave", "op": "==", "value": True}}
    assert evaluate(expr, {"flags": {"entered_cave": False}}) is True
    assert evaluate(expr, {"flags": {"entered_cave": True}}) is False


def test_evaluate_set_membership_in_and_contains() -> None:
    state = {
        "player": {"role": "mage", "inventory": ["ember_sigil", "rustbound_blade"]}
    }
    assert (
        evaluate(
            {"field": "player.role", "op": "in", "value": ["mage", "rogue"]}, state
        )
        is True
    )
    assert (
        evaluate(
            {"field": "player.inventory", "op": "contains", "value": "ember_sigil"},
            state,
        )
        is True
    )
    assert (
        evaluate(
            {"field": "player.inventory", "op": "contains", "value": "nonexistent"},
            state,
        )
        is False
    )


def test_evaluate_string_match() -> None:
    state = {"player": {"title": "The Ashen Wanderer"}}
    assert (
        evaluate({"field": "player.title", "op": "matches", "value": "Ashen"}, state)
        is True
    )
    assert (
        evaluate({"field": "player.title", "op": "matches", "value": "Frozen"}, state)
        is False
    )


def test_evaluate_cross_field_value_reference() -> None:
    """A dotted-string value resolving to a known field is a cross-field
    reference (docs/specs/master-mode-demo-scenario.md §7's invariant)."""
    state = {"player": {"health": 90, "max_health": 100}}
    expr = {"field": "player.health", "op": "<=", "value": "player.max_health"}
    assert evaluate(expr, state) is True

    over_cap_state = {"player": {"health": 120, "max_health": 100}}
    assert evaluate(expr, over_cap_state) is False


def test_evaluate_entity_scoped_field_path() -> None:
    entity_id = str(uuid.uuid4())
    state = {"entities": {entity_id: {"health": 10}}}
    assert (
        evaluate({"field": f"{entity_id}.health", "op": "<=", "value": 0}, state)
        is False
    )
    assert (
        evaluate({"field": f"{entity_id}.health", "op": ">", "value": 0}, state) is True
    )


def test_extract_field_paths_collects_all_referenced_fields() -> None:
    expr = {
        "field": "player.health",
        "op": "<",
        "value": 5,
        "AND": {"field": "flags.entered_cave", "op": "==", "value": True},
    }
    assert extract_field_paths(expr) == {"player.health", "flags.entered_cave"}


def test_extract_field_paths_empty_expression() -> None:
    assert extract_field_paths(None) == set()
    assert extract_field_paths({}) == set()
