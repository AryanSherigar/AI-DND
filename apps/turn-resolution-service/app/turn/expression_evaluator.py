"""Shared condition-expression grammar evaluator for the turn pipeline.

The single implementation of this grammar (comparison, AND/OR/NOT nesting,
set membership, string match) — used by condition_evaluator.py (active
conditions + Effect C) and state_validator.py (rule invariants). Nothing
else in this codebase should re-implement it.

Grammar shape (matches docs/specs/master-mode-demo-scenario.md):
    {"field": "player.health", "op": "<=", "value": 5,
     "AND": {"field": "flags.entered_cave", "op": "==", "value": true}}
A node's own (field, op, value) leaf combines with at most one of AND/OR/NOT
per level — this is a simple chained grammar, not a general boolean parser.
"""

from __future__ import annotations

from app.turn import state_paths

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

_CONNECTIVES = ("AND", "OR", "NOT")


def evaluate(expression: dict[str, object] | None, state: dict[str, object]) -> bool:
    """Evaluate an expression tree against state. Empty/missing -> False."""
    if not expression:
        return False

    result: bool | None = None
    if "field" in expression:
        result = _evaluate_leaf(expression, state)

    if "AND" in expression:
        sub = evaluate(expression["AND"], state)  # type: ignore[arg-type]
        result = sub if result is None else (result and sub)
    if "OR" in expression:
        sub = evaluate(expression["OR"], state)  # type: ignore[arg-type]
        result = sub if result is None else (result or sub)
    if "NOT" in expression:
        sub = not evaluate(expression["NOT"], state)  # type: ignore[arg-type]
        result = sub if result is None else (result and sub)

    return bool(result) if result is not None else False


def extract_field_paths(expression: dict[str, object] | None) -> set[str]:
    """Every field path an expression tree references — used to scope which
    conditions/invariants need re-evaluating when only some fields changed."""
    if not expression:
        return set()
    paths: set[str] = set()
    if "field" in expression:
        paths.add(str(expression["field"]))
    for connective in _CONNECTIVES:
        nested = expression.get(connective)
        if isinstance(nested, dict):
            paths |= extract_field_paths(nested)
    return paths


def _evaluate_leaf(expression: dict[str, object], state: dict[str, object]) -> bool:
    field_path = str(expression["field"])
    op = str(expression.get("op", "=="))
    comparator = _COMPARISON_OPS.get(op)
    if comparator is None:
        return False
    actual = state_paths.get_field_value(state, field_path)
    expected = _resolve_operand(expression.get("value"), state)
    try:
        return bool(comparator(actual, expected))
    except TypeError:
        return False


def _resolve_operand(value: object, state: dict[str, object]) -> object:
    """A dotted-string value that resolves to a known field is treated as a
    cross-field reference (e.g. "player.max_health" in an invariant);
    otherwise it's a literal. See master-mode-demo-scenario.md §7."""
    if isinstance(value, str) and "." in value:
        resolved = state_paths.get_field_value(state, value)
        if resolved is not None:
            return resolved
    return value


def _safe_num(value: object) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return float("nan")
