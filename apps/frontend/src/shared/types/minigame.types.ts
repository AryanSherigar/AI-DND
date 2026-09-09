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

/** Curated hazards only. Their collision geometry is deliberately not authorable. */
export type DodgePattern = "rain" | "ring" | "beam" | "homing";
export type DodgePlayerStyle = "soul" | "heart" | "spark";
export type DodgeObstacleStyle = "ash" | "neon" | "crystal";
export type DodgeBackground = "void" | "ember" | "midnight";
export type DodgeTexture = "none" | "grain" | "stars";
export type DodgePalette = "ashfall" | "ember" | "aurora";

export interface DodgePerformanceThresholds {
  excellent_min_health: number;
  survive_min_health: number;
}

export interface DodgeAudioSettings {
  /** Storage URL returned by the application's uploader; external URLs are not accepted. */
  music_asset_url: string | null;
  volume: number;
  muted: boolean;
}

export interface DodgeCopy {
  instructions: string;
  start_text: string;
  win_text: string;
  lose_text: string;
}

export interface DodgeConfigShape {
  /** Allows readers to safely evolve this presentation-only contract. */
  version?: number;
  difficulty: number; // 1-5
  duration_seconds?: number;
  health?: number;
  invulnerability_ms?: number;
  enabled_patterns?: DodgePattern[];
  pattern_order?: DodgePattern[];
  performance_thresholds?: DodgePerformanceThresholds;
  player_style?: DodgePlayerStyle;
  obstacle_style?: DodgeObstacleStyle;
  obstacle_color?: string;
  background?: DodgeBackground;
  texture?: DodgeTexture;
  palette?: DodgePalette;
  background_asset_url?: string | null;
  audio?: DodgeAudioSettings;
  copy?: DodgeCopy;
}

export const DEFAULT_DODGE_CONFIG: DodgeConfigShape = {
  version: 1,
  difficulty: 3,
  duration_seconds: 15,
  health: 3,
  invulnerability_ms: 1000,
  enabled_patterns: ["rain", "ring", "beam", "homing"],
  pattern_order: ["rain", "ring", "beam", "homing"],
  performance_thresholds: { excellent_min_health: 3, survive_min_health: 1 },
  player_style: "soul",
  obstacle_style: "ash",
  obstacle_color: "#ff8a65",
  background: "void",
  texture: "none",
  palette: "ashfall",
  background_asset_url: null,
  audio: { music_asset_url: null, volume: 0.7, muted: false },
  copy: {
    instructions: "Survive the ashfall. Move with WASD and avoid hazards.",
    start_text: "Start",
    win_text: "Survived!",
    lose_text: "Defeated...",
  },
};

// The play-time payload delivered via the "minigame" SSE event. Deliberately
// carries no mutation/outcome data — TRS alone decides state consequences;
// the client only ever reports what happened (see MinigameResultPayload).
export interface MinigameEventPayload {
  minigame_id: string;
  /** Server-issued identifier for this unresolved encounter. Reused on retries. */
  attempt_id?: string;
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
  /** Must be the attempt_id supplied in MinigameEventPayload when available. */
  attempt_id?: string;
}

// What a minigame implementation (DodgeMinigame, ReplitEmbedMinigame) hands
// back on completion — everything MinigameResultPayload needs except
// minigame_id, which the caller (MinigameOverlay in play/, or a Studio
// preview) already knows and attaches itself.
export type MinigameOutcomeResult = Omit<MinigameResultPayload, "minigame_id">;
