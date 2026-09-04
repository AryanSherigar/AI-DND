"""Read-only evaluation of scenario_conditions against live playthrough state.

Mirrors turn-resolution-service's app/turn/expression_evaluator.py::evaluate
and app/turn/state_paths.py::get_field_value grammar exactly, so a condition
Core API reports as "active" here means the same thing TRS's condition
evaluator means during a turn. Core API and TRS are separate deployables with
no shared package, so this is an intentional mirror of that grammar, not
in-codebase schema/logic duplication — see docs/specs/master-mode-demo-
scenario.md for the expression shape this evaluates.
"""

import uuid

_COMPARISON_OPS = {
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    "<": lambda a, b: _safe_num(a) < _safe_num(b),
    "<=": lambda a, b: _safe_num(a) <= _safe_num(b),
    ">": lambda a, b: _safe_num(a) > _safe_num(b),
    ">=": lambda a, b: _safe_num(a) >= _safe_num(b),
    "in": lambda a, b: a in b if isinstance(b, (list, tuple, set)) else False,
    "contains": lambda a, b: (
        b in a if isinstance(a, (list, tuple, set, str)) else False
    ),
    "matches": lambda a, b: isinstance(a, str) and isinstance(b, str) and b in a,
}


def list_active_condition_labels(
    scenario_conditions: list[object], state: dict[str, object]
) -> list[str]:
    """Every scenario_condition whose condition_expression is currently true,
    for the play screen's persistent status-badge row. Read-only — never
    applies a condition's state_mutation (that is TRS's Effect C, turn-time
    only)."""
    labels: list[str] = []
    for condition in scenario_conditions:
        if not isinstance(condition, dict):
            continue
        if not _evaluate(condition.get("condition_expression"), state):
            continue
        label = condition.get("label")
        if label:
            labels.append(str(label))
    return labels


def _evaluate(expression: object, state: dict[str, object]) -> bool:
    if not isinstance(expression, dict) or not expression:
        return False

    result: bool | None = None
    if "field" in expression:
        result = _evaluate_leaf(expression, state)
    for connective, combine in (
        ("AND", lambda r, s: s if r is None else (r and s)),
        ("OR", lambda r, s: s if r is None else (r or s)),
    ):
        if connective in expression:
            result = combine(result, _evaluate(expression[connective], state))
    if "NOT" in expression:
        negated = not _evaluate(expression["NOT"], state)
        result = negated if result is None else (result and negated)

    return bool(result) if result is not None else False


def _evaluate_leaf(expression: dict[str, object], state: dict[str, object]) -> bool:
    field_path = str(expression["field"])
    comparator = _COMPARISON_OPS.get(str(expression.get("op", "==")))
    if comparator is None:
        return False
    actual = _get_field_value(state, field_path)
    expected = _resolve_operand(expression.get("value"), state)
    try:
        return bool(comparator(actual, expected))
    except TypeError:
        return False


def _resolve_operand(value: object, state: dict[str, object]) -> object:
    if isinstance(value, str) and "." in value:
        resolved = _get_field_value(state, value)
        if resolved is not None:
            return resolved
    return value


def _get_field_value(state: dict[str, object], path: str) -> object:
    root, *rest = path.split(".")
    node: object = (
        state.get("entities", {}).get(root, {})
        if _is_entity_id(root)
        else state.get(root)
    )
    for key in rest:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def _is_entity_id(segment: str) -> bool:
    try:
        uuid.UUID(segment)
    except ValueError:
        return False
    return True


def _safe_num(value: object) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return float("nan")
