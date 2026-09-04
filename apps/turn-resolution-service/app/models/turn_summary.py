"""Pydantic shapes for the master-mode `turn_summary` SSE event.

Translates this turn's validated tool calls (app/models/tool_call.py::
ToolCallLogEntry) into display-ready deltas the play screen renders as an
end-of-chapter summary strip — see app/turn/steps/turn_summary_builder.py.
"""

from pydantic import BaseModel, Field


class StatChange(BaseModel):
    """One resolved set_field/adjust_numeric_field mutation, display-ready."""

    path: str
    label: str
    before: str | float | bool | None = None
    after: str | float | bool | None = None
    delta: float | None = None


class InventoryChange(BaseModel):
    """One resolved add_inventory_item mutation, display-ready."""

    path: str
    entity_id: str
    entity_display_name: str


class DiceRoll(BaseModel):
    """One resolved roll_dice call, display-ready."""

    expression: str
    sides: int
    modifier: int
    roll: int
    total: int


class TurnSummaryPayload(BaseModel):
    """Payload of the `turn_summary` SSE event — master mode only."""

    stat_changes: list[StatChange] = Field(default_factory=list)
    inventory_changes: list[InventoryChange] = Field(default_factory=list)
    dice_rolls: list[DiceRoll] = Field(default_factory=list)
    active_conditions: list[str] = Field(default_factory=list)
