"""Unit tests for expression_validator — pure logic, no I/O."""

from app.models.assistant import AssistantEntitySummary
from app.services.expression_validator import (
    build_available_field_paths,
    validate_expression_tree,
)


def test_build_available_field_paths_includes_state_and_entity_fields() -> None:
    state_schema = {
        "gold": {"type": "number"},
        "party": {
            "type": "object",
            "fields": {"morale": {"type": "number"}},
        },
        "inventory": {"type": "list", "item_type": "string"},
    }
    entities = [
        AssistantEntitySummary(
            entity_id="e1",
            entity_type="character",
            canonical_name="The Warden",
            attributes_schema={"loyalty": {"type": "number"}},
        )
    ]
    paths = build_available_field_paths(state_schema, entities)
    assert paths == {"gold", "party.morale", "the_warden.loyalty"}


def test_validate_expression_tree_accepts_a_valid_simple_expression() -> None:
    errors = validate_expression_tree(
        {"field": "gold", "op": ">=", "value": 100}, {"gold"}
    )
    assert errors == []


def test_validate_expression_tree_flags_unknown_field() -> None:
    errors = validate_expression_tree(
        {"field": "mana", "op": ">=", "value": 10}, {"gold"}
    )
    assert any("Unknown field 'mana'" in e for e in errors)


def test_validate_expression_tree_flags_invalid_operator() -> None:
    errors = validate_expression_tree(
        {"field": "gold", "op": "~=", "value": 10}, {"gold"}
    )
    assert any("Invalid operator" in e for e in errors)


def test_validate_expression_tree_flags_missing_value() -> None:
    errors = validate_expression_tree({"field": "gold", "op": ">="}, {"gold"})
    assert any("missing a 'value'" in e for e in errors)


def test_validate_expression_tree_recurses_into_combinators() -> None:
    expression = {
        "field": "gold",
        "op": ">=",
        "value": 100,
        "AND": {"field": "unknown_field", "op": "==", "value": "x"},
    }
    errors = validate_expression_tree(expression, {"gold"})
    assert any("Unknown field 'unknown_field'" in e for e in errors)


def test_validate_expression_tree_rejects_non_dict() -> None:
    errors = validate_expression_tree("not-a-dict", {"gold"})
    assert errors == ["Expression must be a JSON object."]
