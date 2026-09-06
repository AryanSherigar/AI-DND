// Master-mode Minigames shapes, shared between studio/ (authoring) and
// play/ (gameplay) — features never import from each other, so this shape
// lives in shared/ per CLAUDE.md. See docs/specs/master-mode-minigames.spec.md.

import type { StateMutation } from "./stateMutation.types";

export type { StateMutationOp, StateMutation } from "./stateMutation.types";

export type MinigameType = "dodge" | "replit_embed";
export type OutcomeMode = "binary" | "tiered";
export type MinigameOutcomeTag = "win" | "lose" | "timeout";

export interface TieredOutcomeRange {
  min_score: number;
  max_score: number;
  mutation: StateMutation;
}

export interface DodgeConfigShape {
  difficulty: number; // 1-5
}

// The play-time payload delivered via the "minigame" SSE event. Deliberately
// carries no mutation/outcome data — TRS alone decides state consequences;
// the client only ever reports what happened (see MinigameResultPayload).
export interface MinigameEventPayload {
  minigame_id: string;
  minigame_type: MinigameType;
  label: string;
  dodge_config: DodgeConfigShape | null;
  replit_embed_url: string | null;
  timeout_seconds: number;
}

export interface MinigameResultPayload {
  minigame_id: string;
  outcome_tag: MinigameOutcomeTag;
  score?: number;
}
