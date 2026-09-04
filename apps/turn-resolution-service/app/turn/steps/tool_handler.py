"""Translates a Gemini function call into a proposed state mutation.

Pure computation only — never calls gemini_client (CLAUDE.md: only
ai_orchestrator.py may call it) and never touches Playthrough.state directly
(state_validator.py owns applying + validating). roll_dice is the one
exception: it never mutates state, so it's computed and returned here
directly with no validation step needed.
"""

from __future__ import annotations

import random

from google.genai import types

from app.models.tool_call import ProposedMutation

DEFAULT_DICE_SIDES = 20


def prepare_mutation(call: types.FunctionCall) -> ProposedMutation:
    """Translate one Gemini function call into a ProposedMutation."""
    args = dict(call.args or {})
    name = call.name or ""

    if name == "set_field":
        return ProposedMutation(
            tool_name=name, op="set", path=args.get("path"), value=args.get("value")
        )
    if name == "adjust_numeric_field":
        return ProposedMutation(
            tool_name=name,
            op="increment",
            path=args.get("path"),
            delta=_to_float(args.get("delta"), default=0.0),
        )
    if name == "add_inventory_item":
        return ProposedMutation(
            tool_name=name,
            op="add_item",
            path=args.get("path"),
            value=args.get("entity_id"),
        )
    if name == "roll_dice":
        return ProposedMutation(
            tool_name=name,
            op="roll",
            sides=_to_int(args.get("sides"), default=DEFAULT_DICE_SIDES),
            modifier=_to_int(args.get("modifier"), default=0),
        )
    return ProposedMutation(tool_name=name, op="unknown")


def execute_roll_dice(sides: int, modifier: int) -> dict[str, object]:
    """Pure dice computation — no state mutation, no validation needed."""
    safe_sides = max(sides, 1)
    roll = random.randint(1, safe_sides)
    return {"roll": roll, "modifier": modifier, "total": roll + modifier}


def _to_float(value: object, default: float) -> float:
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default


def _to_int(value: object, default: int) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
