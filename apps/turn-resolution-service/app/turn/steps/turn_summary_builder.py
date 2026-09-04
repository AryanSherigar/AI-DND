"""Translates this turn's validated tool calls into a display-ready
TurnSummaryPayload for the `turn_summary` SSE event.

Pure computation only, called exclusively from pipeline.py (CLAUDE.md: steps
in steps/ never call each other). Effect C mutations (condition_evaluator.py,
pre-AI, non-tool-call) are intentionally excluded — only actual tool-call
results are translated.
"""

from __future__ import annotations

from app.models.turn_summary import (
    DiceRoll,
    InventoryChange,
    StatChange,
    TurnSummaryPayload,
)
from app.turn import state_paths
from app.turn.steps.tool_handler import DEFAULT_DICE_SIDES

_STAT_TOOL_NAMES = ("set_field", "adjust_numeric_field")


def build_turn_summary(
    tool_calls: list[dict[str, object]],
    pre_state: dict[str, object],
    post_state: dict[str, object],
    scenario_snapshot: dict[str, object],
    active_conditions: list[str],
) -> TurnSummaryPayload:
    """Build the display-ready delta payload for one master-mode turn."""
    entities = _entity_index(scenario_snapshot)
    state_schema = scenario_snapshot.get("state_schema", {}) or {}
    stat_changes: list[StatChange] = []
    inventory_changes: list[InventoryChange] = []
    dice_rolls: list[DiceRoll] = []

    for call in tool_calls:
        if not call.get("is_valid"):
            continue
        tool_name = call.get("tool_name")
        if tool_name in _STAT_TOOL_NAMES:
            stat_changes.append(
                _build_stat_change(call, pre_state, post_state, entities, state_schema)
            )
        elif tool_name == "add_inventory_item":
            inventory_changes.append(_build_inventory_change(call, entities))
        elif tool_name == "roll_dice":
            dice_rolls.append(_build_dice_roll(call))

    return TurnSummaryPayload(
        stat_changes=stat_changes,
        inventory_changes=inventory_changes,
        dice_rolls=dice_rolls,
        active_conditions=active_conditions,
    )


def _entity_index(
    scenario_snapshot: dict[str, object],
) -> dict[str, dict[str, object]]:
    entities = scenario_snapshot.get("entities", []) or []
    return {
        str(e["entity_id"]): e
        for e in entities
        if isinstance(e, dict) and "entity_id" in e
    }


def _build_stat_change(
    call: dict[str, object],
    pre_state: dict[str, object],
    post_state: dict[str, object],
    entities: dict[str, dict[str, object]],
    state_schema: dict[str, object],
) -> StatChange:
    arguments = call.get("arguments", {}) or {}
    path = str(arguments.get("path") or "")
    before = state_paths.get_field_value(pre_state, path)
    after = state_paths.get_field_value(post_state, path)
    is_adjustment = call.get("tool_name") == "adjust_numeric_field"
    return StatChange(
        path=path,
        label=_humanize_path(path, entities, state_schema),
        before=before,
        after=after,
        delta=_numeric_delta(before, after) if is_adjustment else None,
    )


def _build_inventory_change(
    call: dict[str, object], entities: dict[str, dict[str, object]]
) -> InventoryChange:
    arguments = call.get("arguments", {}) or {}
    path = str(arguments.get("path") or "")
    entity_id = str(arguments.get("entity_id") or "")
    entity = entities.get(entity_id, {})
    return InventoryChange(
        path=path,
        entity_id=entity_id,
        entity_display_name=str(entity.get("canonical_name") or entity_id),
    )


def _build_dice_roll(call: dict[str, object]) -> DiceRoll:
    arguments = call.get("arguments", {}) or {}
    result = call.get("result", {}) or {}
    sides = _to_int(arguments.get("sides"), DEFAULT_DICE_SIDES)
    modifier = _to_int(result.get("modifier"), 0)
    roll = _to_int(result.get("roll"), 0)
    return DiceRoll(
        expression=_format_dice_expression(sides, modifier),
        sides=sides,
        modifier=modifier,
        roll=roll,
        total=_to_int(result.get("total"), roll + modifier),
    )


def _humanize_path(
    path: str, entities: dict[str, dict[str, object]], state_schema: dict[str, object]
) -> str:
    root, *rest = path.split(".") if path else [""]
    entity = entities.get(root)
    if entity:
        return _humanize_entity_field(entity, rest)
    return _lookup_schema_label(state_schema, path) or _title_case(
        rest[-1] if rest else root
    )


def _humanize_entity_field(entity: dict[str, object], rest: list[str]) -> str:
    field_key = rest[-1] if rest else ""
    attributes_schema = entity.get("attributes_schema", {}) or {}
    field_schema = attributes_schema.get(field_key, {}) or {}
    label = field_schema.get("label") or _title_case(field_key)
    return f"{entity.get('canonical_name', '')} — {label}".strip(" —")


def _lookup_schema_label(state_schema: dict[str, object], path: str) -> str | None:
    node: object = state_schema
    label: str | None = None
    for segment in path.split("."):
        if not isinstance(node, dict):
            break
        field_def = node.get(segment)
        if not isinstance(field_def, dict):
            break
        label = field_def.get("label", label)
        node = field_def.get("fields", {})
    return label


def _numeric_delta(before: object, after: object) -> float | None:
    try:
        return float(after) - float(before)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _format_dice_expression(sides: int, modifier: int) -> str:
    if modifier > 0:
        return f"d{sides}+{modifier}"
    if modifier < 0:
        return f"d{sides}{modifier}"
    return f"d{sides}"


def _title_case(segment: str) -> str:
    return segment.replace("_", " ").title()


def _to_int(value: object, default: int) -> int:
    try:
        return int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
