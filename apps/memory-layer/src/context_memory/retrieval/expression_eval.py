"""`when_active` expression evaluation -- Milestone 4 of the AI-DND bridge
(ADR-9). Evaluates the exact expression-tree shape the RFC itself gives as
the canonical example:

    {"field": "player.health", "op": "<", "value": 5,
     "AND": {"field": "entered_cave", "op": "==", "value": true}}

against a `game_state` dict. `field` is a dotted path into `game_state`
(mirrors AI-DND's own `ScenarioCondition.condition_expression`, which uses
the same tree shape server-side in the Turn Resolution Service -- this is
not a new DSL, it's the one AI-DND already committed to in its RFC).
"""

from __future__ import annotations

from typing import Any

_OPERATORS = {
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    "<": lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">": lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
}


class ExpressionError(ValueError):
    """A malformed expression tree -- missing `field`/`op`, or an
    unsupported `op`. Distinct from a normal false-evaluation (missing
    game_state field, type mismatch), which resolves to `False`, not an
    error: a creator-authored condition referencing a field the current
    playthrough hasn't set yet (e.g. before it's ever been touched) is a
    common, expected case, not a broken one."""


def evaluate_expression(expression: dict[str, Any] | None, game_state: dict[str, Any]) -> bool:
    """`None` (no `when_active` on this fact) means always active -- `True`.
    A fact whose `when_active` is present but references a `field` absent
    from `game_state` evaluates `False` (the condition can't be confirmed
    true), never raises -- an unset game-state field is not a malformed
    request, it's the common "hasn't happened yet" case."""
    if expression is None:
        return True
    if "field" not in expression or "op" not in expression:
        raise ExpressionError(f"expression missing 'field' or 'op': {expression}")
    op = expression["op"]
    if op not in _OPERATORS:
        raise ExpressionError(f"unsupported op: {op!r}")

    actual = _resolve_field(expression["field"], game_state)
    result = actual is not None and _safe_compare(_OPERATORS[op], actual, expression.get("value"))

    if result and "AND" in expression:
        result = evaluate_expression(expression["AND"], game_state)
    if not result and "OR" in expression:
        result = evaluate_expression(expression["OR"], game_state)
    return result


def _resolve_field(field: str, game_state: dict[str, Any]) -> Any:
    current: Any = game_state
    for part in field.split("."):
        if not isinstance(current, dict) or part not in current:
            return None
        current = current[part]
    return current


def _safe_compare(op, actual: Any, expected: Any) -> bool:
    try:
        return bool(op(actual, expected))
    except TypeError:
        # e.g. `<` between incompatible types (a creator's `value` doesn't
        # match the game_state field's actual type) -- treated as "condition
        # not met", not a request-breaking error, consistent with a missing
        # field above.
        return False
