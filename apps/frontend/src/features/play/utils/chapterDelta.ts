import { ToolCallLogEntry } from "../api/turns.api";
import { ChapterDelta, MasterEntity } from "../types/play.types";
import { TurnSummaryEventPayload } from "../types/turnSummary.types";

/** Live path: the turn_summary SSE event is already display-ready. */
export function mapTurnSummaryEvent(
  payload: TurnSummaryEventPayload,
): ChapterDelta {
  return {
    stat_changes: payload.stat_changes,
    inventory_changes: payload.inventory_changes,
    dice_rolls: payload.dice_rolls,
  };
}

/**
 * Historical-reload path: reconstructs a ChapterDelta from a turn's stored
 * tool_calls. NOTE: unlike the live SSE path, there is no pre-turn state
 * snapshot to diff against here, so stat changes only carry an `after` value
 * (never `before`/`delta`) — dice rolls are fully reconstructable since their
 * roll/modifier/total are self-contained in the tool call's result.
 */
export function buildChapterDeltaFromToolCalls(
  toolCalls: ToolCallLogEntry[],
  entities: MasterEntity[],
): ChapterDelta {
  const entityById = new Map(entities.map((e) => [e.entity_id, e]));
  const delta: ChapterDelta = {
    stat_changes: [],
    inventory_changes: [],
    dice_rolls: [],
  };

  for (const call of toolCalls) {
    if (!call.is_valid) continue;
    addToolCallToDelta(call, entityById, delta);
  }
  return delta;
}

function addToolCallToDelta(
  call: ToolCallLogEntry,
  entityById: Map<string, MasterEntity>,
  delta: ChapterDelta,
): void {
  if (
    call.tool_name === "set_field" ||
    call.tool_name === "adjust_numeric_field"
  ) {
    delta.stat_changes.push(buildHistoricalStatChange(call));
  } else if (call.tool_name === "add_inventory_item") {
    delta.inventory_changes.push(
      buildHistoricalInventoryChange(call, entityById),
    );
  } else if (call.tool_name === "roll_dice") {
    delta.dice_rolls.push(buildHistoricalDiceRoll(call));
  }
}

function buildHistoricalStatChange(call: ToolCallLogEntry) {
  const path = String(call.arguments.path ?? "");
  const delta =
    call.tool_name === "adjust_numeric_field"
      ? toNumberOrNull(call.arguments.delta)
      : null;
  return {
    path,
    label: humanizePath(path),
    after:
      call.tool_name === "set_field"
        ? (call.arguments.value as string | number | boolean | null | undefined)
        : undefined,
    delta,
  };
}

function buildHistoricalInventoryChange(
  call: ToolCallLogEntry,
  entityById: Map<string, MasterEntity>,
) {
  const entityId = String(call.arguments.entity_id ?? "");
  const path = String(call.arguments.path ?? "");
  const entity = entityById.get(entityId);
  return {
    path,
    entity_id: entityId,
    entity_display_name: entity?.canonical_name ?? entityId,
  };
}

function buildHistoricalDiceRoll(call: ToolCallLogEntry) {
  const sides = toNumberOrNull(call.arguments.sides) ?? 20;
  const modifier = toNumberOrNull(call.result.modifier) ?? 0;
  const roll = toNumberOrNull(call.result.roll) ?? 0;
  const total = toNumberOrNull(call.result.total) ?? roll + modifier;
  return {
    expression: formatDiceExpression(sides, modifier),
    sides,
    modifier,
    roll,
    total,
  };
}

function formatDiceExpression(sides: number, modifier: number): string {
  if (modifier > 0) return `d${sides}+${modifier}`;
  if (modifier < 0) return `d${sides}${modifier}`;
  return `d${sides}`;
}

function humanizePath(path: string): string {
  const segments = path.split(".");
  const last = segments[segments.length - 1] ?? path;
  return last.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function toNumberOrNull(value: unknown): number | null {
  const num = Number(value);
  return Number.isFinite(num) ? num : null;
}
