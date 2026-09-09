import type { DodgeConfigShape } from "@/shared/types/minigame.types";

export interface DodgeMinigameConfig extends DodgeConfigShape {
  /** Optional bounded overrides from newer scenario snapshots. */
  duration_ms?: number;
  duration_seconds?: number;
  hit_points?: number;
  health?: number;
  invulnerability_ms?: number;
  instructions?: string;
  start_text?: string;
  result_copy?: string;
}

export interface DodgeMinigameOutcome {
  outcome_tag: "win" | "lose";
  score: number;
}

export interface DodgeMinigameProps {
  dodgeConfig: DodgeMinigameConfig;
  onComplete: (result: DodgeMinigameOutcome) => void;
  /** Canonical built-in tension track, resolved by the network-aware parent
   * (this component makes no network calls itself). */
  tensionDefaultTrackUrl?: string;
}
