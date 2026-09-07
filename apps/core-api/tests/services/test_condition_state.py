"""Unit tests for Core API's condition_state.py evaluator mirror."""

import pytest

from app.services.condition_state import list_active_condition_labels


def test_list_active_condition_labels_matches_true_condition() -> None:
    conditions = [
        {
            "label": "Low Health",
            "condition_expression": {
                "field": "player.health",
                "op": "<=",
                "value": 10,
            },
        },
        {
            "label": "High Health",
            "condition_expression": {
                "field": "player.health",
                "op": ">=",
                "value": 50,
            },
        },
    ]
    state = {"player": {"health": 5}}
    labels = list_active_condition_labels(conditions, state)
    assert labels == ["Low Health"]


def test_list_active_condition_labels_cross_field_ref() -> None:
    conditions = [
        {
            "label": "At or Below Max",
            "condition_expression": {
                "field": "player.health",
                "op": "<=",
                "ref": "player.max_health",
            },
        }
    ]
    state = {"player": {"health": 80, "max_health": 100}}
    assert list_active_condition_labels(conditions, state) == ["At or Below Max"]

    over_cap_state = {"player": {"health": 120, "max_health": 100}}
    assert list_active_condition_labels(conditions, over_cap_state) == []


def test_list_active_condition_labels_dotted_string_literal_not_resolved_as_ref() -> (
    None
):
    conditions = [
        {
            "label": "Has Scroll",
            "condition_expression": {
                "field": "player.item",
                "op": "==",
                "value": "scroll.txt",
            },
        }
    ]
    # State has a matching 'scroll.txt' path with an unrelated value
    state = {"player": {"item": "scroll.txt"}, "scroll": {"txt": "other"}}
    assert list_active_condition_labels(conditions, state) == ["Has Scroll"]


def test_list_active_condition_labels_multiple_connectives_raises_error() -> None:
    conditions = [
        {
            "label": "Ambiguous",
            "condition_expression": {
                "field": "player.health",
                "op": "<=",
                "value": 10,
                "AND": {"field": "player.health", "op": ">=", "value": 0},
                "OR": {"field": "flags.escaped", "op": "==", "value": True},
            },
        }
    ]
    with pytest.raises(ValueError, match="at most one connective"):
        list_active_condition_labels(conditions, {"player": {"health": 5}})
