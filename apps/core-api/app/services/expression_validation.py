"""Shared field-reference validation for condition/invariant expression trees.

Used by ConditionService, EndConditionService, and InvariantService to reject
an expression referencing a field path that doesn't exist in the owning
scenario's state_schema or in one of its entities' attributes_schema — before
anything is persisted (master-mode-data-model.spec.md).

This is an authoring-time existence check only (does the root field exist at
all), not full nested-type validation — that's the runtime job of TRS's
dynamically-built Pydantic model (master-mode-turn-pipeline.spec.md).
"""

import uuid
from collections.abc import Callable

from app.db.models.entity import Entity
from app.exceptions.base import BaseAppException

_CONNECTIVES = ("AND", "OR", "NOT")


def validate_expression_field_references(
    expression: dict[str, object] | None,
    state_schema: dict[str, object],
    entities_by_id: dict[uuid.UUID, Entity],
    error_factory: Callable[[str], BaseAppException],
) -> None:
    """Recursively validate every field path in an expression tree.

    error_factory builds the caller's own domain exception (e.g.
    ConditionValidationError, InvariantValidationError) so each domain keeps
    raising its own typed exception rather than a borrowed one.
    """
    if not expression:
        return

    field = expression.get("field")
    if field is not None:
        _validate_field_path(str(field), state_schema, entities_by_id, error_factory)

    for connective in _CONNECTIVES:
        nested = expression.get(connective)
        if isinstance(nested, dict):
            validate_expression_field_references(
                nested, state_schema, entities_by_id, error_factory
            )


def _validate_field_path(
    path: str,
    state_schema: dict[str, object],
    entities_by_id: dict[uuid.UUID, Entity],
    error_factory: Callable[[str], BaseAppException],
) -> None:
    """A field path's root segment must be a state_schema key or an entity ID."""
    root = path.split(".", 1)[0]

    if root in state_schema:
        return
    if _resolves_to_known_entity(root, entities_by_id):
        return

    raise error_factory(
        f"Field '{path}' does not reference a known state_schema field or entity"
    )


def _resolves_to_known_entity(
    root: str, entities_by_id: dict[uuid.UUID, Entity]
) -> bool:
    try:
        return uuid.UUID(root) in entities_by_id
    except ValueError:
        return False
