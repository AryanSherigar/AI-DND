"""Validates AI-generated expression trees before they reach the creator.

Mirrors the field-path vocabulary the frontend's ExpressionBuilder already
builds (studio/components/ConditionEditor/ExpressionBuilder/availableFields.ts)
so a hallucinated field reference is caught server-side instead of silently
producing a rule that can never fire.
"""

import re

from app.models.assistant import AssistantEntitySummary

_VALID_OPERATORS = {"==", "!=", "<", "<=", ">", ">=", "in", "contains", "matches"}
_COMBINATOR_KEYS = ("AND", "OR", "NOT")


def _slugify(canonical_name: str) -> str:
    return re.sub(r"\s+", "_", canonical_name.strip().lower())


def _state_field_paths(state_schema: dict[str, object], prefix: str) -> set[str]:
    paths: set[str] = set()
    for key, definition in state_schema.items():
        path = f"{prefix}.{key}" if prefix else key
        if not isinstance(definition, dict):
            paths.add(path)
            continue
        field_type = definition.get("type")
        if field_type == "list":
            continue
        if field_type == "object":
            nested = definition.get("fields")
            if isinstance(nested, dict):
                paths.update(_state_field_paths(nested, path))
            continue
        paths.add(path)
    return paths


def _entity_field_paths(entities: list[AssistantEntitySummary]) -> set[str]:
    paths: set[str] = set()
    for entity in entities:
        slug = _slugify(entity.canonical_name)
        for attribute_key in entity.attributes_schema:
            paths.add(f"{slug}.{attribute_key}")
    return paths


def build_available_field_paths(
    state_schema: dict[str, object], entities: list[AssistantEntitySummary]
) -> set[str]:
    """Every field path a condition/invariant/end-condition expression may reference."""
    return _state_field_paths(state_schema, "") | _entity_field_paths(entities)


def validate_expression_tree(
    expression: object, available_fields: set[str]
) -> list[str]:
    """Returns human-readable errors for an expression tree, empty if valid."""
    if not isinstance(expression, dict):
        return ["Expression must be a JSON object."]

    errors: list[str] = []
    field = expression.get("field")
    op = expression.get("op")
    has_value = "value" in expression

    if not field or not isinstance(field, str):
        errors.append("Expression is missing a 'field'.")
    elif field not in available_fields:
        errors.append(
            f"Unknown field '{field}' — not found in tracked values or entity attributes."
        )

    if not op or op not in _VALID_OPERATORS:
        errors.append(
            f"Invalid operator '{op}' — must be one of {sorted(_VALID_OPERATORS)}."
        )

    if not has_value:
        errors.append("Expression is missing a 'value'.")

    for combinator in _COMBINATOR_KEYS:
        nested = expression.get(combinator)
        if nested is not None:
            errors.extend(validate_expression_tree(nested, available_fields))

    return errors
