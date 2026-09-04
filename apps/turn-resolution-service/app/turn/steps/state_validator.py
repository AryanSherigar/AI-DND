"""Validates a proposed master-mode state mutation before it's applied.

Two entry points, sharing one core check:
  - validate_mutation: computes the new value from a ProposedMutation (an AI
    tool call, via tool_handler.py) and validates it.
  - validate_applied_change: the value was already computed by the caller
    (Effect C, via condition_evaluator.py) — this just runs the schema +
    invariant checks against the already-mutated state.

Both check (a) schema/type/range via the dynamically-built Pydantic model
from models/game_state.py, coercing values (e.g. "150" -> 150.0) and merging
the coerced result back into the stored state, and (b) every rule_invariants
row from the scenario_snapshot via expression_evaluator — an invariant is
violated when its expression evaluates False against the mutated state.
"""

from __future__ import annotations

from pydantic import ValidationError

from app.models import game_state
from app.models.tool_call import ProposedMutation, ValidationResult
from app.turn import state_paths
from app.turn.expression_evaluator import evaluate

# System-maintained by map_state_sync.py (docs/specs/master-mode-maps.spec.md)
# — never a valid direct tool-call target, matching the derived-field
# read-only precedent already established below.
RESERVED_SYSTEM_PATHS = frozenset({"discovered_location_ids"})


def validate_mutation(
    mutation: ProposedMutation,
    state: dict[str, object],
    scenario_snapshot: dict[str, object],
) -> ValidationResult:
    """Validate an AI tool-call-derived mutation against schema and invariants."""
    if mutation.op == "roll":
        return ValidationResult(is_valid=True, updated_state=state)
    if not mutation.path:
        return ValidationResult(
            is_valid=False, error_message="Missing mutation target path"
        )
    if mutation.path in RESERVED_SYSTEM_PATHS:
        return ValidationResult(
            is_valid=False,
            error_message=f"'{mutation.path}' is system-managed and cannot be set directly",
        )

    state_schema, entities = _snapshot_schemas(scenario_snapshot)
    field_def = _lookup_field_def(mutation.path, state_schema, entities)
    if field_def is None:
        return ValidationResult(
            is_valid=False, error_message=f"Unknown field path '{mutation.path}'"
        )
    if field_def.get("derived") is True:
        return ValidationResult(
            is_valid=False,
            error_message=f"'{mutation.path}' is a derived field and cannot be set directly",
        )

    try:
        new_value = _compute_new_value(mutation, state)
    except (TypeError, ValueError) as exc:
        return ValidationResult(is_valid=False, error_message=str(exc))

    updated_state = state_paths.set_field_value(state, mutation.path, new_value)
    return _validate_and_finalize(mutation.path, updated_state, scenario_snapshot)


def validate_applied_change(
    path: str, updated_state: dict[str, object], scenario_snapshot: dict[str, object]
) -> ValidationResult:
    """Validate a mutation Effect C already applied (schema + invariants only)."""
    return _validate_and_finalize(path, updated_state, scenario_snapshot)


def _validate_and_finalize(
    path: str, updated_state: dict[str, object], scenario_snapshot: dict[str, object]
) -> ValidationResult:
    state_schema, entities = _snapshot_schemas(scenario_snapshot)
    schema_error, coerced_state = _validate_and_coerce_schema(
        path, updated_state, state_schema, entities
    )
    if schema_error:
        return ValidationResult(is_valid=False, error_message=schema_error)

    rule_invariants = scenario_snapshot.get("rule_invariants", []) or []
    invariant_error = _validate_invariants(rule_invariants, coerced_state)
    if invariant_error:
        return ValidationResult(is_valid=False, error_message=invariant_error)

    return ValidationResult(is_valid=True, updated_state=coerced_state)


def _snapshot_schemas(
    scenario_snapshot: dict[str, object],
) -> tuple[dict[str, object], dict[str, dict[str, object]]]:
    state_schema = scenario_snapshot.get("state_schema", {}) or {}
    entities = {
        str(e["entity_id"]): e for e in scenario_snapshot.get("entities", []) or []
    }
    return state_schema, entities


def _compute_new_value(mutation: ProposedMutation, state: dict[str, object]) -> object:
    if mutation.op == "set":
        return mutation.value
    if mutation.op == "increment":
        current = state_paths.get_field_value(state, mutation.path or "") or 0
        return float(current) + float(mutation.delta or 0)
    if mutation.op == "add_item":
        current = state_paths.get_field_value(state, mutation.path or "")
        items = list(current) if isinstance(current, list) else []
        return [*items, mutation.value]
    raise ValueError(f"Unsupported mutation op: {mutation.op}")


def _lookup_field_def(
    path: str, state_schema: dict[str, object], entities: dict[str, dict[str, object]]
) -> dict[str, object] | None:
    root, *rest = path.split(".")
    if root in entities:
        attrs_schema = entities[root].get("attributes_schema", {}) or {}
        return attrs_schema.get(rest[0]) if rest else None

    node: object = state_schema.get(root)
    for part in rest:
        if not isinstance(node, dict):
            return None
        node = node.get("fields", {}).get(part)
    return node if isinstance(node, dict) else None


def _validate_and_coerce_schema(
    path: str,
    state: dict[str, object],
    state_schema: dict[str, object],
    entities: dict[str, dict[str, object]],
) -> tuple[str | None, dict[str, object]]:
    root = path.split(".", 1)[0]
    if root in entities:
        return _validate_entity_attrs(root, state, entities[root])
    return _validate_top_level_state(state, state_schema)


def _validate_entity_attrs(
    entity_id: str, state: dict[str, object], entity: dict[str, object]
) -> tuple[str | None, dict[str, object]]:
    model = game_state.get_entity_attribute_model(
        entity.get("attributes_schema", {}) or {}
    )
    entity_state = state.get("entities", {}).get(entity_id, {})
    try:
        validated = model.model_validate(entity_state)
    except ValidationError as exc:
        return _friendly_error(exc), state
    entities = dict(state.get("entities", {}))
    entities[entity_id] = validated.model_dump()
    new_state = dict(state)
    new_state["entities"] = entities
    return None, new_state


def _validate_top_level_state(
    state: dict[str, object], state_schema: dict[str, object]
) -> tuple[str | None, dict[str, object]]:
    model = game_state.get_state_model(state_schema)
    try:
        validated = model.model_validate(state)
    except ValidationError as exc:
        return _friendly_error(exc), state
    return None, {**state, **validated.model_dump()}


def _friendly_error(exc: ValidationError) -> str:
    first = exc.errors()[0]
    field = ".".join(str(p) for p in first["loc"])
    return f"Invalid value for '{field}': {first['msg']}"


def _validate_invariants(
    rule_invariants: list[object], state: dict[str, object]
) -> str | None:
    for invariant in rule_invariants:
        if not isinstance(invariant, dict):
            continue
        expression = invariant.get("invariant_expression")
        if not evaluate(expression, state):
            return str(invariant.get("narrator_text", "A world rule was violated."))
    return None
