// Single source of truth for the "Effect C" state-mutation shape used by
// scenario_conditions, end_conditions-adjacent flows, and scenario_minigames
// outcome mutations. Lives in shared/ because features/play/ needs it
// (minigame result resolution) and features/studio/ needs it (authoring
// editors) — features never import from each other, per CLAUDE.md.

export type StateMutationOp = "set" | "increment" | "decrement";

export interface StateMutation {
  path: string;
  op: StateMutationOp;
  value: unknown;
}
