import { DiceRoll, InventoryChange, StatChange } from "./play.types";

// Wire shape of TRS's `turn_summary` SSE event
// (turn-resolution-service/app/models/turn_summary.py::TurnSummaryPayload).
export interface TurnSummaryEventPayload {
  stat_changes: StatChange[];
  inventory_changes: InventoryChange[];
  dice_rolls: DiceRoll[];
  active_conditions: string[];
}
