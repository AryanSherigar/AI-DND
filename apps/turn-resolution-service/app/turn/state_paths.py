"""Dot-path get/set helpers over Playthrough.state, entity-attribute-aware.

Not itself part of master-mode-turn-pipeline.spec.md's file list, but shared,
necessary infrastructure: expression_evaluator.py (reads), condition_evaluator
.py (Effect C writes), and state_validator.py (mutation writes) all need the
same path semantics — a path whose root segment is an entity UUID resolves
under state["entities"][<uuid>], everything else resolves directly against
the top-level state tree (e.g. "player.health").
"""

from __future__ import annotations

import uuid


def _is_entity_id(segment: str) -> bool:
    try:
        uuid.UUID(segment)
    except ValueError:
        return False
    return True


def get_field_value(state: dict[str, object], path: str) -> object:
    """Read a value at a dot-path, or None if any segment is missing."""
    root, *rest = path.split(".")
    node: object
    if _is_entity_id(root):
        node = state.get("entities", {}).get(root, {})
    else:
        node = state.get(root)
    for key in rest:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
    return node


def set_field_value(
    state: dict[str, object], path: str, value: object
) -> dict[str, object]:
    """Return a new state dict with the value at path set (copy-on-write)."""
    root, *rest = path.split(".")
    new_state = dict(state)
    if _is_entity_id(root):
        entities = dict(new_state.get("entities", {}))
        entity_attrs = dict(entities.get(root, {}))
        _set_nested(entity_attrs, rest, value)
        entities[root] = entity_attrs
        new_state["entities"] = entities
        return new_state
    if not rest:
        new_state[root] = value
        return new_state
    node = dict(new_state.get(root, {}))
    _set_nested(node, rest, value)
    new_state[root] = node
    return new_state


def _set_nested(node: dict[str, object], keys: list[str], value: object) -> None:
    """Copy-on-write set into a nested dict along keys (mutates node in place —
    node itself is always a fresh copy handed in by the caller above)."""
    if len(keys) == 1:
        node[keys[0]] = value
        return
    key, *remaining = keys
    child = dict(node.get(key, {}))
    _set_nested(child, remaining, value)
    node[key] = child


def apply_mutation(
    state: dict[str, object], path: str, op: str, value: object
) -> dict[str, object]:
    """Apply a set/increment/decrement StateMutation op at path.

    Shared by condition_evaluator.py's Effect C and
    minigame_result_resolver.py's win/lose/tiered/timeout outcome mutations —
    the only two callers that apply an already-computed StateMutation
    directly to state (validate_mutation.py's tool-call path computes its own
    new value from a ProposedMutation and does not go through here).
    """
    if op == "set":
        new_value = value
    elif op in ("increment", "decrement"):
        current = get_field_value(state, path) or 0
        delta = float(value or 0)
        new_value = (
            float(current) + delta if op == "increment" else float(current) - delta
        )
    else:
        return state
    return set_field_value(state, path, new_value)
